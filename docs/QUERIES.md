# Query recipes

Two datasets, one join key, one file per thing. SQLite is the storage format, so
there is no server and no import step — `sqlite3` is in the Python standard library,
and the `sqlite3` CLI, DB Browser and DuckDB (`INSTALL sqlite; LOAD sqlite;`) all open
the files directly.

```bash
git clone https://github.com/penguin-lt/bible-dyb-repo.git bible-db && cd bible-db
curl -L -O https://github.com/penguin-lt/bible-dyb-repo/releases/download/bibles-sqlite-rev9/bibles-sqlite-rev9.zip
curl -L -O https://github.com/penguin-lt/bible-dyb-repo/releases/download/reference-sqlite-rev5/reference-sqlite-part1of2.zip
curl -L -O https://github.com/penguin-lt/bible-dyb-repo/releases/download/reference-sqlite-rev5/reference-sqlite-part2of2.zip
mkdir -p data && unzip -q bibles-sqlite-rev9.zip -d data && unzip -q 'reference-sqlite-part*.zip' -d data
```

Throughout, a translation is one file (`data/AKJV.sqlite3`) with a `verse` table and
a `book` table, and a reference work is one file (`data/MHC.sqlite3`) with an `entry`
table. To work per translation you open exactly one small file — there is no larger
file to prune. To span several, `ATTACH` the ones you need:

```sql
ATTACH 'data/AKJV.sqlite3' AS kjv;
ATTACH 'data/MHC.sqlite3'  AS mhc;
```

> **There is no `KJV` translation in this corpus.** The King James text is
> `AKJV` (Authorised Version, American revision of the KJV), with `KJV1611` for
> the original 1611 edition and `KJVA` for KJV with Apocrypha. Every recipe below
> that says `'KJV'` is really using `'AKJV'`.

---

## 1. Compare translations on one verse

Open each translation file in turn — there is no combined table to filter:

```python
import glob, sqlite3
for path in sorted(glob.glob("data/*.sqlite3")):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    row = db.execute("SELECT verse_text FROM verse WHERE book_id='JHN' "
                     "AND chapter=3 AND verse=16").fetchone()
    if row:
        print(db.execute("SELECT translation_id FROM translation").fetchone()[0], row[0])
```

## 2. A verse with its commentaries, side by side

```sql
ATTACH 'data/AKJV.sqlite3'  AS kjv;
ATTACH 'data/MHC.sqlite3'   AS mhc;
ATTACH 'data/Clarke.sqlite3' AS clarke;
ATTACH 'data/JFB.sqlite3'   AS jfb;
ATTACH 'data/Barnes.sqlite3' AS barnes;

SELECT v.text AS verse,
       (SELECT entry_text FROM mhc.entry    WHERE book_id='ROM' AND chapter=8 AND verse=28) AS matthew_henry,
       (SELECT entry_text FROM clarke.entry WHERE book_id='ROM' AND chapter=8 AND verse=28) AS clarke,
       (SELECT entry_text FROM jfb.entry    WHERE book_id='ROM' AND chapter=8 AND verse=28) AS jfb,
       (SELECT entry_text FROM barnes.entry WHERE book_id='ROM' AND chapter=8 AND verse=28) AS barnes
FROM kjv.verse v WHERE v.book_id='ROM' AND v.chapter=8 AND v.verse=28;
```

## 3. Which works actually cover a given chapter?

The question now spans files, so read the manifests rather than the entries — each
file's `work` table has the work's name, category and entry count:

```python
import glob, sqlite3
hits = []
for path in sorted(glob.glob("data/*.sqlite3")):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    n = db.execute("SELECT count(*) FROM entry WHERE book_id='REV' AND chapter=21").fetchone()[0]
    if n:
        hits.append((n, db.execute("SELECT module_id, category FROM work").fetchone()))
print(sorted(hits, reverse=True)[:20])
```

Useful before trusting an absence: not every commentary covers every verse.

## 4. Every scripture reference the reference library makes, as edges

```sql
ATTACH 'data/TSK.sqlite3' AS tsk;
CREATE TABLE refs AS
SELECT book_id, chapter, verse, entry_key FROM tsk.entry WHERE book_id IS NOT NULL;
```

210,522 entries across the whole library carry a parsed reference — enough to
build a cross-reference graph. Iterate the files and union them, or use the app's
prebuilt `works.db` (see `app/`) if you want that graph already assembled.

## 5. Look up a word in every dictionary at once

```python
import glob, sqlite3
for path in sorted(glob.glob("data/*.sqlite3")):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    w = db.execute("SELECT category FROM work").fetchone()
    if not w or w[0] not in ("Dictionary", "Lexicon"):
        continue
    for key, text in db.execute("SELECT entry_key, entry_text FROM entry "
                                "WHERE upper(entry_key)='ATONEMENT'"):
        print(db.execute("SELECT module_id FROM work").fetchone()[0], key, text[:200])
```

## 6. Strong's numbers across lexicons

`StrongsGreek` / `StrongsHebrew` key on the number (`00026`, `H0430`), and
`BDBGlosses_Strongs`, `AbbottSmithStrongs`, `MLStrong`, `OSHM` key on the same
numbers:

```python
import sqlite3
for mod in ("StrongsGreek", "StrongsHebrew", "BDBGlosses_Strongs", "AbbottSmithStrongs"):
    db = sqlite3.connect(f"data/{mod}.sqlite3")
    print(mod, db.execute("SELECT entry_key, substr(entry_text,1,120) FROM entry "
                          "WHERE entry_key IN ('H0430','0430','0026')").fetchall())
```

(Greek modules zero-pad to five digits without the `G`; Hebrew `RawLD` modules
use `H`-prefixed keys. Normalise before comparing — see `docs/SCHEMA.md`.)

## 7. Word frequency in the corpus, by translation

```python
import glob, sqlite3
for path in sorted(glob.glob("data/*.sqlite3")):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    tid, n = db.execute("SELECT translation_id, verse_count FROM translation").fetchone()
    print(tid, n)
```

Counts are stored per translation in the manifest row, so this needs no scan.

## 8. Where translations disagree about a verse's presence

```python
import collections, glob, sqlite3
seen = collections.Counter()
for path in sorted(glob.glob("data/*.sqlite3")):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seen.update(db.execute("SELECT book_id||':'||chapter||':'||verse FROM verse").fetchall())
print([k[0] for k, n in seen.most_common() if n < 40][:50])
```

## 9. Build a searchable full-text table

Every file already carries one — `verse_fts` in translations, `entry_fts` in
reference works — so there is nothing to build:

```sql
ATTACH 'data/Clarke.sqlite3' AS clarke;
SELECT c.entry_key, snippet(c.entry_fts, 1, '[', ']', '…', 12)
FROM clarke.entry_fts JOIN clarke.entry e ON e.rowid = clarke.entry_fts.rowid
WHERE clarke.entry_fts MATCH 'justification' ORDER BY rank LIMIT 20;
```
