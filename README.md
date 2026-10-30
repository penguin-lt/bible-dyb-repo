# Public-domain Bible database

A single, reproducible, queryable database of public-domain Bible material:
**the text** (97 translations: English, the source languages, and the historic
Bibles of continental Europe, verse-segmented) and **the reference works that explain it** (96 lexicons,
dictionaries, topical indexes and commentaries, entry by entry), all as
self-contained SQLite databases with full provenance — one file per translation,
one file per reference work.

This repository *is* the workspace. Every artefact lives here; there is no
other copy that matters.

---

## What is in the database

| area | path | contents | size |
|---|---|---|---|
| Bible text | `bibles/text/` | 97 translations · **2,176,498 verses** · 10 columns | 97 databases, 605 MB ([release asset](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bibles-sqlite-rev9)) |
| Reference works | `bibles/reference/` | **9,141 works** · **1,073,530 entries** · 2,369,741,291 characters | 9,141 databases, 5.4 GB, two archives ([release asset](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/reference-sqlite-rev5)) |
| App | `app/` | free offline reader: verses, passage guide, lexicon, interlinear, search | SQLite databases on the [bible-search-rev1](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-search-rev1) release |
| Curated subset | `bibles/core/` | English Bibles + critical editions + lexicons: **85 translations · 25 lexical works** ([release asset](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bibles-lexicons-core)) | 110 files, 275 MB |
| Tools | `tools/` | workspace client, schema catalog, query examples | — |
| Docs | `docs/` | cross-dataset guide, join recipes, licence policy | — |

**Totals: 3,249,734 rows of text, 9,218 works, ~2.42 billion characters, 43 languages,
covering all twenty requested subject areas.**

Two datasets, one schema philosophy: **one SQLite file per thing** — a translation
or a reference work — each self-contained, each carrying its own manifest row with
licence and provenance, plain reading text with markup stripped, and an FTS5 index
over its own text. Concatenate all 9,141 with `ATTACH` when you want a whole-corpus
scan; otherwise you open exactly the one file you need and nothing else.

---

## Quick start

```bash
git clone https://github.com/penguin-lt/bible-dyb-repo.git bible-db
cd bible-db

# fetch the two SQLite sets (release assets — combined they are 315 MB + 2.35 GB)
curl -L -O https://github.com/penguin-lt/bible-dyb-repo/releases/download/bibles-sqlite-rev9/bibles-sqlite-rev9.zip
curl -L -O https://github.com/penguin-lt/bible-dyb-repo/releases/download/reference-sqlite-rev5/reference-sqlite-part1of2.zip
curl -L -O https://github.com/penguin-lt/bible-dyb-repo/releases/download/reference-sqlite-rev5/reference-sqlite-part2of2.zip
unzip -q '*.zip' -d data/
```

```python
import sqlite3

# one translation, no setup
db = sqlite3.connect("data/AKJV.sqlite3")
db.execute("SELECT verse_text FROM verse WHERE book_id='JHN' AND chapter=3 AND verse=16").fetchone()

# what does Matthew Henry say about it? open that work's file, nothing else
mh = sqlite3.connect("data/MHC.sqlite3")
mh.execute("""SELECT entry_text FROM entry
              WHERE book_id='JHN' AND chapter=3 AND verse=16""").fetchall()
```

```sql
-- or attach just the two files and join them in one query
ATTACH 'data/AKJV.sqlite3' AS kjv;
ATTACH 'data/MHC.sqlite3'  AS mhc;
SELECT kjv.verse.verse_text, mhc.entry.entry_text
FROM kjv.verse JOIN mhc.entry
  ON mhc.entry.book_id = kjv.verse.book_id
 AND mhc.entry.chapter  = kjv.verse.chapter
 AND mhc.entry.verse    = kjv.verse.verse
WHERE kjv.verse.book_id='JHN' AND kjv.verse.chapter=3 AND kjv.verse.verse=16;
```

---

## The app

`app/` turns the database into something you can actually read. One Python file,
standard library only, no server and no account:

```
python3 app/app.py --db search.db.zst
```

Read any chapter in 97 translations, click a verse for its commentaries,
cross-references, interlinear and lexicon, search verses or the whole reference
library, and browse all 9,141 works by topic — with the licence of every work
shown in the panel that quotes it.

The databases it needs are release assets, not repository files: `search.db.zst`
(312 MB, everything except full-library search) and `works.db.zst` split into
three parts (1.7 GB, the whole corpus). `app/make_release.py` produces them,
`app/build_searchdb.py` rebuilds them from the Parquet in about six minutes, and
[`app/README.md`](app/README.md) has the details.

## The two datasets


### Editions

