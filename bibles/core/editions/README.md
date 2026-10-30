# Critical editions

Twelve public-domain editions of the biblical text in the original languages,
published as the
[`critical-editions`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/critical-editions)
release. Same schema as every other translation database, so they sit in the same
folder and join on `(book_id, chapter, verse)`.

| file | language | scope |
|---|---|---|
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

## Excluded, and why

SBLGNT (© SBL/Logos), Family 35 (© Pickering) and Sahidica (© Wells) are
copyrighted. Rahlfs, NA28/UBS5 and BHS/BHQ are in copyright too. Nestle 1904 and
Westcott–Hort are public domain but are not distributed as USFM by eBible.org —
they are available as XML/CSV from biblicalhumanities and would need their own
converter.

The two public-domain Coptic texts are both **Bohairic**; no public-domain
Sahidic edition exists, so there is no Sahidic file.
