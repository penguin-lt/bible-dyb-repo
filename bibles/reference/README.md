# Public-domain Bible reference library — lexicons, dictionaries, topical indexes, commentaries

Plain-text **Apache Parquet** of public-domain and explicitly free-licensed Bible
reference works: Hebrew/Greek lexicons, Bible dictionaries and encyclopedias,
topical indexes, cross-reference systems, and verse-by-verse commentaries.

Companion to the `public-domain-english-bibles` verse dataset and built to the same
conventions: one combined Parquet file, one Parquet file per work, a manifest table,
plain reading text with no markup, provenance for every row, and an independent QA
pass over the counts.

---

## Headline numbers

| | |
|---|---|
| Works | **9,141** (8,003 Sefaria · 740 CCEL · 282 First1KGreek · 99 SWORD · 10 STEPBible · 7 datasets) |
| Entries | **1,073,530** |
| Characters of text | **2,369,741,291** |
| One SQLite database per work (9,141 files) | **5.4 GB** (2.35 GB in two archives) |
| Languages | **43** — he, en, grc, la, de, fr, ar, syr, gez, vi, ru … |
| Licence | Public Domain 6,289 · CC0 1,289 · CC BY 977 · CC BY-SA 585 · GPL 1 |

By source category: Reference 1,577 works / 159,894 entries · Commentary 162 / 99,246 ·
Patristics 57 · Devotional 80 · Liturgy 65 · Theology 48 · Sermons 44 ·
Church History 43 · Lexicon 19 / 92,436 · Creeds & Confessions 13 ·
Dictionary 10 / 249,802 · Topical 9 / 42,300.

By **subject area** (the twenty requested), in `COVERAGE.md`: Systematic Theology
473 · Hermeneutics & Exegesis 336 · Mysticism 174 · Reformation 112 · Liturgy 112 ·
Rabbinic 1,075 · Patristics 68 · Church History 70 · Apocrypha 63 · Archaeology 44 ·
Lexical 33 · Creeds 23 · Cross-Reference 12 · Morphology 11 · Apologetics 10 ·
Sermons 78 · Background 7 · Interlinears 5 · Maps 5 · Textual Criticism 4.
Machine-readable counts are in `data/stats.json`.

The SQLite set is published as **release assets**:
<https://github.com/penguin-lt/bible-dyb-repo/releases/tag/reference-sqlite-rev5>
— `reference-sqlite-part1of2.zip` and `reference-sqlite-part2of2.zip` (both
needed; each unzips on its own), plus a SHA-256 manifest. One database per work,
each self-contained: its own entries, its own full manifest row, its own FTS5
index. Rebuild with `tools/reference_to_sqlite.py`.
A **commentary-free edition** is published alongside the full one:
[`bible-reference-v5-nocommentary`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-reference-v5-nocommentary)
— 3,795 works, 687,596 entries, 1,198,048,181 characters. See `NO_COMMENTARY.md`.

Revisions: `v1` 96 works (SWORD only) · `v2` 100 (added LSJ, BDB, STEPBible) · `v3` 2,127 (added CCEL, Sefaria, morphology, cross-references, Pleiades) ·
`v4` 10,156 (full Sefaria Hebrew/Aramaic, First1KGreek, STEPBible interlinears) ·
`v5` 9,141 — same sources, 1,015 exact duplicates removed and six data-quality bugs fixed (see QA_REPORT).

---

## Schema

every database shares one schema.
It is the entry-level analogue of the verse-level schema in the bibles dataset:

| column | type | meaning |
|---|---|---|
| `module_id` | string | short identifier — the SWORD module name, e.g. `Easton`, `MHC`, `StrongsHebrew` |
| `module_name` | string | human title, e.g. `Easton's Bible Dictionary` |
| `category` | string | `Lexicon`, `Dictionary`, `Commentary`, `Topical`, `Reference` |
| `entry_key` | string | the work's own headword or verse key, verbatim (`AARON`, `00026`, `Genesis 1:1`, `Psalms 23:0`) |
| `entry_order` | int32 | 0-based position of the entry inside the work, preserving the author's order |
| `book_id` | string | OSIS-style book code when `entry_key` is a scripture reference (`GEN`, `1CO`, `REV`), else null |
| `chapter` | int16 | chapter number when the key is a scripture reference, else null |
| `verse` | int16 | verse number when the key is a scripture reference, else null |
| `entry_text` | string | plain reading text — no markup, no Strong's tags, no notes apparatus, no pronunciation placeholders |
| `char_count` | int32 | length of `entry_text` in characters |

`book_id` / `chapter` / `verse` are parsed from the key, so commentaries and
verse-keyed dictionaries can be joined to any translation database directly
(`ATTACH 'CLARKE.sqlite3' AS clarke;` …):

```python
import sqlite3
kjv = sqlite3.connect("data/AKJV.sqlite3")
mhc = sqlite3.connect("data/MHC.sqlite3")      # Matthew Henry: its own file

kjv.execute("ATTACH DATABASE ? AS mhc", ("data/MHC.sqlite3",))
kjv.execute("""
  SELECT b.book_name, v.chapter, v.verse, v.text, e.entry_text
  FROM verse v JOIN book b USING(book_id)
  JOIN mhc.entry e ON e.book_id = v.book_id
                  AND e.chapter = v.chapter AND e.verse = v.verse
  WHERE v.book_id='JHN' AND v.chapter=3 AND v.verse=16""").fetchall()
```

