# The curated edition — English Bibles, critical editions, lexicons

`bibles/core/` defines a focused subset of the two datasets: 126 Scripture
databases and 25 lexical databases. The original English+Malayalam set is published as the
[`bibles-lexicons-core`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bibles-lexicons-core)
release, plus **12 further critical editions** added separately as
[`critical-editions`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/critical-editions)
(see `editions/`). The full library is unchanged and still on `bibles-sqlite-rev9` and
`reference-sqlite-rev5`.

This directory holds the **selection rules and the manifests**, not the data.

| file | contents |
|---|---|
| `translations_kept.csv` | the 85 translations that survive, with `full_name` and the filename each becomes |
| `translations_dropped.csv` | the 12 that were removed |
| `lexicons_kept.csv` | the 25 reference works that survive, with `full_name` and filename |
| `DROPPED.md` | the same three lists in readable form, plus what was excluded and why |

## What makes the cut

**Translations.** Every English-dialect text (81 of the 97) — Wycliffe through
Tyndale, Coverdale, Matthew, Great, Bishops', both Genevas, KJV 1611 and KJVA,
RV 1885, ASV 1901, up to LSB, BSB, ULT/UST and the 2025 texts — plus the four
critical editions: **LXX** (Septuagint), **TR** (Textus Receptus), **VULGATE**
(Clementine) and **WLC** (Westminster Leningrad Codex). English translations made
from the Septuagint (Brenton, LXX2012, Updated Brenton, Thomson, Ottley) stay,
because they are English translations.

Removed: the 12 non-English Bibles — Chinese Union, Korean 1910, Luther 1912,
Segond 1910, Diodati, Statenvertaling 1917, Reina-Valera 1909, Russian Synodal,
Arabic Van Dyck, and the three Malayalam Bibles.

**Reference works.** Only lexicography: the 18 `Lexicon`-category works (BDB,
LSJ, Abbott-Smith, Dodson, MLStrong, TBESH, TBESG, BDB Glosses, OSHM, Packard and
Robinson in English and French) and 7 Bible dictionaries (Easton, Smith, ISBE,
American Tract Society, Strong's Hebrew, Strong's Greek, Condensed Biblical
Cyclopedia, Wace). Everything else — 9,116 commentaries, Rabbinic works,
theology, liturgy, devotionals, church history — is out.

Three items were weighed and excluded on grounds of substance rather than
category: the **Klingon** lexicons (conlang mappings), **Spurgeon's Morning and
Evening** (a daily devotional the source catalogue files under `Lexicon`) and the
**Swedish glossary** of 330 entries. **Webster's 1806/1828/1913** dictionaries are
excluded as general English lexicography, not biblical. The **STEPBible tag
datasets** (STRONGSHEB/GRK, TEGMC, TEHMC, TIPNR) are excluded because they are
text-encoding data rather than lexicons, though `reference-sqlite-rev5` has them.

## The renaming rule

Every file is named by its full title. The old acronym is kept inside the file as
provenance — `note.source_translation_id` for translations, `note.source_module_id`
for works — while `translation_id` / `work.module_id` carry the full name, so a
file's id matches its filename.

Names are the catalogue's own `translation_name` / `module_name`, with only
filesystem-hostile characters replaced (`/`→`or`, `:`→` -`, `*?"<>|` removed).

## Rebuilding

```bash
# 1. the 85 translations, from the rev9 databases (or bibles.parquet)
python3 tools/parquet_to_sqlite.py --bibles bibles.parquet \
    --translations bibles/text/translations.csv \
    --books bibles/text/books.csv --out-dir sqfull/ \
    --only $(cut -d, -f1 bibles/core/translations_kept.csv | tail -n +2 | tr '\n' ' ')

# 2. the 25 lexical works
python3 tools/reference_to_sqlite.py --reference reference.parquet \
    --modules modules.parquet --out-dir sqref/ \
    --only $(cut -d, -f1 bibles/core/lexicons_kept.csv | tail -n +2 | tr '\n' ' ')

# 3. rename both sets per the `file` column of the two kept.csv manifests
```

The `file` column in each manifest is the exact filename to use.

## Modern translations in this collection

"Modern" is a licence problem before it is a search problem: nearly every
translation made after 1950 is copyrighted, and the free ones cluster around
2016-2026. This collection now holds the free modern English translations that
exist and are not near-duplicates of each other:

| translation | year | note |
|---|---|---|
| `World English Bible Updated.sqlite3` | 2026 | LORD/GOD for the divine name; otherwise the Classic text plus typo fixes |
| `World English Bible, Catholic Edition.sqlite3` | 2026 | deuterocanon in Catholic order |
| `Majority Standard Bible.sqlite3` | 2022 | |
| `Literal Standard Version.sqlite3` | 2020 | |
| `Berean Standard Bible.sqlite3` | 2016 | |
| `Berean Literal Bible.sqlite3` | 2016 | |
| `Plain English Version.sqlite3` | 2024 | |
| `Free Bible Version.sqlite3` | 2018 | |
| `Open English Bible (US Spelling).sqlite3` | 2010 | |
| `unfoldingWord Literal Text.sqlite3` | - | |
| `King James Version, Cambridge Paragraph Bible.sqlite3` | 1873 | Scrivener's critical revision of the AV: 57% of verses differ from the 1611 text |

### Sought and not included, with reasons

- **NET Bible** - copyrighted, Biblical Studies Press. eBible.org hosts a USFM
  edition but it is not free to redistribute.
- **Modern Literal Version (MLV)** - copyrighted, and the permission forbids
  selling it in any form, including with handling or shipping fees: not
  public domain and not open-licensed.
- **Analytical-Literal Translation (ALT)** - quoting limited to 500 verses
  without written permission. Not redistributable.
- **Amplified, GOD'S WORD, NASB, ERV** - marked non-redistributable on
  eBible.org.
- **World English Bible British Edition / British with Deuterocanon** - 72-84%
  of verses identical to the Classic edition already held. Spelling variants of
  a text we already have, so not added.
- **Revised Version 1895** - public domain but 19th century, and 40% verse
  overlap with the ASV already held.

## Plain-text and EPUB editions

Every database in `bibles-core-english.zip` is also published as readable
files, generated directly from the SQLite source of truth by
`tools/export_formats.py`:

- **`bibles-core-english.txt.zip`** - 90 plain-text files (one per translation in that release)
- **`bibles-core-english.epub.zip`** - 90 EPUB 3 files (one per translation in that release)

Each `.txt` begins with the title, edition note, licence and source URL, then
books as banners, chapters as `--- Chapter N ---`, and verses as `N  text`.
Each `.epub` is a valid EPUB 3 with a table of contents and one XHTML file per
book. Matching `*-SHA256SUMS.txt` files are published alongside each zip.

## Creative Commons translations

The public-domain gate was widened on 2026-11-12 to include Creative Commons
licences (BY / BY-SA / CC0), per request. Three CC BY-SA 4.0 English editions
were added (84 -> 87 databases):

- **Open English Translation, Readers' Version** (OET-RV) - modern open-licensed
  translation, includes the deuterocanon. CC BY-SA 4.0.
- **Open English Translation, Literal Version** (OET-LV) - NT literal companion.
  CC BY-SA 4.0.
- **Unlocked Dynamic Bible** (UDB v12) - dynamic paraphrase (Door43/Wycliffe).
  CC BY-SA 4.0. Verified distinct: 0.6% of verses word-identical to the T4T
  already held.

Already-held works whose licence is in fact CC: LSV (CC BY-SA 4.0), PEV
(CC BY-SA 4.0), ULT/UST/ULB (CC BY-SA 4.0), OEB (CC0 public-domain dedication),
FBV (CC BY-ND 4.0).

### Checked and NOT added

- **Lexham English Bible (LEB)** - despite some web claims of CC BY-SA, its own
  USFM front matter (v20230701) states a custom non-CC licence (free to give
  away, not to sell standalone, annual reporting above 1,000 verses). Not a
  Creative Commons work.
- **Dynamic English Bible (DEB2020, BibleCorps)** - CC BY-SA family, but marked
  "Checking (not ready)" - draft.
- **AFINT (African International NT)** - CC BY-SA English NTs exist on
  open.bible, but no clean machine-readable full-text download was reachable.
- NC/ND-licensed English works (e.g. FBV is ND) are kept only where already
  held; nothing new with NC/ND terms was added.

## Malayalam translations

Added 2026-10-29 (87 -> 90 databases), per request, under the same
PD / CC BY-SA / CC0 / Unlicense gate:

- **Sathyavedapusthakam 1910 (Malayalam Bible)** - the 1910 BFBS Malayalam
  Bible in its original orthography, 66 books / 31,098 verses. Public domain
  (TFBF digitization marked Public Domain; CrossWire module Mal1910 states
  "Distribution License Public Domain"). CC0/Public Domain Mark 1.0.
- **Malayalam Sathyavedapusthakam 1910, Contemporary Orthography (2015)** -
  the same 1910 text re-spelled in contemporary Malayalam orthography by the
  Free Bible Foundation (eBible `mal2015`); its details page states CC BY-SA
  4.0. 31,098 verses. Verified distinct from the 1910 original: only 58.9% of
  verses are identical (orthographic modernization only) - both are kept as
  separately licensed editions.
