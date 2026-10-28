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
| Works (SWORD modules) | **96** |
| Entries | **615,459** |
| Characters of text | **387,289,451** |
| Combined `reference.parquet` | **109.4 MB** |
| `reference_partitioned/` (96 files) | **106.3 MB** (105.8 MB zip) |
| Languages | en, fr, de, nl, la, grc, vi, sv, sl, gez, tlh, und |
| Licence | Public Domain 84 · CC BY-SA 7 · CC BY 4 · CC0 1 · GPL 1 |

By category: Commentary 30 works / 262,548 entries · Dictionary 10 / 249,802 ·
Lexicon 15 / 52,247 · Reference 32 / 8,562 · Topical 9 / 42,300.
Machine-readable counts are in `data/stats.json`.

The two large files are published as **release assets**:
<https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-reference-v1>
— `reference.parquet`, `reference_partitioned.zip`, `modules.parquet`.

---

## Schema

`reference.parquet` and every file in `reference_partitioned/` share one schema.
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
verse-keyed dictionaries can be joined to `bibles.parquet` directly:

```python
import duckdb
duckdb.sql("""
  SELECT b.verse_text, c.entry_text
  FROM 'bibles.parquet' b
  JOIN 'reference.parquet' c
    ON c.module_id = 'MHC' AND c.book_id = b.book_id
   AND c.chapter = b.chapter AND c.verse = b.verse
  WHERE b.translation_id = 'KJV' AND b.book_id = 'JHN' AND b.chapter = 3 AND b.verse = 16
""")
```

210,522 entries carry a parsed scripture reference.

---

## Manifest

`modules.parquet` (and the identical `modules.csv`) has one row per work:

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
├── modules.parquet / modules.csv manifest
├── modules_excluded.csv          excluded modules with reasons
├── reference.parquet             combined (110 MB — delivered via release asset)
├── reference_partitioned/        one file per work (107 MB — delivered as a zip)
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
Copyright and licence text for every work is carried in `modules.parquet`; read
the `license`, `copyright` and `about` columns before redistributing. Public
domain status is asserted by the module's distributor, not independently
re-verified here.
