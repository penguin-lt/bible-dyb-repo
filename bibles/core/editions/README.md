# Critical editions

Seventeen public-domain editions of the biblical text in the original languages,
published as the
[`critical-editions`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/critical-editions)
release. Same schema as every other translation database, so they sit in the same
folder and join on `(book_id, chapter, verse)`.

| file | language | scope |
|---|---|---|
| `Westcott and Hort Greek New Testament (1881).sqlite3` | grc | New Testament |
| `Nestle Greek New Testament (1904).sqlite3` | grc | New Testament |
| `Hebrew Bible (Letteris, 1866).sqlite3` | hbo | Old Testament |
| `Vulgate (Clementine, 1598).sqlite3` | lat | Old and New Testaments |
| `Sahidic Coptic New Testament (Horner, 1911).sqlite3` | cop | New Testament |
| `Patriarchal Greek New Testament (1904, Antoniades).sqlite3` | grc | New Testament |
| `Greek New Testament, Majority Text (Robinson-Pierpont).sqlite3` | grc | New Testament |
| `Solid Rock Greek New Testament (Scholar's Edition).sqlite3` | grc | New Testament |
| `Text-Critical Greek New Testament.sqlite3` | grc | New Testament |
| `Greek Textus Receptus (Stephanus, Elzevir, Scrivener).sqlite3` | grc | New Testament |
| `Tischendorf Greek New Testament (8th edition).sqlite3` | grc | New Testament |
| `Septuagint (Greek Old Testament).sqlite3` | grc | Old Testament |
| `Brenton's Greek Text of the Septuagint.sqlite3` | grc | Old Testament |
| `Hebrew Masoretic Text (Westminster Leningrad Codex).sqlite3` | hbo | Old Testament |
| `Westminster Leningrad Codex with Strong's and morphology.sqlite3` | hbo | Old Testament |
| `Coptic New Testament, Bohairic.sqlite3` | cop | New Testament |
| `Coptic New Testament (Bohairic, narrative form).sqlite3` | cop | New Testament |

`editions_kept.csv` is the machine-readable manifest; `editions.json` records how
each was built. The builder is `tools/usfm_to_sqlite.py`, which reads USFM from
eBible.org.

## Sub-lettered verses

Where an edition prints extra material as a sub-lettered verse (`\v 14α`), the row
keeps a distinct key instead of colliding with verse 14: `14α` is stored as
`14011`, `14β` as `14012`. Keys above 1000 decode as `verse // 1000` plus
`chr(verse % 1000)`. The plain verse is still present as its own row.

## Westcott and Hort

The WH text here is **unaccented and breathings-free**, because that is the
character of the only usable public-domain transmission. Of the three:

- `byztxt/greektext-westcott-hort` (Robinson / Sandborg-Petersen) — public domain,
  unaccented beta code. **Used.**
- CrossWire `WHNU` — accented, but CC BY-NC-SA (non-commercial). Excluded.
- ScrollTag (Grauman) — accented with morphology, but CC BY-SA. Excluded.

The beta code was converted to Unicode Greek. Its encoding inverts TLG beta code
in two letters: `q` is psi and `y` is theta (`egraqa` → ἔγραψα, `yeov` → θεός).
No accents were invented; bracketed doubtful readings are kept as printed.

## This release is the single home for these texts

Four texts used to exist twice: here and in `bibles-lexicons-core`. They have
been **removed from `bibles-lexicons-core`** (which keeps its 82 English
translations and lexicons) so that each text now lives in exactly one place:

| text | was also in | dropped from there |
|---|---|---|
| `Greek Textus Receptus (Stephanus, Elzevir, Scrivener).sqlite3` | `bibles-core-english.zip` | yes |
| `Hebrew Masoretic Text (Westminster Leningrad Codex).sqlite3` | `bibles-core-english.zip` | yes |
| `Septuagint (Greek Old Testament).sqlite3` | `bibles-core-english.zip` | yes |
| `Vulgate (Clementine, 1598).sqlite3` | `bibles-core-english.zip` | yes |

Nothing was lost. The copies kept here are the better formation: identical or
fuller text, full-text search, and recorded provenance.

The Vulgate is the same text the older copies held - verified verse for verse,
all 35,809 verses and the same 73 books - so this release adds no Vulgate
content to the library, only a single canonical home for it.

