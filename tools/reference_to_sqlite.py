#!/usr/bin/env python3
"""One SQLite database per reference work, from reference.parquet + modules.parquet.

Every file carries everything needed to read it on its own. Layout (schema 1):

    work   the single row from modules.parquet for this module - all 25 columns,
           same names, same order, plus any extra catalogue columns
    entry  entry_key, entry_order, book_id, chapter, verse, entry_text,
           char_count - all 7 columns of reference.parquet, same order
    entry_fts  FTS5 over the work's own entries, external content
    note   k/v build provenance, entry count, text hash, and the original
           parquet module_id when it differed from the catalogue id

Rows are inserted as they are read, so the corpus is never held in memory.
On a small machine use --slice K/N and run the slices in sequence.

    python3 tools/reference_to_sqlite.py --reference reference.parquet \\
        --modules modules.parquet --out-dir refsqlite/ [--only BDB TSK]
"""
import argparse
import gc
import hashlib
import os
import re
import sqlite3
import time

import pyarrow as pa
import pyarrow.parquet as pq

ENTRY_COLS = ["entry_key", "entry_order", "book_id", "chapter", "verse",
              "entry_text", "char_count"]

SCHEMA = """
PRAGMA page_size = 4096;
PRAGMA cache_size = -8000;
PRAGMA mmap_size = 0;

CREATE TABLE work (
    module_id                  TEXT PRIMARY KEY,
    module_name                TEXT,
    category                   TEXT,
    topic                      TEXT,
    topic_secondary            TEXT,
    sword_driver               TEXT,
    language                   TEXT,
    license                    TEXT,
    copyright                  TEXT,
    source_name                TEXT,
    source_url                 TEXT,
    download_url               TEXT,
    module_version             TEXT,
    sword_version_date         TEXT,
    text_source                TEXT,
    markup_source_type         TEXT,
    about                      TEXT,
    license_basis              TEXT,
    entry_count                INTEGER,
    empty_entries_skipped      INTEGER,
    duplicate_entries_dropped  INTEGER,
    repeated_keys_disambiguated INTEGER,
    char_count                 INTEGER,
    scripture_linked_entries   INTEGER,
    retrieved                  TEXT
);

CREATE TABLE entry (
    entry_key   TEXT,
    entry_order INTEGER,
    book_id     TEXT,
    chapter     INTEGER,
    verse       INTEGER,
    entry_text  TEXT,
    char_count  INTEGER
);

CREATE VIRTUAL TABLE entry_fts USING fts5(
    entry_key, entry_text, content='entry', content_rowid='rowid',
    tokenize="unicode61 remove_diacritics 2");

CREATE TABLE note (k TEXT PRIMARY KEY, v TEXT);
"""

EXTRA_COLS = []
EXTRAS = {}

_LANG = re.compile(r"_(?:en|he|la|fr|de|es|it|nl|ru|ar|ko|zh|mal|grc|syr|gez|"
                   r"pt|pl|yi|ja|sa|fa|tr|el|hu|cs|sv|da|fi|no|ro)_")


def trim():
    gc.collect()
    pa.default_memory_pool().release_unused()


def safe_name(module_id):
    return "".join(c if (c.isalnum() or c in "-_. ") else "_" for c in module_id)


def new_db(path):
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    schema = SCHEMA
    if EXTRA_COLS:
        add = ", ".join(f"{c} TEXT" for c in EXTRA_COLS)
        schema = schema.replace("    retrieved                  TEXT\n);",
                                "    retrieved                  TEXT,\n    " + add + "\n);")
    db.executescript(schema)
    return db


