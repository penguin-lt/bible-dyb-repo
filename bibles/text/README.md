# Public Domain & Freely-Licensed English Bibles — Parquet Dataset

**77 English Bible translations · 1,577,225 verses · 39.9 million words · one Parquet schema**

Every public-domain or freely-licensed English Bible translation for which a reliable,
verse-segmented machine-readable text could be found, normalised to a single structure.
Coverage runs from the Wycliffe Bible (c. 1389) and Tyndale (1526–1534) through the historic
printed Bibles (Coverdale, Matthew's, the Great Bible, Geneva 1560/1599, Bishops', Douay-Rheims–Challoner,
the KJV in its 1611 first edition and the standard 1769 text) to modern public-domain releases
(WEB, Berean, OEB, LSV…), including
Catholic and Orthodox canons with the deuterocanon, Septuagint translations, NT-only and
OT-only works, and partial translations.

| | Count |
|---|---:|
| Translations | 77 |
| Verse rows | 1,577,225 (OT 994,856 · NT 525,473 · Deuterocanon 56,896) |
| Books covered | 87 book codes in use (canonical list: 88, incl. Odes — currently in no translation) |
| Words | 39,909,848 |
| Strictly public domain / CC0 | 65 translations (48 copyright-expired, 12 dedicated, 5 CC0) |
| Other free licences (flagged per translation) | 12 (2× CC BY 4.0, 10× CC BY-SA 4.0) |
| Scopes | 28 complete Bibles, 7 complete with deuterocanon, 26 New Testaments, 4 NT with OT portions, 2 Tanakh/OT-only, 1 Septuagint OT, 1 Targum Pentateuch, 5 partial/portions, 1 single book, 2 OT portions (Isaiah) |

## Files

| File | Contents |
|---|---|
| **`bibles.parquet`** (28.2 MB) | All 76 translations in one file, sorted by canonical book order → chapter → verse → translation (same-verse rows across translations sit together, which compresses extremely well and makes cross-translation comparison a sequential scan). |
| **`bibles_partitioned/`** (55.0 MB, 76 files) | Same rows, Hive-partitioned by `translation_id` (`translation_id=KJVA/part-0.parquet`, …). Read it as a dataset and your engine will prune to one small file per translation. |
| `translations.parquet` / `.csv` | One row per translation: name, year, edition, scope, dialect, licence + evidence URL, source + retrieval date, verse/book/chapter/word counts, per-testament counts, and a SHA-256 of the cleaned text. |
| `books.parquet` / `.csv` | The canonical book list: USFM `book_id`, standard name, testament (`OT`/`NT`/`DC`), and `book_sort`. |
| `QA_REPORT.md` | Build QA: per-translation verse/book/chapter counts, cat-count differences vs source catalogues, gap analysis, and cross-edition similarity checks. |
| `NOT_INCLUDED.md` | Significant translations that were excluded, and why (licence restrictions, or no trustworthy verse-parseable text exists). |
> Workspace size note: the binary sources in `pipeline/sources/` are stored gzipped
> (`*.gz` + `COMPRESSED.json`); run `python3 pipeline/sources/unpack.py` before a rebuild.
> The scraped studybible.info pages and the catalogue pages live in
> `pipeline/studybible_raw.json.gz`, `pipeline/studybible_probe.json.gz` and
> `pipeline/research_wikidot_text.json.gz`, and the PDFs used for the scan-quality
> experiment were deleted (see `pipeline/experiments/MANIFEST.md` for the URLs).

