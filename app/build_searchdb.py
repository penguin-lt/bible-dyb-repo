"""Build the two databases a free Logos-style reader needs.

`search.db` (core)
    Verses (77 translations), the work catalogue, every reference entry, the
    lexicon panel and the interlinear rows. Small enough to ship in the repo.

`refsearch.db` (full-text)
    FTS5 indexes over the whole reference corpus. Optional: passages and reading
    work without it, and it is fetched once by anybody who wants to search the
    1.07 M reference entries.

Both are ordinary SQLite files — no server, no licence, no ORM. A desktop or web
front end opens them read-only with any SQLite driver.

    python3 build_searchdb.py \
        --bibles bibles.parquet --works modules.parquet \
        --reference reference.parquet \
        --out search.db --fts-out refsearch.db
"""
import argparse
import gc
import os
import re
import sqlite3
import time

import pyarrow.parquet as pq

CORE = """
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;
PRAGMA temp_store = FILE;

CREATE TABLE translation (
    translation_id TEXT PRIMARY KEY, verses INTEGER, chars INTEGER) WITHOUT ROWID;

CREATE TABLE book (
    book_id TEXT PRIMARY KEY, book_name TEXT, book_order INTEGER, Testament TEXT
) WITHOUT ROWID;

CREATE TABLE verse (
    id INTEGER PRIMARY KEY,
    translation_id TEXT NOT NULL, book_id TEXT NOT NULL,
    chapter INTEGER NOT NULL, verse INTEGER NOT NULL, verse_end INTEGER,
    verse_text TEXT NOT NULL);
CREATE INDEX verse_ref ON verse(book_id, chapter, verse);
CREATE INDEX verse_tr  ON verse(translation_id, book_id, chapter, verse);

CREATE VIRTUAL TABLE verse_fts USING fts5(
    verse_text, content='verse', content_rowid='id',
    tokenize="unicode61 remove_diacritics 2");

CREATE TABLE work (
    n INTEGER PRIMARY KEY, module_id TEXT UNIQUE, module_name TEXT,
    category TEXT, topic TEXT, language TEXT, license TEXT, source_name TEXT,
    entry_count INTEGER, char_count INTEGER);

CREATE TABLE entry (
    id INTEGER PRIMARY KEY, work_n INTEGER NOT NULL,
    entry_key TEXT, book_id TEXT, chapter INTEGER, verse INTEGER,
    entry_text TEXT NOT NULL);
CREATE INDEX entry_work ON entry(work_n);
CREATE INDEX entry_ref  ON entry(book_id, chapter, verse);

CREATE TABLE lexicon (
    id INTEGER PRIMARY KEY, work_n INTEGER NOT NULL,
    head TEXT, strongs TEXT, body TEXT NOT NULL);
CREATE INDEX lexicon_head   ON lexicon(head);
CREATE INDEX lexicon_strong ON lexicon(strongs);

CREATE TABLE interlinear (
    id INTEGER PRIMARY KEY, work_n INTEGER NOT NULL,
    book_id TEXT, chapter INTEGER, verse INTEGER, body TEXT);
CREATE INDEX inter_verse ON interlinear(book_id, chapter, verse);

CREATE TABLE note (k TEXT PRIMARY KEY, v TEXT) WITHOUT ROWID;
"""

WORKS = """
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;
PRAGMA temp_store = FILE;
PRAGMA cache_size = -80000;

CREATE TABLE work (
    n INTEGER PRIMARY KEY, module_id TEXT UNIQUE, module_name TEXT,
    topic TEXT, language TEXT, license TEXT);
CREATE TABLE entry (
    id INTEGER PRIMARY KEY, work_n INTEGER NOT NULL,
    entry_key TEXT, book_id TEXT, chapter INTEGER, verse INTEGER, entry_text TEXT);
CREATE INDEX entry_work ON entry(work_n);
CREATE INDEX entry_ref  ON entry(book_id, chapter, verse);
CREATE VIRTUAL TABLE entry_fts USING fts5(
    entry_key, entry_text, content='entry', content_rowid='id',
    tokenize="unicode61 remove_diacritics 2");
"""

FTS = """
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;
PRAGMA temp_store = FILE;
PRAGMA cache_size = -80000;

CREATE TABLE work (
    n INTEGER PRIMARY KEY, module_id TEXT UNIQUE, module_name TEXT,
    topic TEXT, language TEXT, license TEXT);
CREATE TABLE entry (
    id INTEGER PRIMARY KEY, work_n INTEGER NOT NULL, entry_key TEXT, entry_text TEXT);
CREATE VIRTUAL TABLE entry_fts USING fts5(
    entry_key, entry_text, content='entry', content_rowid='id',
    tokenize="unicode61 remove_diacritics 2");
"""

