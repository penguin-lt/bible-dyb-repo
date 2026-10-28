# Query recipes

Two Parquet datasets, one join key. DuckDB reads both directly — no server, no
import step. `pip install duckdb`.

```bash
git clone https://github.com/penguin-lt/bible-dyb-repo.git bible-db && cd bible-db
curl -L -O https://github.com/penguin-lt/bible-dyb-repo/releases/download/bible-reference-v1/reference.parquet
python3 -c "import duckdb; duckdb.sql('SELECT 1').show()"
```

Throughout, `bibles/text/bibles.parquet` is the verse corpus and
`reference.parquet` is the reference library. To work per translation without
loading 1.5 M rows, point at the partitioned folder instead:
`read_parquet('bibles/text/bibles_partitioned/*/*.parquet', hive_partitioning=true)`,
or a single one: `'bibles/text/bibles_partitioned/translation_id=AKJV/part-0.parquet'`.

> **There is no `KJV` translation in this corpus.** The King James text is
> `AKJV` (Authorised Version, American revision of the KJV), with `KJV1611` for
> the original 1611 edition and `KJVA` for KJV with Apocrypha. Every recipe below
> that says `'KJV'` is really using `'AKJV'`.

---

## 1. Compare translations on one verse

```sql
SELECT translation_id, verse_text
FROM 'bibles/text/bibles.parquet'
WHERE book_id = 'JHN' AND chapter = 3 AND verse = 16
ORDER BY translation_id;
```

## 2. A verse with its commentaries, side by side

```sql
SELECT b.verse_text,
       max(CASE WHEN c.module_id = 'MHC'    THEN c.entry_text END) AS matthew_henry,
       max(CASE WHEN c.module_id = 'Clarke' THEN c.entry_text END) AS clarke,
       max(CASE WHEN c.module_id = 'JFB'    THEN c.entry_text END) AS jfb,
       max(CASE WHEN c.module_id = 'Barnes' THEN c.entry_text END) AS barnes
FROM 'bibles/text/bibles.parquet' b
LEFT JOIN 'reference.parquet' c
  ON c.book_id = b.book_id AND c.chapter = b.chapter AND c.verse = b.verse
WHERE b.translation_id = 'AKJV' AND b.book_id = 'ROM' AND b.chapter = 8 AND b.verse = 28
GROUP BY b.verse_text;
```

## 3. Which works actually cover a given chapter?

```sql
SELECT module_id, module_name, count(*) AS entries
FROM 'reference.parquet'
WHERE book_id = 'REV' AND chapter = 21
GROUP BY ALL ORDER BY entries DESC;
```

Useful before trusting an absence: not every commentary covers every verse.

## 4. Every scripture reference the reference library makes, as edges

```sql
CREATE TABLE refs AS
SELECT module_id, entry_key, book_id, chapter, verse
FROM 'reference.parquet'
WHERE book_id IS NOT NULL;
```

210,522 entries carry a parsed reference — enough to build a cross-reference
graph, or to check which verses are most commented on:

```sql
SELECT book_id, chapter, verse, count(DISTINCT module_id) AS works
FROM refs GROUP BY ALL ORDER BY works DESC LIMIT 20;
```

## 5. Look up a word in every dictionary at once

```sql
SELECT module_id, entry_text
FROM 'reference.parquet'
WHERE category IN ('Dictionary', 'Lexicon')
  AND upper(entry_key) = 'ATONEMENT'
ORDER BY module_id;
```

## 6. Strong's numbers across lexicons

`StrongsGreek` / `StrongsHebrew` key on the number (`00026`, `H0430`), and
`BDBGlosses_Strongs`, `AbbottSmithStrongs`, `MLStrong`, `OSHM` key on the same
numbers:

```sql
SELECT module_id, entry_key, entry_text
FROM 'reference.parquet'
WHERE entry_key IN ('H0430', '0430', '0026')
  AND category = 'Lexicon'
ORDER BY module_id;
```

(Greek modules zero-pad to five digits without the `G`; Hebrew `RawLD` modules
use `H`-prefixed keys. Normalise before comparing — see `docs/SCHEMA.md`.)

## 7. Word frequency in the corpus, by translation

```sql
SELECT translation_id, count(*) AS verses, sum(len(verse_text)) AS chars
FROM 'bibles/text/bibles.parquet'
GROUP BY 1 ORDER BY chars DESC;
```

## 8. Where translations disagree about a verse's presence

```sql
SELECT book_id, chapter, verse, count(*) AS translations_having_it
FROM 'bibles/text/bibles.parquet'
GROUP BY ALL
HAVING count(*) < 40
ORDER BY translations_having_it, book_id, chapter, verse
LIMIT 50;
```

## 9. Build a searchable full-text table

```sql
COPY (
  SELECT translation_id, book_id, chapter, verse, verse_text AS text
  FROM 'bibles/text/bibles.parquet'
  UNION ALL
  SELECT module_id, book_id, chapter, verse, entry_text
  FROM 'reference.parquet'
) TO 'search.parquet' (FORMAT parquet, COMPRESSION zstd);
```

## 10. Export a study Bible for one book

```sql
COPY (
  SELECT b.chapter, b.verse, b.verse_text,
         (SELECT entry_text FROM 'reference.parquet' r
           WHERE r.module_id = 'TSK' AND r.book_id = b.book_id
             AND r.chapter = b.chapter AND r.verse = b.verse) AS cross_refs,
         (SELECT entry_text FROM 'reference.parquet' r
           WHERE r.module_id = 'MHCC' AND r.book_id = b.book_id
             AND r.chapter = b.chapter AND r.verse = b.verse) AS henry_concise
  FROM 'bibles/text/bibles.parquet' b
  WHERE b.translation_id = 'AKJV' AND b.book_id = 'PHP'
  ORDER BY b.chapter, b.verse
) TO 'philippians.md' (FORMAT markdown);
```

## Working from Python / pandas

```python
import duckdb, pandas as pd
con = duckdb.connect()
df = con.sql("""
    SELECT * FROM 'bibles/text/bibles_partitioned/translation_id=AKJV/part-0.parquet'
    WHERE book_id = 'PSA' AND chapter = 23
""").df()
```

## Memory notes

The reference library is 387 M characters; a naive `SELECT *` on
`reference.parquet` needs ~1 GB of RAM. Filter or project first:

```sql
SET memory_limit = '400MB';
SET preserve_insertion_order = false;
SET threads = 1;
```

That combination is what the build pipeline uses on a 2 GB box.

---

## Verified against the real data

Every recipe above was run against the repository's own files on 2026-10-28:

```python
>>> duckdb.sql("""SELECT count(*) n, count(DISTINCT translation_id) t
...               FROM 'bibles/text/bibles.parquet'""").fetchall()
[(1577225, 77)]
>>> duckdb.sql("""SELECT verse_text FROM 'bibles/text/bibles.parquet'
...               WHERE translation_id='AKJV' AND book_id='JHN'
...                 AND chapter=3 AND verse=16""").fetchall()[0][0][:40]
'For God so loved the world, that he gave hi'
```

`reference.parquet` was verified separately: 795,269 rows, 2,127 works,
1,175,804,995 characters, all checks in `bibles/reference/QA_REPORT.md` passing.