> Note on reproducibility: the original v1 collection pipeline (parsers for USFM, SWORD, MySword SQLite, JSON/CSV/TSV sources) is not bundled with this copy, but every translation's provenance (`source_url`, licence and `text_sha256`) is recorded in `translations.parquet`/`.csv`, so each text can be re-fetched from its origin and verified. The bundled revision-2 script (`pipeline/rebuild_dataset.py`) deduplicated the set and added the 1611 KJV from `pipeline/sources/kjv1611.ont`; the revision-3 script (`pipeline/add_data_csv_additions_rev3.py`) added ABU1865, Worrell and RIVERSIDE from the three TheWord module files kept beside it in `pipeline/sources/`; the revision-4 script (`pipeline/add_mybible_additions_rev4.py`) added MOFFATT and PANIN from the two MyBible modules there (`NTM.SQLite3`, `NumNT.SQLite3`); the revision-5 script (`pipeline/add_wikidot_additions_rev5.py`) added WHISTON after reconciling the whole Internet Bible Catalog (bibles.wikidot.com); the revision-6 script (`pipeline/add_studybible_additions_rev6.py`, plus `pipeline/studybible_fetch.py` for the scrape and `pipeline/fix_rev6.py` for one corrected Ottley verse) added MACE, SAWYER and OTTLEY from studybible.info (see `STUDYBIBLE_SOURCES.md`); the revision-7 script (`pipeline/add_bibliatodo_addition_rev7.py`, with `pipeline/biblecom_fetch.py`) added TEG, John Jones's 1830 Isaiah, after sweeping the English catalogue of bibliatodo.com and the Digital Bible Society inventory (see `BIBLIATODO_SOURCES.md` and `DBS_SOURCES.md`).

## Schema (identical in both layouts)

| Column | Type | Meaning |
|---|---|---|
| `translation_id` | string | Translation code; join key to `translations.parquet` (also the partition column in the partitioned layout). |
| `book_id` | string | USFM book code (`GEN`, `PSA`, `MAT`, `TOB`, …; `DAG` = Greek Daniel included as its own book in Septuagint-based texts). |
| `book_name` | string | Book name as the source prints it (e.g. *"The Acts of the Apostles"*, *"Psalms [Praise]"*), else the standard name. |
| `book_order` | int16 | Position of the book within that translation's own ordering. |
| `book_sort` | int16 | Fixed ecumenical canonical order (Protestant OT → deuterocanon → NT → Laodiceans), identical for every translation — sort/group by this to compare translations. |
| `Testament` | string | `OT`, `NT`, or `DC` (deuterocanonical). |
| `chapter` | int16 | Chapter number in the translation's own versification. |
| `verse` | int16 | Verse number (`0` = psalm superscription/introduction where the source marks one). |
| `verse_end` | int16 | Last verse covered by this row; `> verse` when the source prints one text block for a range (841 such rows). |
| `verse_text` | string | Clean reading text only (see cleaning below). Never null or empty. |

**Versification is native**: each translation keeps its own chapter/verse numbering
(e.g. Douay-Rheims follows Vulgate psalm numbering; Septuagint texts follow Greek
numbering). A row exists **only where the source prints text** — verses omitted by
critical-text translations (e.g. Matthew 17:21 in the ASV) simply have no row.

## Text cleaning

`verse_text` is plain reading text. The pipeline strips, from every source format
(USFM, SWORD modules, MySword SQLite, JSON/CSV/TSV): Strong's numbers and morphology,
footnote and cross-reference markers, section headings embedded in verse text, word-level
alignment markup, and all formatting tags. Italics/supplied-word tags lose their markers
but keep the words. Punctuation split by word-level markup is re-joined to its word,
whitespace is normalised, text is Unicode-NFC. Original spellings are **not** modernised
(historic Bibles keep their orthography). One deliberate retention: unfoldingWord ULT's
`{braces}` around supplied words are part of that translation's printed convention and are kept.

## Licence notes

The per-translation `license`, `license_type` and `license_url` columns in
`translations.parquet` are authoritative — check them before redistributing any
single translation. Two jurisdiction caveats to know:

- **KJV family** — public domain in most of the world, but in the United Kingdom the
  Authorized Version remains under perpetual Crown prerogative (letters patent).
- **BBE** (Bible in Basic English) — public domain in the US (no renewal) but copyrighted
  in life+70 jurisdictions until 2039.

CC BY-SA translations (FBV, LSV, ULT/UST, T4T, F35, PEV, OURB, E2T, modern Wycliffe edition)
require share-alike for adaptations; converting format/schema, as done here, is not an
adaptation of the text itself, but satisfy yourself for your use case. This dataset is
offered without warranty; this file is not legal advice.

