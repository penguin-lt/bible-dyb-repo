# Critical editions

Thirteen public-domain editions of the biblical text in the original languages,
published as the
[`critical-editions`](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/critical-editions)
release. Same schema as every other translation database, so they sit in the same
folder and join on `(book_id, chapter, verse)`.

| file | language | scope |
|---|---|---|
| `Westcott and Hort Greek New Testament (1881).sqlite3` | grc | New Testament |
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

## Excluded, and why

SBLGNT (© SBL/Logos), Family 35 (© Pickering) and Sahidica (© Wells) are
copyrighted. Rahlfs, NA28/UBS5 and BHS/BHQ are in copyright too. Nestle 1904 is public domain but is not distributed as
USFM by eBible.org — it is available as XML/CSV from biblicalhumanities and would
need its own converter. Westcott–Hort has been added from the byztxt text.

The two public-domain Coptic texts are both **Bohairic**; no public-domain
Sahidic edition exists, so there is no Sahidic file.