Two builds of the reference library are published from the same pipeline:

| edition | works | entries | characters | SQLite |
|---|---|---|---|---|
| [`reference-sqlite-rev5`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/reference-sqlite-rev5) — everything | 9,141 | 1,073,530 | 2,369,741,291 | 9,141 files, 5.4 GB |
| [`bible-reference-v5-nocommentary`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-reference-v5-nocommentary) — commentaries removed | 3,795 | 687,596 | 1,198,048,181 | subset of the above; every file carries its `status` |

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
book code. See `bibles/text/README.md#revision-8--the-supabase-additions`. The dataset is published as 97 self-contained SQLite databases, one per translation,
with no duplication between them: [`bibles-sqlite-rev9`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bibles-sqlite-rev9),
rebuilt by `tools/parquet_to_sqlite.py` in about 20 seconds.

| column | type |
|---|---|
| `translation_id`, `book_id`, `book_name` | string |
| `book_order`, `book_sort`, `chapter`, `verse`, `verse_end` | int16 |
| `Testament` | string (`OT` / `NT` / `DC`) |
| `verse_text` | string |

Licences: 48 expired-copyright, 12 dedicated to the public domain, 5 CC0,
10 CC BY-SA, 2 CC BY. Provenance per translation in `translations.csv` and each file's `translation` table
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

210,522 entries carry a parsed scripture reference and join straight to any
translation database on `(book_id, chapter, verse)`.
Licences: Public Domain 6,289 · CC0 1,289 · CC BY 977 · CC BY-SA 585 · GPL 1. No non-commercial licence is present anywhere in the output.
Details: [`bibles/reference/README.md`](bibles/reference/README.md) — plus
`SOURCES.md`, `NOT_INCLUDED.md` (52 modules rejected, all on licence) and
`QA_REPORT.md`.

---

## The one join that makes this a database

```sql
-- every verse of Romans 8 in the Authorised Version, with Matthew Henry,
-- Barnes and the Treasury of Scripture Knowledge alongside it: three files
ATTACH 'data/AKJV.sqlite3'   AS kjv;
ATTACH 'data/MHC.sqlite3'    AS mhc;
ATTACH 'data/Barnes.sqlite3' AS barnes;
ATTACH 'data/TSK.sqlite3'    AS tsk;

SELECT v.book_name, v.chapter, v.verse, v.text,
       (SELECT entry_text FROM mhc.entry    e WHERE e.book_id=v.book_id AND e.chapter=v.chapter AND e.verse=v.verse) AS henry,
       (SELECT entry_text FROM barnes.entry e WHERE e.book_id=v.book_id AND e.chapter=v.chapter AND e.verse=v.verse) AS barnes,
       (SELECT entry_text FROM tsk.entry    e WHERE e.book_id=v.book_id AND e.chapter=v.chapter AND e.verse=v.verse) AS cross_refs
FROM (SELECT b.book_name, v.chapter, v.verse, v.text, v.book_id
      FROM kjv.verse v JOIN kjv.book b USING(book_id)) v
WHERE v.book_id='ROM' AND v.chapter=8 ORDER BY v.verse;
```

Every file is a plain SQLite database, so `ATTACH`, `sqlite3`, pandas, DuckDB
(`INSTALL sqlite; LOAD sqlite;`), DB Browser and the `sqlite3` CLI all read it
without conversion.

---

## Publishing and provenance

Everything is fetched from open, verifiable sources and labelled per row:
CrossWire SWORD modules (reference works), scrollmapper/bible_databases, DBS,
studybible.info, Wikisource and bible.com (text). Every manifest row names the
exact URL, retrieval date, licence and version. Public-domain status is the
distributor's assertion, carried verbatim; nothing was OCR'd.

The data is published as release assets — 9,238 SQLite databases, one per
translation and one per reference work — while its docs, manifests and pipeline
stay in the repository. **No Parquet file remains**: it was the intermediate
format, and every column of it now lives in the SQLite files (verified row for
row, see `bibles/text/README.md` and `bibles/reference/README.md`).

| asset | size | contents |
|---|---|---|
| [`bibles-sqlite-rev9`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bibles-sqlite-rev9) → `bibles-sqlite-rev9.zip` | 292 MB | 97 translation databases |
| [`reference-sqlite-rev5`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/reference-sqlite-rev5) → `reference-sqlite-part1of2.zip` + `-part2of2.zip` | 1.25 + 1.10 GB | 9,141 work databases (both parts needed; each unzips on its own) |
| SHA-256 manifests on both releases | — | one checksum per database |

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
each database's `translation` / `work` row before redistributing, and keep the
attribution for the CC BY / CC BY-SA works.
