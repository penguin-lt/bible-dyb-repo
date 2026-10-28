# studybible.info as a source — disposition of all 162 version codes

Source: <https://studybible.info/versions/> (index read 2026-10-28; each code's own
`/version/<CODE>` page read for its title). The library is served as verse-segmented
HTML — one page per chapter (`/<CODE>/<Book>%20<chapter>`) and one per verse
(`/<CODE>/<Book>%20<chapter>:<verse>`), server rendered, no JavaScript needed, no OCR
anywhere in the path. Scraper: `pipeline/studybible_fetch.py`; cached pages:
`pipeline/studybible_raw.json.gz` (all books for the four full scrapes) and
`pipeline/studybible_probe.json.gz` (Matthew for every probed code); comparison tool for the table below:
`pipeline/studybible_compare.py`; build: `pipeline/add_studybible_additions_rev6.py`.

Of the 162 codes, 105 are English or English-source editions and 57 are Greek, Hebrew,
Latin or other languages. **Three** English texts were missing from the dataset and
clean enough to ingest; they were added in revision 6 (73 → 76 translations).

## 1. Added in revision 6

| studybible code | id | translation | year | rows | notes |
|---|---|---|---:|---:|---|
| `Mace` | `MACE` | Daniel Mace, *The New Testament in Greek and English* | 1729 | 7,957 | English column only. Mace's own book order (Pastoral Epistles last) is re-mapped to standard chapter/verse. This is the title theword.net advertises as `Mace.nt.exe` but never shipped as plain text; the reconciliation had listed it as scan-only. |
| `Sawyer` | `SAWYER` | Leicester Ambrose Sawyer, *The New Testament, with Chronological Arrangement* | 1858 | 7,957 | Sawyer's own parenthesised section numbers (e.g. `(1:1)`) are part of his printed text and are kept. Replaces the scan previously listed in `PDF_ONLY_SOURCES.md`. |
| `Ottley` | `OTTLEY` | R. R. Ottley, *The Book of Isaiah according to the Septuagint* | 1904–06 | 1,286 | Isaiah only, Greek chapter/verse numbering. |

Duplicate screen (normalised, word-identical verses against every existing translation
over all shared references — the same test that caught the revision-2 duplicates):
Mace's closest neighbour is `KJVA` at **2.3 %**, Sawyer's is `Anderson` at **3.3 %**,
Ottley's is `LXXUP` at **0.9 %** (Brenton 0.7 %). Nothing near the ~90 % that marks a
respelling.

Text quality: 0 `ſ`, 0 `vv`/`cv` OCR artefacts, 0 leftover HTML tags or entities, no
double spaces, longest verse 379 characters. One source defect was found and corrected:
Isaiah 24:20 came through as "for her transgression **15** strong upon her" — the `15`
is the library's slip for `is` in Ottley's "for her transgression is strong upon her";
it is fixed in the ingested text and flagged in the manifest notes.

## 2. Already in the dataset under another code

Each code below was scraped for Matthew and compared with the dataset; the number is the
share of Matthew verses that are word-identical after normalisation, against the named
dataset translation.