def build_id_map(reference, mods):
    """Map reference.parquet module_ids onto catalogue module_ids.

    268 of 9,141 works carry "<catalogue_id>_<lang>_<Title...>" in the reference
    rows but the bare "<catalogue_id>" in modules.parquet. Resolution is
    longest-catalogue-prefix, plus a reverse rule for the one work that runs the
    other way. The original id is recorded in each file's note table.
    """
    seen = set()
    for b in pq.ParquetFile(reference).iter_batches(batch_size=4_000,
                                                    columns=["module_id"]):
        seen.update(b.column(0).to_pylist())
        del b
        trim()
    ids = sorted(mods)
    mapping, unresolved = {}, []
    for pid in seen:
        if pid in mods:
            mapping[pid] = pid
            continue
        cands = [c for c in ids if pid.startswith(c + "_")]
        if not cands:
            base = _LANG.split(pid)[0]
            cands = [c for c in ids if c.startswith(base)]
        if cands:
            mapping[pid] = max(cands, key=len)
        else:
            unresolved.append(pid)
    return mapping, unresolved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True)
    ap.add_argument("--modules", required=True)
    ap.add_argument("--modules-extra", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--slice", default="")
    ap.add_argument("--no-fix-ids", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    mods = {r["module_id"]: r for r in pq.read_table(a.modules).to_pylist()}
    mcols = pq.read_schema(a.modules).names
    print(f"{len(mods)} works in the catalogue")

    idmap = {k: k for k in mods}
    if not a.no_fix_ids:
        idmap, unresolved = build_id_map(a.reference, mods)
        drift = sum(1 for k, v in idmap.items() if k != v)
        print(f"module_id repair: {drift} drifted ids mapped, "
              f"{len(unresolved)} unresolvable")
        if a.only:
            a.only = sorted({idmap.get(x, x) for x in a.only})

    global EXTRA_COLS
    if a.modules_extra:
        et = pq.read_table(a.modules_extra)
        EXTRA_COLS = [c for c in et.schema.names if c not in mcols]
        for r in et.to_pylist():
            EXTRAS[idmap.get(r["module_id"], r["module_id"])] = r
        print(f"extra catalogue: {et.num_rows} rows, extra columns {EXTRA_COLS}")

    if a.slice:
        k, ntot = (int(x) for x in a.slice.split("/"))
        order = sorted(mods)
        lo, hi = (k - 1) * len(order) // ntot, k * len(order) // ntot
        keep = set(order[lo:hi])
        a.only = sorted(keep & set(a.only)) if a.only else sorted(keep)
        print(f"slice {k}/{ntot}: {len(a.only)} works [{lo}:{hi}]", flush=True)

    pf = pq.ParquetFile(a.reference)
    t0 = time.time()
    counts, wrote_any = {}, set()
    cur = None

    def open_work(mid):
        db = new_db(os.path.join(a.out_dir, safe_name(mid) + ".sqlite3"))
        m, ex = mods.get(mid, {}), EXTRAS.get(mid, {})
        cols = mcols + EXTRA_COLS
        db.execute(f"INSERT INTO work ({', '.join(cols)}) VALUES "
                   f"({','.join('?' * len(cols))})",
                   [m.get(c) if c not in EXTRA_COLS else ex.get(c) for c in cols])
        return {"mid": mid, "db": db, "n": 0, "h": hashlib.sha256(), "raw": set()}

    def close_work(w):
        db, mid, n = w["db"], w["mid"], w["n"]
        drifted = sorted(r for r in w["raw"] if r != mid)
        db.execute("INSERT INTO entry_fts(entry_fts) VALUES('rebuild')")
        db.executemany("INSERT INTO note VALUES (?,?)", [
            ("schema", "1"),
            ("built", time.strftime("%Y-%m-%d")),
            ("source", "penguin-lt/bible-dyb-repo bible-reference-v5"),
            ("generator", "tools/reference_to_sqlite.py"),
            ("module_id", mid),
            ("parquet_module_id", ";".join(drifted) if drifted else mid),
            ("entries", str(n)),
            ("text_sha256", w["h"].hexdigest()),
        ])
        db.commit()
        db.execute("ANALYZE")
        db.commit()
        db.close()
        counts[mid] = n
        if n:
            wrote_any.add(mid)

    for batch in pf.iter_batches(batch_size=4_000,
                                 columns=["module_id"] + ENTRY_COLS):
        d = batch.to_pydict()
        ids = [idmap.get(m, m) for m in d["module_id"]]
        i, n_rows = 0, len(ids)
        while i < n_rows:
            mid = ids[i]
            j = i
            while j < n_rows and ids[j] == mid:
                j += 1
            if a.only and mid not in a.only:
                i = j
                continue
            if cur is None or cur["mid"] != mid:
                if cur is not None:
                    close_work(cur)
                cur = open_work(mid)
            sl = slice(i, j)
            cur["db"].executemany("INSERT INTO entry VALUES (?,?,?,?,?,?,?)",
                                  zip(*[d[c][sl] for c in ENTRY_COLS]))
            for t in d["entry_text"][sl]:
                cur["h"].update((t or "").encode())
            cur["n"] += j - i
            cur["raw"].update(d["module_id"][sl])
            i = j
        del d, batch, ids
        trim()
    if cur is not None:
        close_work(cur)

    missing = [m for m in mods if (not a.only or m in a.only) and m not in wrote_any]
    print(f"\n{len(counts)} files, {sum(counts.values()):,} entries, "
          f"{time.time()-t0:.0f}s")
    if missing:
        print(f"works with no entries: {len(missing)} e.g. {missing[:5]}")
    os.sync()


if __name__ == "__main__":
    main()