## Usage examples

**DuckDB — John 1:1 in every translation that has it:**
```sql
SELECT translation_id, verse_text FROM 'bibles.parquet'
WHERE book_id='JHN' AND chapter=1 AND verse=1 ORDER BY translation_id;  -- 67 rows
```

**DuckDB — one translation from the partitioned layout (reads one file):**
```sql
SELECT * FROM read_parquet('bibles_partitioned/**/*.parquet', hive_partitioning=true)
WHERE translation_id='Tyndale' AND book_id='JON';
```

**Python / PyArrow:**
```python
import pyarrow.dataset as ds
bibles = ds.dataset("bibles_partitioned", partitioning="hive")
psalm23 = bibles.to_table(filter=(ds.field("book_id")=="PSA") & (ds.field("chapter")==23))
```

**Pandas (single translation fits easily):**
```python
import pandas as pd
kjv = pd.read_parquet("bibles_partitioned/translation_id=KJVA/part-0.parquet")
```

## Known source quirks (faithful to the sources, documented not "fixed")

- **Brenton / LXXUP** — the eBible.org source prints Greek *Esdras B* (Ezra+Nehemiah) both
  as one 23-chapter book (`EZR`) and re-split (`NEH` 1–13), so Nehemiah's text appears
  twice under two chapter numberings.
- **TNT vs Tyndale** — two independent transcriptions of Tyndale's 1534 NT with different
  abbreviation-expansion conventions (þe → “the” vs “ye”); only ~59% of verses are
  byte-identical after trivial normalisation. `Tyndale` additionally has the Pentateuch and Jonah.
- **JST** has no Song of Solomon (Smith left it out of the Inspired Version).
- **GREAT** (Great Bible) source module leaves 7 verse slots blank; blank source verses
  produce no rows.
- **OURB** is a work-in-progress: Torah, Psalms (+Psalm 151), Proverbs, Isaiah,
  1 Maccabees and the four Gospels. **THOMSON** is the 11 books completed so far of a
  modern transcription. **E2T** is a single book (Jonah).
- **WYCPORTIONS** was dropped at build time: it is a 99.5%-identical subset of `WYCLIFFE` (see `QA_REPORT.md`).
- **KJV1611** is the true first edition in original spelling ("Heauen", "Iesus", u/v as
  printed; long s normalised). It is textually a different edition from `KJVA` (the
  1769-family text): only ~4% of sampled verses are word-identical. The 1611 printing
  also contained the Apocrypha, but the source module is 66-book, so for the KJV
  deuterocanon see `KJVA`.
- **Deduplication (revision 2, 2026-10-28)** — 15 spelling/repackage variants were
  removed in favour of the fullest kept equivalent (e.g. the 8-member WEB family → `WEB`
  + `WMB`; `KJV`/`KJVPCE`/`KJVCPB` → `KJVA`, which contains their Protestant-canon text
  plus the Apocrypha, and `KJV1611` added). The full drop list with measured similarity
  is in `QA_REPORT.md` and `NOT_INCLUDED.md`.
- **Revision 7 addition (`TEG`)** — John Jones of Bala ("Ioan Tegid"), *Isaiah*,
  Oxford 1830 / 2nd ed. 1842. Isaiah only (66 chapters, 1,292 verses). The British &
  Foreign Bible Society digital edition, fetched from its verse-segmented HTML at
  bible.com (bibliatodo.com lists it but is behind a Cloudflare challenge). His
  Hebrew poetry line breaks are joined with single spaces.