210,522 entries carry a parsed scripture reference.

---

## Manifest

`modules.csv` has one row per work, and each database's `work` table holds that
work's own row verbatim, so the file is self-describing:

`module_id, module_name, category, sword_driver, language, license, copyright,
source_name, source_url, download_url, module_version, sword_version_date,
text_source, markup_source_type, about, entry_count, empty_entries_skipped,
duplicate_entries_dropped, repeated_keys_disambiguated, char_count,
scripture_linked_entries, retrieved`

## What is in scope

* **Lexicons and dictionaries** — Strong's Greek and Hebrew, Brown-Driver-Briggs
  glosses, Abbott-Smith, Dodson, Thayer-equivalents, Robinson/Packard morphology
  codes, Open Scriptures Hebrew Morphology, Mounce/MLStrong, Easton, Smith,
  International Standard Bible Encyclopedia, American Tract Society, Condensed
  Biblical Cyclopedia, Hitchcock's Bible Names, Nave's Topical Bible, Torrey,
  Thompson Chain, Scripture Alphabet of Animals, Webster 1806/1828/1913,
  Cawdrey's *A Table Alphabeticall* (1604), Bagster's *Daily Light*.
* **Commentaries** — Matthew Henry (Complete and Concise), Adam Clarke,
  Jamieson-Fausset-Brown, Barnes, Keil & Delitzsch, Calvin, Luther, Wesley,
  John Lightfoot, Burkitt, Catena Aurea, Scofield, Darby notes, The Fourfold
  Gospel, People's New Testament, Spurgeon's *Treasury of David*, Treasury of
  Scripture Knowledge, Glossa Ordinaria, Tischendorf's spurious passages,
  Rieger, Ansorg, Kanttekeningen.
* **Reference / devotional prose** — Calvin's *Institutes*, Aquinas' *Summa*,
  Josephus, Bunyan, à Kempis, Chesterton, Owen, Edwards, Ryle, Finney, Bounds,
  the Book of Concord, Westminster and Baptist confessions, 1 Enoch (English and
  Ge'ez), Jubilees, Didache.
* **Four works that are not SWORD modules**, ingested from open scholarly
  repositories: full **LSJ** (5,706 biblical Greek articles, 4.6 M characters)
  and **TBESG/TBESH** from STEPBible (CC BY 4.0), plus the full
  **Brown-Driver-Briggs** lexicon from Open Scriptures (public domain) — SWORD
  carries only BDB *glosses*, so this is new content.
* Non-English public-domain works are included and flagged by `language`
  (French Chrysostom/Augustine/Jerome, Dutch Kanttekeningen, Latin Glossa,
  German Rieger/Ansorg, Swedish, Vietnamese, Ge'ez).

## What is out of scope, and why

`modules_excluded.csv` lists every reference-class module that was inspected and
not ingested, with the reason. The rule is the same as the bibles dataset:
**public domain, or a licence that permits redistribution** (CC0, CC BY, CC BY-SA,
GPL). Excluded:

* modules whose `DistributionLicense` is "Permission granted to CrossWire",
  free-non-commercial, freely-distributable-with-restrictions, or blank;
* CC BY-NC-ND / CC BY-ND modules (no derivatives / non-commercial);
* modules that exist in the CrossWire catalogue but are not in the public
  `rawzip` mirror.

No OCR text is included: every work arrives as a born-digital SWORD module.

## Layout

```
public-domain-bible-reference/
├── README.md                     this file
├── SCHEMA.md                     column-by-column reference
├── SOURCES.md                    every source, licence finding and disposition
├── QA_REPORT.md                  verification results
├── NOT_INCLUDED.md               excluded modules and licence reasoning
├── stats.json                    machine-readable counts
├── modules.csv                   manifest (one row per work)
├── modules_excluded.csv          excluded modules with reasons
├── (the data itself: 9,141 SQLite databases, one per work — release assets on
│    reference-sqlite-rev5; this repository carries docs, manifests and pipeline)
└── pipeline/                     harvest + verification scripts
```

The two large data artefacts are published as release assets on the GitHub
repository holding this documentation, so the scripts and docs stay lightweight
and the dataset stays complete.

## Pipeline

```bash
python3 pipeline/sword_plan.py     # resolve the module set + licence decisions
python3 pipeline/harvest.py        # fetch, dump, normalise, write per-work Parquet
python3 pipeline/combine.py        # combined Parquet + manifests + stats.json
python3 pipeline/verify.py         # independent count/quality checks
```

Requires `libsword-utils` (for `mod2imp`), `unzip`, `curl`, `pyarrow`,
`zstandard`. The harvest is streaming: one module is in memory at a time and its
zip, unpacked module and dump are deleted immediately after the Parquet file is
written, so peak disk is roughly one module rather than the whole corpus.

## Provenance and licensing

Every work comes from the CrossWire Bible Society SWORD module archive
(`https://www.crosswire.org/ftpmirror/pub/sword/packages/rawzip/`), retrieved
2026-10-28, with version and licence taken from each module's own `.conf`.
Copyright and licence text for every work is carried in each file's `work` table
(and in `modules.csv`); read
the `license`, `copyright` and `about` columns before redistributing. Public
domain status is asserted by the module's distributor, not independently
re-verified here.
