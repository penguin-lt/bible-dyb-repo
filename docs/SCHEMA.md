# Schema catalog

Two datasets, one design. Both ship (a) a combined Parquet file for whole-corpus
scans, (b) a partitioned folder for cheap filtering, (c) a manifest table with a
row per translation/work carrying licence and provenance, and (d) a stats file
with machine-readable counts.

| dataset | combined file | partitions | manifest | stats |
|---|---|---|---|---|
| verse corpus | `bibles/text/bibles.parquet` | `bibles/text/bibles_partitioned/translation_id=<ID>/part-0.parquet` | `translations.parquet` (+`.csv`), `books.parquet` (+`.csv`) | per-translation counts inside `translations.csv` |
| reference library | `reference.parquet` (release asset) | `reference_partitioned/<Module>.parquet` (zip asset) | `bibles/reference/data/modules.parquet` (+`.csv`) | `bibles/reference/data/stats.json` |

---

## Verse corpus — 10 columns, 2,176,498 rows

| column | Arrow type | notes |
|---|---|---|
| `translation_id` | string | e.g. `KJV`, `ASV`, `WYCLIFFE`, `TEG`. Partition key. |
| `book_id` | string | OSIS-style code, 87 in use (`GEN`…`REV`, plus deuterocanonical codes). |
| `book_name` | string | display name, e.g. `1 Corinthians`. |
| `book_order` | int16 | canonical order position. |
| `book_sort` | int16 | tie-break for books sharing a slot (e.g. alternative placements). |
| `Testament` | string | `OT`, `NT`, `DC` (deuterocanonical / apocryphal). |
| `chapter` | int16 | native versification of the source. |
| `verse` | int16 | |
| `verse_end` | int16 | for merged verse ranges; equals `verse` for a single verse. |
| `verse_text` | string | plain reading text — no Strong's tags, headings or notes. |

Book codes and names: `books.csv` (88 rows, 87 in use). One row per translation
in `translations.csv` with 22 columns including `license_type`, `license_url`,
`source_name`, `source_url`, `source_retrieved`, `verse_count`, `book_count`,
`chapter_count`, `word_count`, `ot_verses`, `nt_verses`, `dc_verses` and a
`text_sha256` over the translation's text.

## Reference library — 10 columns, 795,269 rows

| column | Arrow type | notes |
|---|---|---|
| `module_id` | string | the work: `Easton`, `MHC`, `StrongsHebrew`, `Webster1913`. Partition key. |
| `module_name` | string | human title. |
| `category` | string | `Lexicon` · `Dictionary` · `Commentary` · `Topical` · `Reference`. |
| `entry_key` | string | the work's own key, verbatim: headword (`AARON`), Strong's number (`00026`), verse key (`Genesis 1:1`), book path (`/summa/FP`). |
| `entry_order` | int32 | 0-based position in the source, preserving author order. |
| `book_id` | string | parsed OSIS book code when the key is a scripture reference, else null. |
| `chapter` | int16 | parsed, else null. |
| `verse` | int16 | parsed, else null. `0` marks a book/chapter-level preface. |
| `entry_text` | string | plain reading text, markup stripped, pronunciation placeholders removed. |
| `char_count` | int32 | precomputed length, so size aggregates never read the text column. |

## Join contract

```text
bibles.text.(book_id, chapter, verse)  ==  reference.(book_id, chapter, verse)
```

Both sides use OSIS-style three-letter book codes. 210,522 reference entries are
on the reference side of this join. Commentary keys that are prefaces
(`Genesis 0:0`) have `verse = 0` and will not match a verse row — join with
`c.verse = b.verse` to exclude them, or `(c.verse = b.verse OR c.verse = 0)` to
keep them as chapter context.

Keys are **never normalised**: Greek lexicons zero-pad to five digits without a
`G` prefix (`00026`), Hebrew `RawLD` lexicons prefix `H` (`H0430`), and
`entry_order` preserves the source order even where `entry_key` sorts
differently.

## Encoding

All text columns are UTF-8. Sources that were ISO-8859-1 in the SWORD module are
decoded at harvest; the corpus is scanned for U+FFFD replacement characters and
none remain. There is no OCR-derived text anywhere in either dataset.