- **Revision 6 additions (`MACE`, `SAWYER`, `OTTLEY`)** — scraped verse by verse from
  studybible.info, no OCR involved. Mace's own book order (Pastoral Epistles last) and
  Sawyer's chronological section numbers are mapped onto standard chapter/verse, so
  Sawyer's verses keep his printed section markers, e.g. `(1:1) IN the beginning…`.
  `OTTLEY` is Isaiah only, from the Septuagint (Greek chapter and verse numbering), and is
  distinct from Brenton (0.7 % word-identical verses). studybible.info's own Isaiah 24:20
  read "for her transgression 15 strong upon her" — the `15` is its slip for `is` — and is
  corrected. **THOMSON** is still the 11-book transcription, not the full Bible: the
  studybible library has all 66 books (30,974 verses) of it, so the 56 missing books
  (27,395 verses) are recorded in `pipeline/stats_v6.json` →
  `thomson_completeness.available_not_ingested` for a later revision.
- **Revision 5 addition (`WHISTON`)** — Whiston's 1745 Primitive New Testament comes from a
  MySword/theWord module in the same one-line-per-KJV-verse-slot layout as the revision-3
  modules. Whiston prints bracketed supplied words (`"[be]"`, `"[day]"`) and they are kept;
  the module's `<CL>` tag is only a paragraph break inside a verse, so it is removed and the
  words are retained. The text keeps Whiston's own eclectic readings (short 1 John 5:7,
  "the evil one" in Matthew 6:13) and is the most archaic-English NT in the set.
- **Revision 4 additions (`MOFFATT`, `PANIN`)** — both come from MyBible modules and keep
  this dataset's plain-text rule, with three documented editorial decisions. MOFFATT's
  module prints Moffatt's own bracketed relocation instructions ("[Relocated to follow
  vs 20]"); those instructions are dropped, while bracketed *translation text*
  ("[the Son of God]") is kept, and 17 KJV slots that hold only a punctuation dash in the
  module yield no row. PANIN marks the Greek article by placing a colon before the English
  word (a typographic device, so the colons are removed with no word altered, added or
  reordered), and its module files Matthew 23:13's text under verse 14 — corrected back to
  23:13, leaving 23:14 with no row — and merges Hebrews 1:14 into 1:13, so HEB 1:14 has no
  row. Nineteen slots marked "Omitted"/blank in PANIN yield no row.
- **Revision 3 additions (`ABU1865`, `Worrell`, `RIVERSIDE`)** — these three NTs came
  from TheWord modules whose 7,957 lines occupy KJV verse slots. Slots holding only a
  module placeholder (`TEXT OMITTED` / `OMITTED TEXT`) or, in ABU, a bracketed textual
  note yield no row; bracketed *translation text* is kept. RIVERSIDE was printed in
  paragraphs without verse numbers, so its segmentation is the module maker's; its
  printed parenthetical matter is preserved in parentheses.

## Sources

