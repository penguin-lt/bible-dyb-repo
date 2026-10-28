# Coverage matrix — the twenty requested areas

Every work in the database is classified against the twenty coverage areas the
brief listed. A work gets one **primary** area and may carry **secondary** areas,
so the totals below overlap where a work genuinely serves two purposes.

Generated from the built manifest by `bibles/reference/pipeline/taxonomy.py`.

| # | area | works | entries | Mchars |
|---|---|---|---|---|
| 1 | Apocrypha & Pseudepigrapha | 180 | 10,370 | 65.9 |
| 2 | Rabbinic Literature & Targums | 8,275 | 222,576 | 1,113.0 |
| 3 | Patristics & Early Church Fathers | 351 | 33,210 | 230.1 |
| 4 | Textual Criticism & Variants | 139 | 6,910 | 5.3 |
| 5 | Systematic Theology & Dogmatics | 610 | 102,573 | 461.6 |
| 6 | Sermons & Homiletics | 80 | 5,287 | 69.7 |
| 7 | Church History & Historiography | 169 | 3,159 | 119.7 |
| 8 | Liturgy & Lectionaries | 242 | 3,801 | 31.7 |
| 9 | Historical & Cultural Background | 47 | 13,403 | 31.2 |
| 10 | Maps & Geography | 7 | 94,991 | 10.0 |
| 11 | Cross-Reference Systems | 13 | 94,913 | 25.7 |
| 12 | Morphology & Parsing Data | 22 | 126,137 | 32.2 |
| 13 | Interlinears & Reverse Interlinears | 13 | 78,779 | 30.5 |
| 14 | Hermeneutics & Exegetical Methods | 2,972 | 146,879 | 638.3 |
| 15 | Reformation & Early Modern Texts | 122 | 130,276 | 171.8 |
| 16 | Creeds & Confessions | 23 | 332 | 12.4 |
| 17 | Mysticism & Asceticism | 456 | 8,006 | 156.0 |
| 18 | Archaeology & Epigraphy | 138 | 10,885 | 55.0 |
| 19 | Apologetics & Polemics | 10 | 129 | 4.1 |
| 20 | Lexical Datasets (Domain/Semantic) | 47 | 486,301 | 120.3 |

**No area is empty.** Two remain genuinely thin, and the reason is a rights
problem rather than an effort problem:

* **Apologetics & Polemics (10 works, 129 entries)** — the CCEL apologetics shelf
  is largely pre-1929 but the works are classified under dogmatics or church
  history as their *primary* area and appear as secondary hits there. A dedicated
  keyword pass over Butler, Paley, Lardner and Newman's Anglican writings would
  move works, not add text.
* **Textual Criticism & Variants (139 works)** — much improved over v3 (4 works),
  because TAHOT/TAGNT carry the Ketiv/Qere and edition-difference apparatus
  column by column, and 130 Sefaria texts are critical editions with variant
  apparatus. What is still missing is a full critical apparatus proper (NA28,
  UBS5, BHS): copyrighted, and it will not appear.

## Where the mass comes from

| source | works | note |
|---|---|---|
| Sefaria (Sefaria-Export) | 9,016 | 1,282 English in v3 plus 7,734 Hebrew/Aramaic editions: Talmud Bavli and Yerushalmi, Mishneh Torah with its commentaries, Shulchan Arukh, responsa, Midrash, Targums, Zohar |
| Christian Classics Ethereal Library | 741 | patristics (NPNF/ANF), dogmatics, church history, sermons, devotion |
| First Thousand Years of Greek | 282 | 76 Mchars of Greek: Homer, Hesiod, the tragedians, Herodotus, Thucydides, Plato, Aristotle, the Septuagint, Philo, Josephus, apostolic fathers, NT apocrypha |
| CrossWire SWORD | 100 | lexicons, dictionaries, commentaries, topical indexes |
| STEPBible (interlinears) | 10 | TAGNT and TAHOT verse interlinears, plus verse-level morphology and Strong's datasets |
| Open Scriptures · OpenBible · Pleiades | 7 | LSJ, BDB, TEBG/TBESH, 340k cross-references, 80,424 place names |

## Deliberate exclusions

| corpus | why |
|---|---|
| Sefaria CC-BY-NC / CC-BY-NC-SA / CC-BY-NC-ND (783 works) | non-commercial or no-derivative licence; removed by `repair.py` |
| CCEL works with an empty `DC.Rights` whose print edition is 1929 or later (476) | no public-domain basis |
| CCEL image-only volumes (74) | page scans with no extractable text — the no-OCR rule |
| Catholic Encyclopedia (1913) | the born-digital transcription (New Advent) asserts its own copyright; the Wikisource text is OCR-derived, which the no-OCR rule excludes |
| Jewish Encyclopedia (1906) | jewishencyclopedia.com blocks crawlers in `robots.txt`; the Wikisource text is OCR-derived |
| SBLGNT apparatus, RWP, KingComments, NET notes | copyrighted, non-commercial, or no redistribution grant |
| NA28 / UBS5 / BHS apparatus | copyrighted |
| Internet Archive OCR, Google Books OCR, Wikisource `Page:` transcriptions | OCR excluded by standing rule |

Each of the two encyclopedias is a real loss — roughly 25,000 articles between
them — and each is blocked by a different rights problem, not by difficulty. If
you can obtain a public-domain transcription of either (a pre-1929 printed
edition scanned with a text layer by its publisher, for instance), they would slot
straight into the existing pipeline as two more partitions.

## Verification

`bibles/reference/QA_REPORT.md` records the checks: 10,156 works, 1,086,263
entries, counts agreeing across the combined file, the 10,156 partitions and the
manifest; no empty text, no null keys, no duplicate keys, no U+FFFD; twenty
content spot checks; and **no non-commercial or no-derivative licence anywhere in
the output**.
