# The curated edition — English Bibles, critical editions, lexicons

`bibles/core/` defines a focused subset of the two datasets: 85 Scripture
databases and 25 lexical databases, published together as the
[`bibles-lexicons-core`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bibles-lexicons-core)
release. The full library is unchanged and still on `bibles-sqlite-rev9` and
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