Texts were retrieved 2026-10-27 from eBible.org (USFM), CrossWire (SWORD modules, plus
the scrollmapper JSON/CSV mirror of the same modules), MySword module downloads, Door43
(unfoldingWord), and public GitHub transcription projects; `KJV1611` was added 2026-10-28
from a theWord module (theword-modules.com). Revision 5 (2026-10-28) reconciled every entry of the Internet Bible Catalog (bibles.wikidot.com/indexpage) and added Whiston's Primitive NT (1745) from a MySword/theWord module. Revision 4 (2026-10-28) drew on the
MyBible (ph4.org) English module catalogue, adding Moffatt's NT (1913) and Panin's Numeric
NT (1914) — both modules downloaded from ph4.org and screened for licence, coverage and
duplicate similarity before inclusion. In revision 3 (2026-10-28) the user's
250-title candidate list was reconciled against this dataset; the three titles on it
that met every rule — American Bible Union NT (1865), Worrell NT (1904) and Riverside NT
(1923) — were added from TheWord modules on the same site (ABU cross-checked against
Project Gutenberg #26361). `translations.csv` records the exact `source_url` per
translation. Full QA methodology and per-translation counts are in `QA_REPORT.md`;
exclusions are in `NOT_INCLUDED.md`.

## Translations included

| translation_id | Translation | First published | Books | Verses | Licence type |
|---|---|---|---|---|---|
| `ABU1865` | American Bible Union New Testament | 1865 | 27 | 7,953 | public_domain_expired |
| `ACV` | A Conservative Version | — | 66 | 31,102 | public_domain_dedicated |
| `AKJV` | American King James Version | 1999 | 66 | 31,102 | public_domain_dedicated |
| `Anderson` | Anderson's New Testament | 1864 | 27 | 7,946 | public_domain_expired |
| `ASV` | American Standard Version | 1901 | 66 | 31,086 | public_domain_expired |
| `ASVBT` | American Standard Version Byzantine Text | 1901 | 84 | 37,761 | public_domain_dedicated |
| `BBE` | Bible in Basic English | 1949 | 66 | 31,102 | public_domain_expired |
| `BISHOPS` | Bishops' Bible | 1568 | 66 | 31,102 | public_domain_expired |
| `BLB` | Berean Literal Bible | 2016 | 27 | 7,941 | cc0 |
| `Brenton` | Brenton Septuagint Translation | 1844 | 53 | 28,690 | public_domain_expired |
| `BSB` | Berean Standard Bible | 2016 | 66 | 31,086 | cc0 |
| `Coverdale` | Coverdale Bible | 1535 | 66 | 31,089 | public_domain_expired |
| `CPDV` | Catholic Public Domain Version | 2009 | 73 | 35,812 | public_domain_dedicated |
| `DBY` | Darby Translation | 1890 | 66 | 31,099 | public_domain_expired |
| `DIAGLOTT` | The Emphatic Diaglott (Benjamin Wilson Emphatic Version) | 1864 | 27 | 7,910 | public_domain_expired |
| `DRA` | Douay-Rheims Bible (American Edition) | 1899 | 73 | 35,811 | public_domain_expired |
| `E2T` | Easy to Translate English Jonah | 2025 | 1 | 47 | cc_by_sa_4.0 |
| `Etheridge` | Etheridge's Peshitta New Testament | 1849 | 27 | 7,940 | public_domain_expired |
| `F35` | Family 35 New Testament (Wilbur Pickering) | 2016 | 27 | 7,953 | cc_by_sa_4.0 |
| `FBV` | Free Bible Version | 2018 | 66 | 31,087 | cc_by_sa_4.0 |
| `GHT` | Garth's Hyper-literal Translation | — | 27 | 7,956 | public_domain_dedicated |
| `GNV1560` | Geneva Bible (1560) | 1560 | 66 | 31,102 | public_domain_expired |
| `GNV1599` | Geneva Bible (1599) | 1599 | 66 | 31,090 | public_domain_expired |
| `Godbey` | Godbey New Testament | 1902 | 27 | 7,913 | public_domain_expired |
| `GREAT` | Great Bible | 1539 | 66 | 31,095 | public_domain_expired |
| `HAWEIS` | Haweis New Testament | 1795 | 27 | 7,957 | public_domain_expired |
| `JPS1917` | JPS TaNaKH (Jewish Publication Society) | 1917 | 39 | 23,145 | public_domain_expired |
| `JST` | Joseph Smith Translation (Inspired Version) | 1867 | 65 | 30,829 | public_domain_expired |
| `KJV1611` | King James Bible (1611 First Edition) | 1611 | 66 | 31,102 | public_domain_expired |
| `KJVA` | King James Version with Apocrypha | 1611 | 80 | 36,822 | public_domain_expired |
| `Leeser` | Leeser Tanakh | 1853 | 39 | 23,143 | public_domain_expired |
| `LIVINGORACLES` | The Living Oracles | 1826 | 27 | 7,955 | public_domain_expired |
| `LSV` | Literal Standard Version | 2020 | 66 | 31,104 | cc_by_sa_4.0 |
| `LXX2012` | LXX2012: Septuagint in American English | 2012 | 54 | 28,324 | public_domain_dedicated |
| `LXXUP` | Updated Brenton English Septuagint | 2020 | 52 | 28,349 | cc0 |
| `Matthew` | Matthew Bible | 1537 | 66 | 31,092 | public_domain_expired |
| `MOFFATT` | Moffatt New Testament | 1913 | 27 | 7,940 | public_domain_expired |
| `MONTGOMERY` | Montgomery New Testament (Centenary Translation) | 1924 | 27 | 7,927 | public_domain_expired |
| `MSB` | Majority Standard Bible | 2022 | 66 | 31,098 | cc0 |
| `Murdock` | Murdock's Peshitta New Testament | 1852 | 27 | 7,947 | public_domain_expired |
| `NHEB` | New Heart English Bible | — | 66 | 31,097 | public_domain_dedicated |
| `Noyes` | Noyes Bible | 1869 | 49 | 18,213 | public_domain_expired |
| `OEBUS` | Open English Bible (US Spelling) | 2010 | 44 | 13,894 | cc0 |
| `OJB` | Orthodox Jewish Bible | 2002 | 66 | 31,165 | cc_by_4.0 |
| `OnkelosETHERIDGE` | Targum Onkelos Etheridge (English) | 1862 | 5 | 5,848 | public_domain_expired |
| `OURB` | One Unity Resource Bible | 2016 | 14 | 15,230 | cc_by_sa_4.0 |
| `PANIN` | Panin Numeric New Testament | 1914 | 27 | 7,937 | public_domain_expired |
| `PEV` | Plain English Version | 2024 | 30 | 7,374 | cc_by_sa_4.0 |
| `RIVERSIDE` | Riverside New Testament | 1923 | 27 | 7,932 | public_domain_expired |
| `RKJNT` | Revised King James New Testament | 2000 | 27 | 7,956 | public_domain_dedicated |
| `RNKJV` | Restored Name King James Version | — | 66 | 31,102 | public_domain_dedicated |
| `Rotherham` | Rotherham's Emphasised Bible | 1902 | 66 | 31,086 | public_domain_expired |
| `RV1895` | Revised Version with Apocrypha | 1885 | 80 | 36,836 | public_domain_expired |
| `SLT` | Smith's Literal Translation (Julia E. Smith Parker) | 1876 | 66 | 31,102 | public_domain_expired |
| `T4T` | Translation for Translators | 2008 | 66 | 30,640 | cc_by_sa_4.0 |
| `TCENT` | Text-Critical English New Testament | 2022 | 27 | 7,954 | cc_by_4.0 |
| `TCNT` | Twentieth Century New Testament | 1904 | 27 | 7,940 | public_domain_expired |
| `THOMSON` | Charles Thomson Septuagint (transcribed books) | 1808 | 11 | 3,599 | public_domain_expired |
| `TNT` | Tyndale New Testament (eBible.org edition) | 1534 | 27 | 7,954 | public_domain_expired |
| `Tyndale` | William Tyndale Bible (surviving corpus) | 1526 | 33 | 13,852 | public_domain_expired |
| `UKJV` | Updated King James Version | — | 66 | 31,102 | public_domain_dedicated |
| `ULT` | unfoldingWord Literal Text | — | 66 | 31,103 | cc_by_sa_4.0 |
| `UST` | unfoldingWord Simplified Text | — | 66 | 30,975 | cc_by_sa_4.0 |
| `WEB` | World English Bible Classic | 2020 | 81 | 38,029 | public_domain_dedicated |
| `Webster` | Webster Bible | 1833 | 66 | 31,102 | public_domain_expired |
| `Wesley` | Wesley New Testament | 1755 | 27 | 7,957 | public_domain_expired |
| `Weymouth` | Weymouth New Testament | 1903 | 27 | 7,957 | public_domain_expired |
| `WHISTON` | Whiston Primitive New Testament | 1745 | 27 | 7,957 | public_domain_expired |
| `WMB` | World Messianic Bible | 2011 | 66 | 31,098 | public_domain_dedicated |
| `Worrell` | Worrell New Testament | 1904 | 27 | 7,946 | public_domain_expired |
| `Worsley` | Worsley New Testament | 1770 | 27 | 7,958 | public_domain_expired |
| `WYCLIFFE` | Wycliffe Bible (Later Version, c. 1395) | 1395 | 76 | 36,227 | cc_by_sa_4.0 |
| `YLT` | Young's Literal Translation | 1862 | 66 | 31,102 | public_domain_expired |
