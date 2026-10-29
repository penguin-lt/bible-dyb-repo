# Column reference

Every database carries the same ten entry columns in the same order, as the
`entry` table, with the source's SQLite types (`TEXT` / `INTEGER`). The
`work` table holds that work's manifest row verbatim, and `entry_fts` is an FTS5
index over `entry_key` + `entry_text`.

| # | column | Arrow type | nullable | description |
|---|---|---|---|---|
| 0 | `module_id` | — | — | Short stable identifier of the work — the SWORD module name, and the database filename (`MHC.sqlite3`). It is the key of the single-row `work` table, not a per-entry column: one file holds one work. The id the rows carried in the original `reference.parquet` is preserved in `note` when the two published files disagreed. |
| 2 | `module_name` | `string` | no | Human-readable title as carried by the module, e.g. `Easton's Bible Dictionary`, `Matthew Henry's Complete Commentary on the Whole Bible`. |
| 3 | `category` | `string` | no | One of `Lexicon`, `Dictionary`, `Commentary`, `Topical`, `Reference`. Derived from the SWORD driver plus the title (see `pipeline/harvest.py:category_of`). |
| 4 | `entry_key` | `string` | no | The work's own addressing key, preserved verbatim: a headword (`AARON`, `ACCESS TO GOD`), a Strong's number (`00026`, `H0430`), a verse key (`Genesis 1:1`), or a book/chapter path for general books (`/summa/FP`). |
| 5 | `entry_order` | `int32` | no | 0-based position of the entry in the source module, so the author's original ordering can be restored even where `entry_key` sorts differently. |
| 6 | `book_id` | `string` | yes | OSIS-style book code parsed from `entry_key` when the key is a scripture reference: `GEN`, `PSA`, `JHN`, `1CO`, `REV`, … Null for alphabetic headwords. |
| 7 | `chapter` | `int16` | yes | Chapter number parsed from the key, else null. |
| 8 | `verse` | `int16` | yes | Verse number parsed from the key, else null. A book- or chapter-level entry (e.g. `Genesis 0:0` prefaces) keeps `verse = 0`. |
| 9 | `entry_text` | `string` | no | Plain reading text. Markup is stripped, cross-reference tags are reduced to their printed reference text, Strong's tags and note apparatus removed, pronunciation placeholders removed, entities decoded. Paragraph breaks are preserved as `\n`. |
| 10 | `char_count` | `int32` | no | `len(entry_text)` in characters — precomputed so corpus size can be aggregated without reading the text column. |

## Key conventions

* **One row = one entry.** For lexicons and dictionaries that is one headword;
  for commentaries it is one verse or passage block; for general books it is one
  section.
* **Keys are never normalised.** `Nave` sorts `AARON` before `ABADDON` if that is
  the module's order; use `ORDER BY entry_order` to see the source order, or
  `ORDER BY entry_key` for alphabetical.
* **Repeated headwords.** Where a work genuinely defines the same headword twice
  with different text (Smith's `ADAM`, `BAAL`, `EPHRAIM`), both rows are kept and
  the later ones are keyed `ADAM (2)`, `ADAM (3)`. Exact duplicate entries were
  dropped and counted in `duplicate_entries_dropped` (a column of `work`).
* **Scripture linkage.** 210,522 entries carry a parsed `book_id`. They join
  directly to any translation database on `(book_id, chapter, verse)`.
* **Versification** is the module's own; nothing was re-mapped.

## Manifest columns (`work` table / `modules.csv`)

| column | description |
|---|---|
| `module_id`, `module_name`, `category` | as above |
| `sword_driver` | `zLD`, `RawLD`, `zCom`, `zCom4`, `RawCom`, `RawGenBook`, `RawFiles` |
| `language` | ISO 639 code from the module (`en`, `fr`, `de`, `nl`, `la`, `grc`, `vi`, `sv`, `sl`, `gez`, `tlh`, `und`, `zxx`) |
| `license` | `DistributionLicense` verbatim: Public Domain / CC0 / CC BY 4.0 / CC BY-SA 4.0 / GPL |
| `copyright` | `Copyright` field verbatim from the module `.conf` |
| `source_name`, `source_url`, `download_url` | module info page and the exact zip retrieved |
| `module_version`, `sword_version_date` | version metadata from the `.conf` |
| `text_source`, `markup_source_type` | upstream text source and markup dialect (TEI / OSIS / ThML) |
| `about` | the module's own `About` blurb (licence and provenance prose) |
| `entry_count` | rows written for this work |
| `empty_entries_skipped` | entries whose markup contained no reading text |
| `duplicate_entries_dropped` | exact duplicate entries removed |
| `repeated_keys_disambiguated` | entries kept under a `(2)`-qualified key |
| `char_count` | total characters across the work |
| `scripture_linked_entries` | entries with a parsed `book_id` |
| `retrieved` | retrieval date |

`modules_excluded.csv` carries `module_id, module_name, language, reason` for every
reference-class module that was inspected and not ingested.