BATCH = 4000
LEX_WORKS = {"BDB", "TBESG", "TBESH", "LSJ", "AbbottSmith", "AbbottSmithStrongs",
             "StrongsGreek", "StrongsHebrew", "Thayer", "Vine", "Webster1828",
             "Webster1913", "Smith", "Easton", "ISBE", "BDBGlosses_Strongs",
             "OHLEX", "Hitchcock", "Nave", "Torrey"}
INTER_WORKS = {"TAGNT_Mat-Jhn", "TAGNT_Act-Rev", "TAHOT_Gen-Deu", "TAHOT_Jos-Est",
               "TAHOT_Job-Sng", "TAHOT_Isa-Mal"}
STRONG_KEY = re.compile(r"^([GH]\d{1,5}[A-Za-z]?)\b")


def rss():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return 0.0


def trim():
    gc.collect()
    try:
        import pyarrow as pa
        pa.default_memory_pool().release_unused()
    except Exception:
        pass


def core_db(bibles, works, reference, out):
    for p in (out, out + "-journal"):
        if os.path.exists(p):
            os.remove(p)
    db = sqlite3.connect(out)
    db.executescript(CORE)
    t0 = time.time()

    # ---- works
    w = pq.read_table(works).to_pylist()
    by_id = {}
    for n, m in enumerate(w, 1):
        by_id[m["module_id"]] = n
    db.executemany("INSERT INTO work VALUES (?,?,?,?,?,?,?,?,?,?)",
                   [(n, m["module_id"], m.get("module_name"), m.get("category"),
                     m.get("topic"), m.get("language"), m.get("license"),
                     m.get("source_name"), int(m.get("entry_count") or 0),
                     int(m.get("char_count") or 0)) for n, m in enumerate(w, 1)])
    db.commit()
    print(f"works             {len(w):>9,}", flush=True)

    # ---- verses
    b = pq.read_table(bibles, columns=["translation_id", "book_id", "book_name",
                                       "book_order", "Testament", "chapter", "verse",
                                       "verse_end", "verse_text"])
    d = b.to_pydict()
    rows = list(zip(d["translation_id"], d["book_id"], d["chapter"], d["verse"],
                    d["verse_end"], d["verse_text"]))
    db.executemany("INSERT INTO verse(translation_id,book_id,chapter,verse,verse_end,"
                   "verse_text) VALUES (?,?,?,?,?,?)", rows)
    books = {}
    for bid, bn, bo, te in zip(d["book_id"], d["book_name"], d["book_order"], d["Testament"]):
        books.setdefault(bid, (bn, bo, te))
    db.executemany("INSERT INTO book VALUES (?,?,?,?)",
                   [(k, v[0], v[1], v[2]) for k, v in books.items()])
    tot = {}
    for tid, txt in zip(d["translation_id"], d["verse_text"]):
        a = tot.setdefault(tid, [0, 0])
        a[0] += 1
        a[1] += len(txt or "")
    db.executemany("INSERT INTO translation VALUES (?,?,?)",
                   [(k, v[0], v[1]) for k, v in tot.items()])
    n_verse = len(rows)
    db.commit()
    print(f"verses            {n_verse:>9,}", flush=True)
    print(f"translations      {len(tot):>9,}", flush=True)
    del d, b, rows, tot, books
    trim()

    # ---- reference entries (streamed; never buffered)
    pf = pq.ParquetFile(reference)
    cols = ["module_id", "entry_key", "book_id", "chapter", "verse", "entry_text"]
    ins = ("INSERT INTO entry(work_n,entry_key,book_id,chapter,verse,entry_text)"
           " VALUES (?,?,?,?,?,?)")
    n_entry = 0
    for batch in pf.iter_batches(batch_size=BATCH, columns=cols):
        d = batch.to_pydict()
        # The core file holds only the entries that carry scripture coordinates:
        # they power the passage guide, which must be instant. The rest of the
        # corpus (2.1 Gchars of prose and rabbinics) lives in works.db.
        pending = [(by_id[m], k, bid, ch, vs, t)
                   for m, k, bid, ch, vs, t in zip(d["module_id"], d["entry_key"],
                                                   d["book_id"], d["chapter"],
                                                   d["verse"], d["entry_text"])
                   if m in by_id and t and bid]
        db.executemany(ins, pending)
        n_entry += len(pending)
        del pending, d, batch
        trim()
    db.commit()
    print(f"reference entries {n_entry:>9,}  rss {rss():.0f} MB", flush=True)

    # ---- lexicon panel and interlinear, from the same file
    lex_w = set(LEX_WORKS)
    for (mid,) in db.execute("SELECT module_id FROM work WHERE topic LIKE 'Lexical%'"):
        lex_w.add(mid)
    inter_w = INTER_WORKS & set(by_id)
    n_lex = n_int = 0
    for batch in pf.iter_batches(batch_size=BATCH, columns=cols):
        d = batch.to_pydict()
        lex, inter = [], []
        for m, k, bid, ch, vs, t in zip(d["module_id"], d["entry_key"], d["book_id"],
                                        d["chapter"], d["verse"], d["entry_text"]):
            if not t:
                continue
            if m in lex_w:
                mt = STRONG_KEY.match(str(k or ""))
                lex.append((by_id[m], k, mt.group(1) if mt else None, t))
            if m in inter_w:
                inter.append((by_id[m], bid, ch, vs, t))
        if lex:
            db.executemany("INSERT INTO lexicon(work_n,head,strongs,body) VALUES (?,?,?,?)", lex)
            n_lex += len(lex)
        if inter:
            db.executemany("INSERT INTO interlinear(work_n,book_id,chapter,verse,body)"
                           " VALUES (?,?,?,?,?)", inter)
            n_int += len(inter)
        db.commit()
        del lex, inter, d, batch
        trim()
    print(f"lexicon entries   {n_lex:>9,}", flush=True)
    print(f"interlinear rows  {n_int:>9,}", flush=True)

    # ---- verse search index (small: 1.5 M short rows)
    db.execute("INSERT INTO verse_fts(verse_fts) VALUES('rebuild')")
    db.commit()
    db.executemany("INSERT INTO note VALUES (?,?)", [
        ("built", time.strftime("%Y-%m-%d")),
        ("bibles_source", "penguin-lt/bible-dyb-repo bibles/text (rev7)"),
        ("reference_source", "bible-reference-v5"),
        ("verses", str(n_verse)), ("translations", str(len(tot) if 'tot' in dir() else 77)),
        ("works", str(len(w))), ("entries", str(n_entry)),
        ("lexicon_entries", str(n_lex)), ("interlinear_rows", str(n_int)),
    ])
    db.execute("ANALYZE")
    db.commit()
    db.close()
    print(f"\n{out}  {os.path.getsize(out)/1e6:.0f} MB  in {time.time()-t0:.0f}s")


