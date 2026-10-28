# Coverage matrix — the twenty requested areas

Every work in the database is classified against the twenty coverage areas the
brief listed. A work gets one **primary** area and may carry **secondary** areas,
so the totals below overlap where a work genuinely serves two purposes.

Generated from the built manifest by `bibles/reference/pipeline/taxonomy.py`.

| # | area | works | entries | Mchars |
|---|---|---|---|---|
| 1 | Apocrypha & Pseudepigrapha | 63 | 4,115 | 42.1 |
| 2 | Rabbinic Literature & Targums | 1,075 | 43,693 | 86.6 |
| 3 | Patristics & Early Church Fathers | 68 | 20,485 | 156.1 |
| 4 | Textual Criticism & Variants | 4 | 5,998 | 1.9 |
| 5 | Systematic Theology & Dogmatics | 473 | 101,410 | 426.0 |
| 6 | Sermons & Homiletics | 78 | 5,281 | 68.1 |
| 7 | Church History & Historiography | 70 | 829 | 64.3 |
| 8 | Liturgy & Lectionaries | 112 | 2,359 | 22.9 |
| 9 | Historical & Cultural Background | 7 | 8,859 | 24.0 |
| 10 | Maps & Geography | 5 | 90,610 | 8.8 |
| 11 | Cross-Reference Systems | 12 | 94,791 | 25.7 |
| 12 | Morphology & Parsing Data | 11 | 38,734 | 7.7 |
| 13 | Interlinears & Reverse Interlinears | 5 | 33,757 | 11.9 |
| 14 | Hermeneutics & Exegetical Methods | 336 | 101,942 | 284.3 |
| 15 | Reformation & Early Modern Texts | 112 | 42,898 | 147.3 |
| 16 | Creeds & Confessions | 23 | 332 | 12.4 |
| 17 | Mysticism & Asceticism | 174 | 2,629 | 43.5 |
| 18 | Archaeology & Epigraphy | 44 | 6,068 | 7.5 |
| 19 | Apologetics & Polemics | 10 | 129 | 4.1 |
| 20 | Lexical Datasets (Domain/Semantic) | 33 | 398,875 | 92.6 |

**No area is empty.** Four are thin, and the reasons are concrete:

* **Textual Criticism & Variants (4)** — the copyright-free apparatus material in
  reach is limited to Tischendorf's spurious passages, the CC0 NT variant
  apparatus, and the SBLGNT apparatus (which is non-commercial and therefore
  excluded). Fuller critical apparatuses (NA28, UBS5) are copyrighted and will
  never be here.
* **Apologetics & Polemics (10)** and **Historical & Cultural Background (7)** —
  the works exist in CCEL (Butler's *Analogy*, Paley, Lardner, Edersheim,
  Smith's *Bible Dictionary* background articles) but many are classified under
  their primary area (dogmatics or lexicography) and appear as secondary hits.
* **Maps & Geography (5)** — Pleiades contributes 80,413 ancient place names, and
  CCEL carries the geography works, but there is no public-domain *map image*
  corpus here: this dataset is text, so maps arrive as gazetteer text only.

## Where the mass comes from

| source | works | note |
|---|---|---|
| Sefaria (Sefaria-Export) | 1,282 | rabbinics, Targums, Second Temple, liturgy, Kabbalah — the whole English PD corpus |
| Christian Classics Ethereal Library | 741 | patristics (NPNF/ANF), dogmatics, church history, sermons, devotion |
| CrossWire SWORD | 96 | lexicons, dictionaries, commentaries, topical indexes |
| STEPBible / Open Scriptures / OpenBible / Pleiades | 8 | LSJ, BDB, TBESG/TBESH, morphology codes, cross-references, gazetteer |

## Deliberate exclusions

| corpus | why |
|---|---|
| Sefaria CC-BY-NC / CC-BY-NC-SA (103 texts) | non-commercial licence; removed by `repair.py` |
| CCEL works with an empty `DC.Rights` whose print edition is post-1928 | no public-domain basis |
| CCEL image-only volumes (74) | page scans with no extractable text — rejected on the no-OCR rule |
| SBLGNT apparatus, RWP, KingComments, NET notes | copyrighted, non-commercial, or no redistribution grant |
| NA28 / UBS5 / BHS apparatus | copyrighted |
| Internet Archive OCR, Google Books OCR | OCR excluded by standing rule |

## Verification

`bibles/reference/QA_REPORT.md` records the checks: 2,127 works, 795,269 entries,
counts agreeing across the combined file, the 2,127 partitions and the manifest;
no empty text, no null keys, no duplicate keys, no U+FFFD; twenty content spot
checks; and **no non-commercial licence anywhere in the output**.