- **Bailey's Malayalam New Testament 1829** - Benjamin Bailey's 1829 NT, the
  first Malayalam Bible translation, NT only (27 books / 7,739 verses).
  GitHub repo licensed under the Unlicense (public domain). The 1829 print
  repeats some verse numbers within chapters (section numbering); the repeats
  were merged into single rows, no text lost. 125 verses still carry
  unconverted .SFM markup (`<lb/>`, `<lg ...>`), preserved verbatim.

### Malayalam works checked and NOT added

- **Indian Revised Version (eBible `mal`)** - copyright Bridge Communication
  Systems. Not PD, not CC.
- **Biblica Open Malayalam Contemporary Version (eBible `malc`)** - copyright
  Biblica.
- **SanskritBible Malayalam (eBible `sanmal`)** - copyright SanskritBible.in.

## Major Latin-script languages

Added 2026-10-29 (90 -> 126 databases), per request, restricted to languages
written in the **Latin script** and under the same PD / CC BY / CC BY-SA /
CC0 / Unlicense gate. 36 editions in 26 languages, 1,000,383 verses:

| language | editions added |
|---|---|
| Spanish | Reina-Valera 1909 (PD); ULB es-419 (CC BY-SA 4.0) |
| French | Louis Segond 1910 (PD); ULB fr (CC BY-SA 4.0) |
| Portuguese | NVA (CC BY-SA 4.0, CrossWire); ULB pt-BR (CC BY-SA 4.0) |
| German | Lutherbibel 1912 (PD); Elberfelder 1905 (PD) |
| Italian | Diodati 1885 (PD); Riveduta 1927 (PD) |
| Dutch | Statenvertaling 1917 (PD); Petrus Canisius 1939, Catholic canon (PD) |
| Romanian | Biblia Liberă, NT, Latin script (PD; upstream draft note kept) |
| Czech | Bible Kralická 1613 (PD) |
| Croatian | Sveta Biblija (Šarić), Catholic canon (PD) |
| Hungarian | Károli 1908 (PD, CrossWire) |
| Finnish | Biblia 1776 with apocrypha (PD, CrossWire) |
| Swedish | Svenska Bibeln 1917 with apocrypha (PD, CrossWire) |
| Norwegian | Bibelen på Norsk 1930 (PD, CrossWire) |
| Danish | OT 1871 + NT 1907, original orthography (PD, CrossWire) |
| Polish | Biblia Gdańska 1881 (PD, CrossWire) |
| Latvian | Glück 8th edition (PD, CrossWire) |
| Slovenian | Stritar 1882, NT + Psalms text in a 73-book module (PD, CrossWire) |
| Albanian | Bibla Shqiptare (PD, CrossWire) |
| Vietnamese | Kinh Thánh 1934 (PD); ULB vi (CC BY-SA 4.0) |
| Indonesian | ULB id (CC BY-SA 4.0); covers the Malay language family |
| Tagalog/Filipino | Ang Biblia 1905 (PD, CrossWire); ULB tl (CC BY-SA 4.0) |
| Cebuano | ULB ceb (CC BY-SA 4.0) |
| Ilocano | ULB ilo (CC BY-SA 4.0) |
| Swahili | Krapf 1850 NT portions (PD); ULB sw (CC BY-SA 4.0) |
| Hausa | ULB ha (CC BY-SA 4.0) |
| Esperanto | Londona Biblio 1910 (PD) |
| Haitian Creole | Bib La 1985 (PD: 1985 notice without US renewal) |

Sources: eBible.org USFM (details page states Public Domain for each), CrossWire
SWORD modules via scrollmapper/bible_databases JSON (ModInfo.jsp states
"Distribution License Public Domain" / "CC BY-SA 4.0"), Door43-Catalog ULB
repos (LICENSE.md = CC BY-SA 4.0). Empty verse rows present in some SWORD
modules are absent rows and are not stored. All 126 databases are also
published together with clean asset names on the
[`bibles-core-multilingual`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bibles-core-multilingual)
release (`bibles-core.zip`); the earlier `bibles-lexicons-core` release is
untouched.

### Latin-script languages checked with NO qualifying edition (not added)

Turkish, Malay (zlmKSZI is ©), Lithuanian (LtKBB ©), Estonian, Slovak,
Catalan, Galician, Basque, Afrikaans (Afr1953 ©), Somali (SomKQA ©),
Yoruba, Igbo, Zulu, Xhosa, Shona/Ndebele (GFDL only - outside the gate),
and all non-Latin-script languages (Arabic, Greek, Hebrew, Russian, Ukrainian,
Chinese, Japanese, Korean, Hindi, Bengali, Tamil, ... - Greek/Hebrew/Latin
critical editions are already in `editions/`). CrossWire modules marked
"Copyrighted; permission to distribute granted to CrossWire" (e.g. SpaRV1909,
FreSegond1910, RomCor) are NOT redistributable by us and were not used; where
the same text is PD at the source (eBible details page) the eBible copy was
used instead.
