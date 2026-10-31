# The curated edition — English Bibles, critical editions, lexicons

`bibles/core/` defines a focused subset of the two datasets: 85 Scripture
databases and 25 lexical databases, published together as the
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