| studybible code | dataset id | Matthew identity |
|---|---|---:|
| `KJV` | `KJVA` | 99.2 % |
| `KJV_Cambridge` | `KJVA` | 99.4 % |
| `Wycliffe` | `WYCLIFFE` | 100 % |
| `Coverdale` | `Coverdale` | 100 % |
| `Matthew` | `Matthew` | 100 % |
| `Great` | `GREAT` | 100 % |
| `Geneva` | `GNV1599` (and `GNV1560` at 79.9 %) | 100 % |
| `Bishops` | `BISHOPS` | 99.9 % |
| `DouayRheims` | `DRA` | 88.8 % |
| `Tyndale` | `Tyndale` / `TNT` | 83.6 % / 44.3 % (two different transcriptions, both kept) |
| `Wesley` | `Wesley` | 100 % |
| `Worsley` | `Worsley` | 99.7 % |
| `Haweis` | `HAWEIS` | 100 % |
| `Living_Oracles` | `LIVINGORACLES` | 98.6 % |
| `Webster` | `Webster` | 100 % |
| `Etheridge` | `Etheridge` | 89.2 % |
| `Murdock` | `Murdock` | 100 % |
| `ABU` | `ABU1865` | 100 % |
| `Anderson` | `Anderson` | 96.3 % |
| `Noyes` | `Noyes` | 92.9 % |
| `JuliaSmith` | `SLT` | 100 % |
| `Darby` | `DBY` | 99.9 % |
| `ERV` | `RV1895` | 100 % |
| `ASV` | `ASV` | 98.2 % |
| `Rotherham` | `Rotherham` | 98.8 % |
| `Twentieth_Century` | `TCNT` | 95.6 % |
| `Godbey` | `Godbey` | 99.9 % |
| `WNT` | `Weymouth` | 99.8 % |
| `Worrell` | `Worrell` | 100 % |
| `Moffatt` | `MOFFATT` | 99.8 % |
| `Riverside` | `RIVERSIDE` | 100 % |
| `MNT` | `MONTGOMERY` | 97.2 % |
| `BBE` | `BBE` | 99.7 % |
| `ACV` | `ACV` | 100 % |
| `WEB` | `WEB` | 93.5 % |
| `NHEB` | `NHEB` | 61.2 % |
| `AKJV` | `AKJV` | 93.2 % |
| `BSB` | `BSB` | 99.9 % |
| `MSB` | `MSB` | 96.2 % |
| `BLB` | `BLB` | 89.8 % |
| `RKJNT` | `RKJNT` | **100 %** — byte-identical |
| `UKJV` | `UKJV` | **100 %** — byte-identical |
| `WPNT` | `F35` | 95.2 % — Pickering's own Family 35 text |
| `Whiston` | `WHISTON` | same edition (added revision 5) |

`Thomson` is a special case: the dataset has only the 11 books of Thomson transcribed by
hand so far (3,599 verses), and studybible.info has **all 66 books (30,974 verses)**.
Over the 3,574 verses they share, **94.2 % are word-identical** — the differences are
transcription spellings, not a different translator. The 56 missing books (27,395 verses)
are recorded in `pipeline/stats_v6.json` →
`thomson_completeness.available_not_ingested`, ready to be added in a later revision.
(Daniel differs in versification: the dataset splits `DAN` + `DAG`, the site has one 14-
chapter Daniel; `PS2`/Psalm 151 is not served by the site.)

Not fetched as chapters (they have no chapter pages, verse pages only, and add nothing):
`KJV_Strongs`, `ASV_Strongs`, `WEB_Strongs`, `AKJV_Strongs`, `CKJV_Strongs`,
`Webster_Strongs`, `new`.

## 3. Respellings / repackagings — excluded by the balanced-dedup rule

These are not new translations of the text; each is a KJV- or YLT-family modernisation or
a tagged edition of something already present. The low identity scores below are an
artefact of re-typing, not of new wording.

| code | what it is | nearest dataset text (Matthew) |
|---|---|---:|
| `KJ2000` | King James 2000 | UKJV 37.3 % |
| `KJC` | King James Clarified | UKJV 45.3 % |
| `MKJV` | Modern King James Version | RKJNT 11.8 % |
| `TKJU` | Timeless King James Update | AKJV 17.6 % |
| `EJ2000` | English Jubilee Bible | KJVA 22.1 % |
| `MSTC` | Modern Spelling Tyndale–Coverdale | KJVA 7.9 % |
| `RYLT` | Revised Young's Literal Translation NT | YLT 51.1 % |
| `CAB` | Complete Apostle's Bible | RKJNT 6.7 % |
| `LITV`, `MLV` | literal KJV-era revisions | ULT 2.9 % / 1.8 % |
| `JPS_ASV_Byz` | JPS OT + ASV NT conformed to the Byzantine text | ASVBT 76.0 %, ASV 71.0 % — a variant of `ASVBT` |
| `ECB` | exeGeses Companion Bible (KJV with sacred names) | NHEB 0.3 % |
| `ABP_Strongs`, `ACVI` | Apostolic Bible Polyglot English / ACV reverse interlinear | interlinear — tagged text is out of scope by rule |