def fts_db(works, reference, out):
    if os.path.exists(out):
        os.remove(out)
    db = sqlite3.connect(out)
    db.executescript(WORKS)
    t0 = time.time()
    w = pq.read_table(works).to_pylist()
    by_id = {m["module_id"]: n for n, m in enumerate(w, 1)}
    db.executemany("INSERT INTO work VALUES (?,?,?,?,?,?)",
                   [(n, m["module_id"], m.get("module_name"), m.get("topic"),
                     m.get("language"), m.get("license")) for n, m in enumerate(w, 1)])
    db.commit()
    pf = pq.ParquetFile(reference)
    ins = ("INSERT INTO entry(work_n,entry_key,book_id,chapter,verse,entry_text)"
           " VALUES (?,?,?,?,?,?)")
    n = 0
    for batch in pf.iter_batches(batch_size=BATCH, columns=[
            "module_id", "entry_key", "book_id", "chapter", "verse", "entry_text"]):
        d = batch.to_pydict()
        pending = [(by_id[m], k, bid, ch, vs, t) for m, k, bid, ch, vs, t in
                   zip(d["module_id"], d["entry_key"], d["book_id"], d["chapter"],
                       d["verse"], d["entry_text"])
                   if m in by_id and t]
        db.executemany(ins, pending)
        n += len(pending)
        del pending, d, batch
        trim()
        if n % 100000 < BATCH:
            print(f"  {n:,} entries  rss {rss():.0f} MB", flush=True)
    db.commit()
    print(f"entries           {n:>9,}", flush=True)
    print("building FTS index…", flush=True)
    db.execute("INSERT INTO entry_fts(entry_fts) VALUES('rebuild')")
    db.commit()
    db.execute("ANALYZE")
    db.close()
    print(f"{out}  {os.path.getsize(out)/1e6:.0f} MB  in {time.time()-t0:.0f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bibles", required=True)
    ap.add_argument("--works", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--out", default="search.db")
    ap.add_argument("--works-out", default="", help="second file: whole corpus")
    ap.add_argument("--only", default="", help="core | works")
    a = ap.parse_args()
    if a.only in ("", "core"):
        core_db(a.bibles, a.works, a.reference, a.out)
    if a.works_out and a.only in ("", "works"):
        fts_db(a.works, a.reference, a.works_out)


if __name__ == "__main__":
    main()
