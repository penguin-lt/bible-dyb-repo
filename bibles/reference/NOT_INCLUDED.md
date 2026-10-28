# Not included — reference-class modules we inspected and rejected

52 of the 148 reference-class modules in the CrossWire archive are not in this
dataset. Every one of them was excluded for **licence**, never for size,
difficulty or markup quality. The machine-readable version of this list is
`modules_excluded.csv` (`module_id, module_name, language, reason`).

The rule is the one used for the bibles dataset: public domain, or a licence
that permits redistribution (CC0, CC BY, CC BY-SA, GPL). A module that says
"Permission granted to CrossWire" has *not* granted redistribution to you.

## Copyrighted — no redistribution grant — 20 modules

| module | language | title |
|---|---|---|
| `DBD` | en | Day By Day By Grace - Bob Hoekstra |
| `FreCJE` | fr | Chaque jour les Écritures |
| `FreDAW` | fr | Dictionnaire encyclopédique de la Bible A. Westphal (1932) |
| `FreStrongsGreek` | fr | Dictionnaire grec des nombres de Strong |
| `FreStrongsHebrew` | fr | Lexique hébreu des nombres de Strong |
| `GerHfaLex2002` | de | Hoffnung fuer alle - Worterklaerungen |
| `GerLutPredigten` | de | Eine Sammlung von Lutherpredigten |
| `ItaDizGreco` | it | Greek-Italian Dictionary of the New Testament |
| `ItaNomiBibbia` | it | Dizionario dei nomi della Bibbia |
| `MollColossians` | en | Paul's Letter to the Believers at Colosse - A Series of Devotions by Pastor Ra |
| `NETnotesfree` | en | Free version of NET Bible Footnotes with limited notes |
| `PorIBP` | pt | Índice Bíblico-Pastoral da Bíblia dos Capuchinhos |
| `PorLitCal2020` | pt | Calendário litúrgico 2020 |
| `PorLitCal2022` | pt | Calendário litúrgico |
| `PorLitCal2023` | pt | Calendário litúrgico 2023 |
| `PorLitCal2024` | pt | Calendário litúrgico 2024 |
| `RusCARSADICT` | ru | Смысловой перевод Таурата, Книги Пророков, Забура и Инджила. |
| `RusCARSDict` | ru | Смысловой перевод Таурата, Книги Пророков, Забура и Инджила. |
| `RusCARSTDICT` | ru | Смысловой перевод Таврота, Книги Пророков, Забура и Инджила. |
| `VieLCCMNCT` | vi | Lời Chúa Cho Mọi Người Chú Thích |

## Free non-commercial only — 10 modules

| module | language | title |
|---|---|---|
| `alzat` | ar | الذات للبابا شنودة الثالث |
| `DutKingComments` | nl | Kingcomments-NL, Commentaar op de hele Bijbel. |
| `GerAugustinus` | de | Augustines Confessions (German) |
| `GerKingComments` | de | Kingcomments (German), Kommentar zur ganzen Bibel. |
| `GreekHebrew` | grc | Greek to Hebrew Dictionary of Septuagint Words |
| `HebrewGreek` | he | Hebrew to Greek Dictionary of Septuagint Words |
| `KingComments` | en | Kingcomments, commentary on the whole Bible. |
| `PorKingComments` | pt | Kingcomments |
| `RWP` | en | Robertson's Word Pictures |
| `SBLGNTApp` | grc | The Greek New Testament: SBL Edition, Apparatus |

## No licence statement at all — 9 modules

| module | language | title |
|---|---|---|
| `2BabDict` | en | Definitions and Symbols from The Two Babylons |
| `ABS_Essay_GoodSam_SWB` | en | Essays on The Good Samaritan: Violence on the Road, Social World of Bandits |
| `br_en` | br | Breton to English Glossary |
| `en_eu` | eu | English to Basque Glossary |
| `Family` | en | Family Bible Notes |
| `FreBailly` | fr | Abbreviated Greek-French Dictionary by A. Bailly. |
| `Geneva` | en | Geneva Bible Translation Notes |
| `la_en` | la | Latin to English Glossary |
| `Personal` | — | Personal Commentary |

## Copyrighted, "freely distributable" — 8 modules

| module | language | title |
|---|---|---|
| `ChisStrongsGreek` | zh-Hans | CBOL希腊文字典 |
| `ChisStrongsHebrew` | zh-Hans | CBOL希伯来文字典 |
| `ChitStrongsGreek` | zh-Hant | CBOL希臘文字典 |
| `ChitStrongsHebrew` | zh-Hant | CBOL希伯來文字典 |
| `FreGBM` | fr | Glossary of the Bible David Martin 1744 |
| `FreLitCal2025` | fr | Calendrier liturgique catholique |
| `FreLitCal2026` | fr | Calendrier liturgique catholique 2026 |
| `Westminster21` | en | The Westminster Standards translated into twenty-first century American Englis |

