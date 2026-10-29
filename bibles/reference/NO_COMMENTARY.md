# Edition without commentaries

A narrower build of the same database for readers who want the primary texts,
lexicons, dictionaries and apparatus but not running commentary.

Released as **`bible-reference-v5-nocommentary`**:
<https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-reference-v5-nocommentary>

| | full v5 | without commentaries |
|---|---|---|
| Works | 9,141 | **3,795** |
| Entries | 1,073,530 | **687,596** |
| Characters | 2,369,741,291 | **1,198,048,181** |
| SQLite databases | 9,141 files, 5.4 GB | **3,795 files, 2.6 GB** |

Schema, column names and the `join on (book_id, chapter, verse)` convention are
byte-for-byte the same, so any query written for the full release works here.
This edition is a *selection*, not a separate build: every file in it is one of
the 9,141, and each `work` table carries its `status` (`ok`) column so the
subset is self-identifying.

## What was removed — 5,346 works

| rule | works |
|---|---|
| SWORD modules with category `Commentary` (Barnes, Matthew Henry, Clarke, JFB, Catena, Pulpit, Cambridge Bible, Ellicott …) | 162 |
| Sefaria works that Sefaria itself files under a commentary category (`Rishonim on…`, `Acharonim on…`, `Modern Commentary on…`, `…/Commentary`, `Shulchan Arukh/Commentary`, `Mishneh Torah/Commentary`) | 5,184 |

The Sefaria rule uses **Sefaria's own taxonomy** from `books.json`, not the title.
That matters in both directions: titles miss commentaries named after a tractate
(`Tosafot on Bava Metzia`, `Rashi on Chagigah`) and would mis-fire on texts that
merely mention a book. The complete inventory is in
`data/commentaries_removed.csv` — every removed work with its id, size and the
rule that removed it — so any single work can be restored by id.

## What was deliberately kept

* **Talmud, Mishnah, Tosefta, Midrash, Targums, Tanakh, Zohar, siddurim** — the
  texts themselves, including their Hebrew/Aramaic originals.
* **Mishneh Torah and Shulchan Arukh themselves** (the codes), while their
  supercommentaries are removed.
* **Responsa** (including responsa that quote and argue — they are their own genre,
  not commentary).
* **Lexicons and dictionaries**: LSJ, BDB, TBESG/TBESH, Strong's, Webster,
  Smith, ISBE, Easton, Nave, Torrey.
* **Interlinears and apparatus**: TAGNT, TAHOT, morphology, verse-level Strong's,
  TIPNR, TVTMS, cross-references, Pleiades.
* **Patristics, sermons, dogmatics, devotion, church history, creeds, liturgy.**

## Known residue — 38 works

A small number of patristic and classical volumes are filed under `Patristics` or
`Reference` rather than `Commentary`, so they survive on a category rule even
though their titles read like commentary: the 17 **Catenae (Novum Testamentum)**
volumes (Greek catena fragments), Origen's *Commentarium in Evangelium Matthaei*,
Michael of Ephesus' *In Libros De Partibus Animalium Commentaria*, NPNF volumes
of Chrysostom's expositions, and similar. They are listed in
`data/commentaries_removed.csv`'s inverse — filter on
`module_name ~ 'commentar|exposition|catena'` if you want them gone too.

The same applies in reverse to Sefaria's *Duties of the Heart*, *Akeidat
Yitzchak* and similar: filed under `Jewish Thought`, kept, though they are
discursive theology rather than commentary proper.