One further stale copy exists and is **deliberately left alone**:
`bibles-sqlite-rev8` (superseded by `bibles-sqlite-rev9`) still carries
`TR`, `WLC`, `LXX` and `VULGATE` under their old acronyms, along with 94 other
acronym-named files. That release is the previous generation of the whole
library, not a separate copy of these four texts, and pruning it piecemeal
would leave it neither one thing nor the other. Retire it wholesale or keep it;
do not cannibalise it.

## Two editions with approximate verse boundaries

The Sahidic Coptic text of Horner (1911) is the only public-domain Sahidic New
Testament in digital form, and it divides chapters but not verses. Its chapters
are split into one row per reference verse by word count, so the text is
continuous and complete but verse boundaries are approximate; the `note` table
records `verse_references = approximate`. The two verse-level Sahidic editions
(Sahidica and the Sahidica Manuscripts) are copyrighted.

All other editions give exact verse references.

## Sources that are not USFM

Four editions do not come from eBible.org USFM and need their own readers, all
in `tools/usfm_to_sqlite.py`:

| edition | format | reader |
|---|---|---|
| Westcott and Hort | Robinson beta code, verse per line | `--format betacode` |
| Nestle 1904 | one row per word, tab-separated | `--format nestle` |
| Sahidic (Horner) | SWORD zText module | `--format sword` |
| Letteris 1866 | tab-separated verse rows | `--format letteris` |

## Excluded, and why

SBLGNT (© SBL/Logos), Family 35 (© Pickering) and Sahidica (© Wells) are
copyrighted. Rahlfs, NA28/UBS5 and BHS/BHQ are in copyright too. Still missing, and why:

- **A verse-level Sahidic text** — the public-domain one (Horner) is chapter-level; the verse-level ones (Sahidica, Sahidica Manuscripts) are copyrighted.
- **Swete's Septuagint** — public domain, but the digital transcriptions (First1KGreek, lxx-swete) are CC BY-SA.
- **A Syriac Peshitta** — no public-domain digitisation with a clear licence was found.

The two public-domain Coptic texts are both **Bohairic**; no public-domain
Sahidic edition exists, so there is no Sahidic file.

## Plain-text and EPUB editions

Every database in `critical-editions.zip` is also published as readable files,
generated from the same SQLite sources by `tools/export_formats.py`:

- **`critical-editions.txt.zip`** - 17 plain-text files
- **`critical-editions.epub.zip`** - 17 EPUB 3 files

Matching `*-SHA256SUMS.txt` files are published alongside each zip.

## New Testament critical editions added 2026-11-03 (21 total)

Four further legally obtainable NT editions, all public domain, were added
after surveying eBible's Greek catalogue (only copyrighted grcf35 and grcsbl
were new there) and the CrossWire module library:

| file | what it is | source |
|---|---|---|
| `Tregelles Greek New Testament 1864.sqlite3` | Tregelles' 1864 Greek critical edition, 27 books, 7,947 verses, exact verse refs | CSNTM/Tyndale House digitisation of the 1864 London print (the print is PD) |
| `Syriac Peshitta New Testament (BFBS 1905).sqlite3` | Syriac Peshitta NT, BFBS 1905 print, 27 books | CrossWire `Peshitta` module |
| `Vulgate, Sixtine Edition 1590, New Testament.sqlite3` | Sixtine Vulgate 1590 NT (distinct from the Clementine 1598 already held), 27 books | CrossWire `VulgSistine` module |
| `Church Slavonic Elizabeth Bible 1757, New Testament.sqlite3` | Church Slavonic NT, 1757 Elizabeth Bible print, 27 books | CrossWire `CSlElizabeth` module |

The three SWORD-module editions divide chapters but not verses, so verse rows
were reconstructed by word count and are marked `verse_references =
approximate` (same treatment as the Sahidic NT already held).

### Sought and not added, with reasons

- **SBLGNT, NA28, UBS4/UBS5** - copyrighted (SBL / Nestle-Aland / UBS).
- **Statistical Restoration GNT** - CC BY 4.0, not public domain.
- **VulgConte (2009) and VulgHetzenauer (1914)** - reprints of the Sixtine /
  Clementine Vulgate text now held; near-duplicates.
- **Wulfila Gothic NT and Western Armenian NT 1853** - public domain, but the
  machine-readable CrossWire modules carry no chapter/verse structure, so
  building them would have meant inventing verse boundaries; not added rather
  than shipped with fabricated references.
- **Lachmann, Griesbach, Scholz, Souter, Wordsworth-White, von Soden** -
  public-domain editions, but only available as poor-quality OCR scans
  (archive.org) without reliable verse alignment.
- **grcf35 (Pickering)** - (c) 2020 Wilbur N. Pickering.
