# Public-domain Bible database

A single, reproducible, queryable database of public-domain Bible material:
**the text** (97 translations: English, the source languages, and the historic
Bibles of continental Europe, verse-segmented) and **the reference works that explain it** (96 lexicons,
dictionaries, topical indexes and commentaries, entry by entry), all as plain
Apache Parquet with full provenance.

This repository *is* the workspace. Every artefact lives here; there is no
other copy that matters.

---

## What is in the database

| area | path | contents | size |
|---|---|---|---|
| Bible text | `bibles/text/` | 97 translations · **2,176,498 verses** · 10 columns | 70.3 MB combined + 97 partitions (release asset) |
| Reference works | `bibles/reference/` | **9,141 works** · **1,073,530 entries** · 2,369,741,291 characters | release assets (1.5 GB) |
| Tools | `tools/` | workspace client, schema catalog, query examples | — |
| Docs | `docs/` | cross-dataset guide, join recipes, licence policy | — |

**Totals: 3,249,734 rows of text, 9,218 works, ~2.42 billion characters, 43 languages,
covering all twenty requested subject areas.**

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
  WHERE b.translation_id = 'AKJV' AND b.book_id = 'JHN'
    AND b.chapter = 3 AND b.verse = 16
""").show()
```

More recipes: [`docs/QUERIES.md`](docs/QUERIES.md) · column reference:
[`docs/SCHEMA.md`](docs/SCHEMA.md) · the full list of works:
[`tools/catalog.py`](tools/catalog.py).

---

## The two datasets


### Editions

Two builds of the reference library are published from the same pipeline:

| edition | works | entries | characters | parquet |
|---|---|---|---|---|
| [`bible-reference-v5`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-reference-v5) — everything | 9,141 | 1,073,530 | 2,369,741,291 | 787.0 MB |
| [`bible-reference-v5-nocommentary`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-reference-v5-nocommentary) — commentaries removed | 3,795 | 687,596 | 1,198,048,181 | 385.6 MB |

Both share the schema and the join convention exactly. The narrower build removes
5,346 works: 162 SWORD commentary modules and 5,184 Sefaria works that Sefaria
itself files under a commentary category. Every removed work is listed with its
size and the rule that removed it in
`bibles/reference/data/commentaries_removed.csv`; see
[`bibles/reference/NO_COMMENTARY.md`](bibles/reference/NO_COMMENTARY.md).
Produce it yourself with `pipeline/exclude_category.py --what commentaries --apply`.

### `bibles/text/` — the verse corpus

97 public-domain or explicitly free translations, 2,176,498 verses, 51,153,830
words, 88 book codes, native versification preserved. Revision 8 added the 20
translations the project's Supabase mirror carried but this dataset did not —
Hebrew, Greek, Latin, German, French, Spanish, Italian, Dutch, Russian, Arabic,
Korean, Chinese, Malayalam and four more English texts, plus 1 Enoch as a new
book code. See `bibles/text/README.md#revision-8--the-supabase-additions`. One combined
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

9,141 works, 1,073,530 entries, 2,369,741,291 characters, in 43 languages:

| source | works | what it brings |
|---|---|---|
| Sefaria (Sefaria-Export) | 8,003 | Talmud, Mishnah, Midrash, Targums, halakhah, responsa, Kabbalah, liturgy — English and the Hebrew/Aramaic originals |
| Christian Classics Ethereal Library | 740 | patristics (ANF/NPNF), dogmatics, church history, sermons, devotion |
| First Thousand Years of Greek | 282 | Homer, Plato, Septuagint, Philo, Josephus, apostolic fathers (Greek) |
| CrossWire SWORD | 99 | lexicons, dictionaries, commentaries, topical indexes |
| STEPBible · Open Scriptures · OpenBible · Pleiades | 17 | interlinears, morphology, verse-level Strong's, cross-references, place names |

Coverage against the twenty requested areas is in
[`bibles/reference/COVERAGE.md`](bibles/reference/COVERAGE.md) — all twenty are
represented, four thinly, with the reason stated for each. Entry-level
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
Licences: Public Domain 6,289 · CC0 1,289 · CC BY 977 · CC BY-SA 585 · GPL 1. No non-commercial licence is present anywhere in the output.
Details: [`bibles/reference/README.md`](bibles/reference/README.md) — plus
`SOURCES.md`, `NOT_INCLUDED.md` (52 modules rejected, all on licence) and
`QA_REPORT.md`.

---

## The one join that makes this a database

```sql
-- every verse of the Authorised Version with Matthew Henry, Barnes and the Treasury of Scripture Knowledge
SELECT b.book_name, b.chapter, b.verse, b.verse_text,
       max(CASE WHEN c.module_id='MHC'   THEN c.entry_text END) AS henry,
       max(CASE WHEN c.module_id='Barnes' THEN c.entry_text END) AS barnes,
       max(CASE WHEN c.module_id='TSK'   THEN c.entry_text END) AS cross_refs
FROM 'bibles/text/bibles.parquet' b
LEFT JOIN 'reference.parquet' c
  ON c.book_id = b.book_id AND c.chapter = b.chapter AND c.verse = b.verse
WHERE b.translation_id = 'AKJV' AND b.book_id = 'ROM' AND b.chapter = 8
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

**<https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-reference-v5>**

| asset | size | contents |
|---|---|---|
| `reference.parquet` | 787.0 MB | all 9,141 works, 1,073,530 entries |
| `reference_partitioned.zip` | 762.3 MB | one Parquet file per work |
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