## 4. Clean texts held out on copyright grounds

| code | work | status |
|---|---|---|
| `Goodspeed` | Edgar J. Goodspeed, *The New Testament: An American Translation* | 1923 printing PD in the US since 2019, but the circulating digital text is the 1925/1937 edition — not verifiably free. Addable in one build if the 1923 printing is accepted as PD. |
| `Williams` | Charles B. Williams, *The New Testament in the Language of the People* | 1937, renewed |
| `Lamsa` | George M. Lamsa, *The Holy Bible from Ancient Eastern Manuscripts* | 1933, renewed |
| `CLV` | Concordant Literal Version | 1926 first edition, later revisions © Concordant Publishing Concern |
| `ISV` | International Standard Version | © 1995–2011, all rights reserved |
| `LEB` | Lexham English Bible | © Lexham Press, all rights reserved |
| `Common` | *The Common Edition: New Testament* | © Timothy E. Clontz 1999, "All rights reserved" on its own version page |
| `AUV` | An Understandable Version | modern work, no licence statement found |
| `NSB` | New Simplified Bible | modern work, no licence statement found |
| `VIN` | Venerably Illuminating Narrative | modern work (2020s), no licence statement found |
| `JMNT` | Jonathan Mitchell New Testament | © Jonathan Mitchell |
| `BIB`, `BGB` | Berean Interlinear Bible / Berean Greek Bible | interlinear + Greek source text; the running English is `BLB`/`BSB`, already present |

The last four columns of evidence: for `Common` the site's own page states the copyright;
for the others no free licence appears on the site, and nothing in the catalogue record
suggests one has expired.

## 5. Not translations of the running text, or not English

* **Greek / Hebrew / Latin source texts and interlinears** (32 codes): `Stephanus`, `TR`,
  `Tischendorf`, `Tregelles`, `Nestle`, `RP`, `SBLGNT`, `LXX_WH`, `HOT`, `IHOT`, `IGNT`,
  `Brenton_Greek`, `Vulgate`, `Clementine_Vulgate`, `Peshitta`, `Arabic`, `Armenian`
  source editions. Out of scope: the dataset is English running text.
* **West Saxon Gospels** (`WestSaxon990`, `WestSaxon1175`) — Old English (pre-1150), outside
  the "English translation" scope used for every other row, and the site's verses carry
  editorial Latin notes in `[Note: …]` brackets. Noted here rather than ingested; can be
  added on request.
* **Other languages** (23 codes): Luther 1545/1912, Elberfelder 1871/1905, Statenvertaling,
  Giguet, Darby FR, Martin, Segond, Reina-Valera, Sagradas Escrituras, Jubilee ES, Almeida,
  Kralická, CUV/CUVS, RST, Finnish, Hungarian, Japanese, Korean, Esperanto, Estonian,
  Georgian, Haitian, Indonesian, Italian, Kabyle, Latvian, Lithuanian, Manx Gaelic,
  Norwegian, Romanian, Ukrainian (×2), Bulgarian, Croatian, Danish, Albanian, Amharic,
  Basque, Breton, Armenian (×2), PBG.

## 6. Method notes

* Chapter pages are the fast path. A handful of chapters are served only verse-by-verse
  (some psalm titles in some versions), so the scraper falls back to the verse pages for
  any chapter that comes back empty.
* Verse counts were checked against the KJV's 7,957 NT slots: Mace and Sawyer fill all
  7,957; Ottley fills all 1,286 Isaiah verses. Nothing was retyped and nothing was OCR'd.
* Scraped pages are cached in two gzipped files so the build is reproducible without
  re-hitting the site: `pipeline/studybible_raw.json.gz` (2.1 MB — every book of Mace,
  Sawyer, Ottley and Thomson) and `pipeline/studybible_probe.json.gz` (3.1 MB — Matthew
  for the 70 other codes that were probed for the comparison table). The plain
  per-book JSON tree was 17 MB across 193 files and is regenerated by a live scrape.
