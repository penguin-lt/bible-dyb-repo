# Public-domain Bible database

A single, reproducible, queryable database of public-domain Bible material:
**the text** (77 translations in the original languages of the English tradition,
verse-segmented) and **the reference works that explain it** (96 lexicons,
dictionaries, topical indexes and commentaries, entry by entry), all as plain
Apache Parquet with full provenance.

This repository *is* the workspace. Every artefact lives here; there is no
other copy that matters.

---

## What is in the database

| area | path | contents | size |
|---|---|---|---|
| Bible text | `bibles/text/` | 77 translations · **1,577,225 verses** · 10 columns | 28.2 MB combined + 55.1 MB partitioned |
| Reference works | `bibles/reference/` | 100 works · **655,648 entries** · 398,036,788 characters | release assets (222 MB) |
| Tools | `tools/` | workspace client, schema catalog, query examples | — |
| Docs | `docs/` | cross-dataset guide, join recipes, licence policy | — |

**Totals: 2,232,873 rows of text, 177 works, ~438 million characters.**

Two datasets, one schema philosophy: one combined Parquet file for whole-corpus
scans, one Parquet file per translation/work for cheap filtering, a manifest table
with licence and provenance for every row, plain reading text with markup
stripped, and an independent verification pass over the counts.

---

## Quick start

```bash
git clone https://github.com/penguin-lt/bible-dyb-repo.git bible-db
cd bible-db

# the verse corpus is small enough to live in git
python3 -c "import duckdb; print(duckdb.sql('''
  SELECT translation_id, count(*) v FROM 'bibles/text/bibles.parquet'
  GROUP BY 1 ORDER BY 2 DESC LIMIT 5'''))"

# the reference library is a release asset — fetch it once
curl -L -O https://github.com/penguin-lt/bible-dyb-repo/releases/download/bible-reference-v1/reference.parquet
```

```python
import duckdb
# what does Matthew Henry say about John 3:16, next to the verse itself?
duckdb.sql("""
  SELECT b.verse_text AS verse, c.entry_text AS commentary
  FROM 'bibles/text/bibles.parquet' b
  JOIN 'reference.parquet' c
    ON c.module_id = 'MHC' AND c.book_id = b.book_id
   AND c.chapter = b.chapter AND c.verse = b.verse
  WHERE b.translation_id = 'KJV' AND b.book_id = 'JHN'
    AND b.chapter = 3 AND b.verse = 16
""").show()
```

More recipes: [`docs/QUERIES.md`](docs/QUERIES.md) · column reference:
[`docs/SCHEMA.md`](docs/SCHEMA.md) · the full list of works:
[`tools/catalog.py`](tools/catalog.py).

---

## The two datasets

### `bibles/text/` — the verse corpus

77 public-domain or explicitly free translations, 1,577,225 verses, 39,909,848
words, 87 book codes, native versification preserved. One combined
`bibles.parquet` plus `bibles_partitioned/translation_id=<ID>/part-0.parquet`.

| column | type |
|---|---|
| `translation_id`, `book_id`, `book_name` | string |
| `book_order`, `book_sort`, `chapter`, `verse`, `verse_end` | int16 |
| `Testament` | string (`OT` / `NT` / `DC`) |
| `verse_text` | string |

Licences: 48 expired-copyright, 12 dedicated to the public domain, 5 CC0,
10 CC BY-SA, 2 CC BY. Provenance per translation in `translations.parquet`
(including `source_url`, `text_sha256`, `word_count`, `notes`).
Details: [`bibles/text/README.md`](bibles/text/README.md).

### `bibles/reference/` — the reference library

100 works, 655,648 entries, 398,036,788 characters, in 12 languages. 96 are
CrossWire SWORD modules; four are ingested from open scholarly repositories:
full LSJ and STEPBible TBESG/TBESH (CC BY 4.0), and full Brown-Driver-Briggs
(public domain). Entry-level
Parquet: one row per headword, verse or section, keyed by the work's own key.

| column | type |
|---|---|
| `module_id`, `module_name`, `category`, `entry_key` | string |
| `entry_order` | int32 |
| `book_id` | string (null for alphabetic headwords) |
| `chapter`, `verse` | int16 |
| `entry_text`, `char_count` | string / int32 |

210,522 entries carry a parsed scripture reference and join straight to
`bibles/text/bibles.parquet` on `(book_id, chapter, verse)`.
Licences: Public Domain 85, CC BY-SA 7, CC BY 6, CC0 1, GPL 1.
Details: [`bibles/reference/README.md`](bibles/reference/README.md) — plus
`SOURCES.md`, `NOT_INCLUDED.md` (52 modules rejected, all on licence) and
`QA_REPORT.md`.

---

## The one join that makes this a database

```sql
-- every verse of the KJV with Matthew Henry, Barnes and the Treasury of Scripture Knowledge
SELECT b.book_name, b.chapter, b.verse, b.verse_text,
       max(CASE WHEN c.module_id='MHC'   THEN c.entry_text END) AS henry,
       max(CASE WHEN c.module_id='Barnes' THEN c.entry_text END) AS barnes,
       max(CASE WHEN c.module_id='TSK'   THEN c.entry_text END) AS cross_refs
FROM 'bibles/text/bibles.parquet' b
LEFT JOIN 'reference.parquet' c
  ON c.book_id = b.book_id AND c.chapter = b.chapter AND c.verse = b.verse
WHERE b.translation_id = 'KJV' AND b.book_id = 'ROM' AND b.chapter = 8
GROUP BY ALL ORDER BY b.verse;
```

---

## Publishing and provenance

Everything is fetched from open, verifiable sources and labelled per row:
CrossWire SWORD modules (reference works), scrollmapper/bible_databases, DBS,
studybible.info, Wikisource and bible.com (text). Every manifest row names the
exact URL, retrieval date, licence and version. Public-domain status is the
distributor's assertion, carried verbatim; nothing was OCR'd.

The reference library is too large for a git checkout alongside the verse data,
so it is published as release assets while its docs, manifests and pipeline stay
in the repository:

**<https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-reference-v2>**

| asset | size | contents |
|---|---|---|
| `reference.parquet` | 112.7 MB | all 100 works, 655,648 entries |
| `reference_partitioned.zip` | 109.0 MB | one Parquet file per work |
| `modules.parquet` | 30 KB | manifest (also in `bibles/reference/data/`) |

## Working on it

The repository is the source of truth, and `tools/workspace.py` treats it that
way from any machine:

```bash
export GH_TOKEN=...                       # a token with `repo` scope
python3 tools/workspace.py stat           # what is in the database, by area
python3 tools/workspace.py ls bibles/text # browse
python3 tools/workspace.py sync bibles/reference/data ./data   # pull a subtree
python3 tools/workspace.py put ./new_manifest.csv bibles/reference/data/modules.csv
```

Rebuilds are scripted per dataset — `bibles/text/pipeline/` and
`bibles/reference/pipeline/` — and each writes its own Parquet, manifest, stats
and QA pass. See [`docs/REPRODUCE.md`](docs/REPRODUCE.md).

## Licence

The database structure, documentation and pipeline code here are free to use.
The *content* is public domain or explicitly free-licensed per work: read
`translations.parquet` and `modules.parquet` before redistributing, and keep the
attribution for the CC BY / CC BY-SA works.
