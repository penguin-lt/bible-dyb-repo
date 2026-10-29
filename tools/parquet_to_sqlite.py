#!/usr/bin/env python3
"""One SQLite database per Bible translation, from bibles.parquet.

Each file is self-contained and carries no data belonging to any other
translation: its own verses, only the books it actually contains, its own
catalogue row, and FTS5 over its own text. Nothing is duplicated across files,
so the whole set is the corpus and nothing more.

Layout of every file (schema version 1):

    book        book_id, book_name, book_order, book_sort, testament
                -- only the books this translation has, in reading order
    translation translation_id, name, year, language, scope, canon,
                versification, licence + evidence, source, counts, text hash
    verse       book_id, chapter, verse, verse_end, text  (PRIMARY KEY book,chapter,verse)
    verse_fts   FTS5 over verse.text, external content
    note        k/v build provenance

    python3 tools/parquet_to_sqlite.py --bibles bibles.parquet \\
        --translations translations.csv --books books.csv --out-dir sqbible/
"""
import argparse
import csv
import hashlib
import os
import sqlite3
import time

import pyarrow.compute as pc
import pyarrow.parquet as pq

SCHEMA = """
PRAGMA page_size = 4096;

CREATE TABLE translation (
    translation_id     TEXT PRIMARY KEY,
    translation_name   TEXT NOT NULL,
    year_published     INTEGER,
    language           TEXT,
    scope              TEXT,
    canon              TEXT,
    versification      TEXT,
    license            TEXT,
    license_type       TEXT,
    license_url        TEXT,
    source_name        TEXT,
    source_url         TEXT,
    source_retrieved   TEXT,
    verse_count        INTEGER,
    book_count         INTEGER,
    chapter_count      INTEGER,
    word_count         INTEGER,
    ot_verses          INTEGER,
    nt_verses          INTEGER,
    dc_verses          INTEGER,
    text_sha256        TEXT
) WITHOUT ROWID;

CREATE TABLE book (
    book_id    TEXT PRIMARY KEY,
    book_name  TEXT NOT NULL,
    book_order INTEGER NOT NULL,     -- reading order within this translation
    book_sort  INTEGER,              -- global position in the canonical list
    testament  TEXT
) WITHOUT ROWID;

-- a normal rowid table: FTS5 external-content indexes address rows by rowid,
-- which a WITHOUT ROWID table does not have. The primary key is still enforced.
CREATE TABLE verse (
    book_id   TEXT NOT NULL REFERENCES book(book_id),
    chapter   INTEGER NOT NULL,
    verse     INTEGER NOT NULL,
    verse_end INTEGER,
    text      TEXT NOT NULL,
    PRIMARY KEY (book_id, chapter, verse)
);

CREATE VIRTUAL TABLE verse_fts USING fts5(
    text, content='verse', content_rowid='rowid',
    tokenize="unicode61 remove_diacritics 2");

CREATE TABLE note (k TEXT PRIMARY KEY, v TEXT) WITHOUT ROWID;
"""

# translations.csv column -> translation table column
MANIFEST = [
    ("translation_name", "translation_name"),
    ("year_first_published", "year_published"),
    ("dialect", "language"),
    ("scope", "scope"),
    ("canon", "canon"),
    ("versification", "versification"),
    ("license", "license"),
    ("license_type", "license_type"),
    ("license_url", "license_url"),
    ("source_name", "source_name"),
    ("source_url", "source_url"),
    ("source_retrieved", "source_retrieved"),
    ("verse_count", "verse_count"),
    ("book_count", "book_count"),
    ("chapter_count", "chapter_count"),
    ("word_count", "word_count"),
    ("ot_verses", "ot_verses"),
    ("nt_verses", "nt_verses"),
    ("dc_verses", "dc_verses"),
    ("text_sha256", "text_sha256"),
]


def build(tbl, books, manifest, tid, path):
    if os.path.exists(path):
        os.remove(path)
    rows = tbl.filter(pc.equal(tbl["translation_id"], tid))
    d = rows.to_pydict()
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)

    # books actually present, numbered in this translation's reading order
    present = {}
    for bid, bname, bsort in zip(d["book_id"], d["book_name"], d["book_sort"]):
        present.setdefault(bid, (bname, bsort))
    order = {}
    # reading order must follow the file, not alphabetical: take the first
    # position each book appears in, which is how bibles.parquet is sorted
    seen = []
    for bid in d["book_id"]:
        if bid not in seen:
            seen.append(bid)
    for i, bid in enumerate(seen, 1):
        order[bid] = i

    db.executemany("INSERT INTO book VALUES (?,?,?,?,?)",
                   [(bid, present[bid][0], order[bid], present[bid][1],
                     books.get(bid, {}).get("Testament"))
                    for bid in seen])

    db.executemany("INSERT INTO verse VALUES (?,?,?,?,?)",
                   zip(d["book_id"], d["chapter"], d["verse"],
                       d["verse_end"], d["verse_text"]))

    m = manifest.get(tid, {})
    vals = [tid]
    for src, _ in MANIFEST:
        v = m.get(src, "")
        if src in ("year_first_published", "verse_count", "book_count",
                   "chapter_count", "word_count", "ot_verses", "nt_verses",
                   "dc_verses"):
            try:
                v = int(v)
            except (TypeError, ValueError):
                v = None
        vals.append(v if v != "" else None)
    db.execute("INSERT INTO translation VALUES (" + ",".join("?" * len(vals)) + ")", vals)

    db.execute("INSERT INTO verse_fts(verse_fts) VALUES('rebuild')")
    db.executemany("INSERT INTO note VALUES (?,?)", [
        ("schema", "1"),
        ("built", time.strftime("%Y-%m-%d")),
        ("source", "penguin-lt/bible-dyb-repo bibles/text (rev8)"),
        ("generator", "tools/parquet_to_sqlite.py"),
        ("text_sha256", m.get("text_sha256", "") or ""),
    ])
    db.commit()
    db.execute("ANALYZE")
    db.commit()
    db.close()
    return len(d["book_id"]), len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bibles", required=True)
    ap.add_argument("--translations", default="")
    ap.add_argument("--books", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    manifest = {}
    if a.translations:
        for r in csv.DictReader(open(a.translations)):
            manifest[r["translation_id"]] = r
    books = {}
    if a.books:
        for r in csv.DictReader(open(a.books)):
            books[r["book_id"]] = r

    tbl = pq.read_table(a.bibles, columns=["translation_id", "book_id", "book_name",
                                           "book_order", "book_sort", "Testament",
                                           "chapter", "verse", "verse_end", "verse_text"])
    ids = sorted(set(tbl.column("translation_id").to_pylist()))
    if a.only:
        ids = [i for i in ids if i in a.only]
    print(f"{len(ids)} translations")

    total = 0
    t0 = time.time()
    for tid in ids:
        path = os.path.join(a.out_dir, f"{tid}.sqlite3")
        n, nb = build(tbl, books, manifest, tid, path)
        size = os.path.getsize(path)
        total += size
        print(f"  {tid:18} {nb:>3} books {n:>7,} verses {size/1e6:7.2f} MB", flush=True)
    print(f"\n{len(ids)} files, {total/1e6:.1f} MB total, in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