## Licence deferred to a README — 3 modules

| module | language | title |
|---|---|---|
| `ZhEnglish` | zh | English/Chinese Dictionary |
| `ZhHanzi` | zh | Chinese/English Dictionary |
| `ZhPinyin` | zh | Chinese (Pinyin)/English Dictionary |

## CC BY-NC-ND (non-commercial, no derivatives) — 2 modules

| module | language | title |
|---|---|---|
| `GerStrongsGreek` | de | Griechisch-Deutsch Strong Lexikon - 2020 |
| `SloHenoh` | sl | The Book of Enoch in Slovene |

## Notable exclusions, spelled out

* **`RWP` — Robertson's Word Pictures.** Asked for often, still in copyright; the
  module is "free non-commercial distribution" only.
* **`NETnotesfree` / `SBLGNTApp`.** Both carry a bare `Copyrighted` or
  non-commercial grant with no permission to redistribute.
* **`Geneva`, `Family`, `2BabDict`, `FreBailly`, `la_en`, `en_eu`, `br_en`,
  `ABS_Essay_GoodSam_SWB`, `Personal`.** `DistributionLicense` is blank. Some are
  very likely public domain on age grounds (Cawdrey's 1604 dictionary *is*
  public domain and arrived with a licence; these did not), but a blank field is
  not a licence, and `FreBailly` carries a copyright line naming its transcriber.
  If CrossWire adds an explicit PD statement for any of them, they can be added
  by rerunning the pipeline.
* **Chinese, Russian, Italian, Portuguese, Vietnamese, Arabic and Korean reference
  works.** Excluded on licence, not language — the dataset already carries
  French, German, Dutch, Latin, Greek, Swedish, Ge'ez and Vietnamese works that
  did clear the licence test.

## Ingested since this list was first written

`LSJ`, `BDB`, `TBESG` and `TBESH` were on the "not yet ingested" list below and
are now **in** the dataset (see `SOURCES.md`). They were never licence
exclusions — only parser work. Still open from that list: `TIPNR` (proper names)
and the STEPBible morphology-code files, both text-annotation data rather than
reference works.

## Not yet ingested, though the source is open

These are public domain or explicitly free and were confirmed reachable on
2026-10-28. They are not SWORD modules, so they need their own parser; they are
the next revision, not rejections:

| source | work | licence | why it matters |
|---|---|---|---|
| Perseus (`PerseusDL/lexica`) | LSJ TEI XML, 42.9 MB | public domain | **rejected — alpha-only fascicle, not the full lexicon** |
| Open Scriptures (`HebrewLexicon`) | Brown-Driver-Briggs, full | public domain | **ingested as `BDB`** |
| STEPBible (`STEPBible-Data`) | TFLSJ formatted LSJ, TBESG/TBESH | CC BY 4.0 | **ingested as `LSJ`, `TBESG`, `TBESH`** |
| STEPBible (`STEPBible-Data`) | TIPNR proper names, morphology codes | CC BY 4.0 | annotation data, not a reference work — out of scope |
| CCEL | its whole reference corpus | mixed PD | same works as SWORD, but ThML endpoints now 404 — SWORD is the cleaner route |

## v3 exclusions, with counts

### Non-commercial and no-derivative licences — 112 works

Sefaria publishes 103 of its English texts under `CC-BY-NC` or `CC-BY-NC-SA`, and
9 more carry comparable restrictions. They are readable, but the licence forbids
commercial use and, for the `-SA` subset, imposes share-alike on anything derived.
Rejected before combining; the list is in `data/modules_excluded.csv`. Notably
this removes SBLGNT's apparatus and several modern translations of rabbinic
works.

### CCEL page-image volumes — 74 works

Scanned volumes whose ThML carries only `Image of page i`, `Image of page ii`, …
placeholders. There is no text to extract, and OCR is excluded by standing rule.
These were ingested in the first v3 run and removed after detection; the guard in
`ccel_harvest.py` now rejects them at source.

### Empty rights with a post-1928 print edition — 476 works

CCEL lists them, `DC.Rights` is blank, and the print edition they were digitised
from is 1929 or later. With no statement and no expiry argument there is no
public-domain basis. They are the single largest omission in this revision.

### Exact duplicates — 2 works

`ccel_encyclopedia` (superseded by `schaff_encyclopedia`) and
`walker_harmony2`. Text-identical, so only one copy is kept.

### Same-work pairs kept, not merged — 50 pairs

`data/dedupe_report.csv` lists works whose titles and subject overlap across
sources (e.g. BDB from SWORD and from Open Scriptures; Schaff's *History* from
CCEL and from SWORD). Both editions are kept because their coverage and wording
differ; the report flags them so a consumer can pick. Fuzzy deduplication was
tried and abandoned — it deleted Barnes on Isaiah as a duplicate of Schaff's
encyclopedia on a 0.93 containment score driven entirely by series front matter.
