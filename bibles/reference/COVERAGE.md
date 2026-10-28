# Coverage matrix — the twenty requested areas

Every work in the database is classified against the twenty coverage areas the
brief listed. A work gets one **primary** area and may carry **secondary** areas,
so the totals below overlap where a work genuinely serves two purposes.

Generated from the built manifest by `bibles/reference/pipeline/taxonomy.py`.
The classifier is idempotent: it reads only the source's own description of a
work, never its previous classification.

| # | area | works | entries | Mchars |
|---|---|---|---|---|
| 1 | Apocrypha & Pseudepigrapha | 140 | 10,248 | 61.4 |
| 2 | Rabbinic Literature & Targums | 7,434 | 216,871 | 1071.7 |
| 3 | Patristics & Early Church Fathers | 92 | 21,047 | 163.3 |
| 4 | Textual Criticism & Variants | 139 | 6,910 | 5.3 |
| 5 | Systematic Theology & Dogmatics | 691 | 16,813 | 293.0 |
| 6 | Sermons & Homiletics | 79 | 5,285 | 69.7 |
| 7 | Church History & Historiography | 111 | 1,914 | 71.8 |
| 8 | Liturgy & Lectionaries | 220 | 3,409 | 31.3 |
| 9 | Historical & Cultural Background | 42 | 13,373 | 31.0 |
| 10 | Maps & Geography | 7 | 94,991 | 10.0 |
| 11 | Cross-Reference Systems | 13 | 94,913 | 25.7 |
| 12 | Morphology & Parsing Data | 22 | 126,137 | 32.2 |
| 13 | Interlinears & Reverse Interlinears | 13 | 78,779 | 30.5 |
| 14 | Hermeneutics & Exegetical Methods | 2,891 | 309,575 | 869.9 |
| 15 | Reformation & Early Modern Texts | 122 | 130,276 | 171.8 |
| 16 | Creeds & Confessions | 23 | 332 | 12.4 |
| 17 | Mysticism & Asceticism | 394 | 7,777 | 155.8 |
| 18 | Archaeology & Epigraphy | 4 | 5,938 | 3.3 |
| 19 | Apologetics & Polemics | 10 | 129 | 4.1 |
| 20 | Lexical Datasets (Domain/Semantic) | 55 | 504,748 | 144.6 |

**No area is empty.** Three are thin, and in each case the reason is external:

* **Archaeology & Epigraphy (4 works)** — CCEL's archaeological shelf is small and
  what exists (Edersheim, Smith's dictionary articles, the Palestine Exploration
  Fund volumes) is classified under background or lexicography. A dedicated
  corpus would have to come from a new source; excavation reports are rarely
  public domain or born-digital.
* **Apologetics & Polemics (10 works)** — the works are present (Butler, Paley,
  Lardner, Newman's Anglican volumes) but their primary area is dogmatics or
  church history, so they appear as secondary hits rather than being counted here.
* **Textual Criticism & Variants (139 works, 5.3 Mchars)** — the free apparatus
  material is Tischendorf, the CC0 NT apparatus, and the Ketiv/Qere columns of
  TAHOT. NA28/UBS5/BHS are copyrighted and will not appear.

## Where the mass comes from

| source | works | note |
|---|---|---|
| Sefaria (Sefaria-Export) | 8,003 | Talmud Bavli and Yerushalmi, Mishneh Torah and its commentaries, Shulchan Arukh, responsa, Midrash, Targums, Zohar — English **and** the Hebrew/Aramaic originals |
| Christian Classics Ethereal Library | 740 | patristics (NPNF/ANF), dogmatics, church history, sermons, devotion |
| First Thousand Years of Greek | 282 | 76 Mchars of Greek: Homer, Plato, the Septuagint, Philo, Josephus, apostolic fathers |
| CrossWire SWORD | 99 | lexicons, dictionaries, commentaries, topical indexes |
| STEPBible (interlinears) | 10 | TAGNT/TAHOT verse interlinears, verse-level morphology and Strong's |
| Open Scriptures · OpenBible · Pleiades | 7 | LSJ, BDB, TBESG/TBESH, 340k cross-references, 80,424 place names |

## Deliberate exclusions

| corpus | why |
|---|---|
| Sefaria CC-BY-NC / -SA / -ND (783 works) | non-commercial or no-derivative licence |
| CCEL works with an empty `DC.Rights` whose print edition is 1929 or later (476) | no public-domain basis |
| CCEL image-only volumes (74) | page scans with no extractable text — the no-OCR rule |
| 1,015 exact duplicates | same text under two version titles (Sefaria publishes many works twice, page-split and merged); one copy kept, listed in `data/dedupe_report.csv` |
| Catholic Encyclopedia (1913) | the born-digital transcription asserts its own copyright; the Wikisource text is OCR-derived |
| Jewish Encyclopedia (1906) | site blocks crawlers; Wikisource text is OCR-derived |
| SBLGNT apparatus, RWP, KingComments, NET notes | copyrighted or non-commercial |
| NA28 / UBS5 / BHS apparatus | copyrighted |
| Internet Archive / Google Books OCR | OCR excluded by standing rule |

## Verification

`bibles/reference/QA_REPORT.md` lists the defects found in audit. Two scripts must
pass before a release:

* `verify.py` — counts agreeing across the combined file, the partitions and the
  manifest; no empty or duplicate keys; canonical licences only.
* `audit.py` — the same invariants plus random row sampling: residual markup,
  template and entity residue, control bytes, char_count accuracy, language
  against script, and identical-text detection across partitions.
