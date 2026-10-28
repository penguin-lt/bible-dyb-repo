# Sources, licence findings and dispositions

Everything here was retrieved on **2026-10-28**. For each source: what it is, what
it yielded, and what was done with it.

---

## 1. CrossWire Bible Society SWORD archive — primary source

* Module catalogue: <https://www.crosswire.org/ftpmirror/pub/sword/packages/rawzip/>
  (463 module zips, direct download, no challenge)
* Module metadata: <https://www.crosswire.org/ftpmirror/pub/sword/raw/mods.d.tar.gz>
  (428 `.conf` files; each carries `ModDrv`, `Lang`, `DistributionLicense`,
  `Copyright`, `Description`, `Version`)
* Rendering tool: `mod2imp` from Debian `libsword-utils` 1.9.0 (`apt install
  libsword-utils diatheke`), which dumps a whole module as `$$$KEY` + markup
  blocks regardless of driver.

**Module census.** 428 modules parse; **98 are reference-class** — drivers `zLD`
(47), `RawLD` (18), `RawLD4` (3), `zCom` (29), `zCom4` (7), `RawCom` (5),
`RawGenBook` (39), `RawFiles` (1) — as opposed to the 278 `zText` verse modules
already covered by the bibles dataset.

**Licence policy.** Same rule as the bibles build: public domain, or a licence
that permits redistribution (CC0, CC BY, CC BY-SA, GPL). Distribution-licence
tally across all 428 modules: Public Domain 227, "Permission granted to
CrossWire" 80, free non-commercial 31, blank 16, CC BY-SA 11, CC BY-NC-ND 10,
freely distributable 8, CC BY-NC-SA 7, CC BY 6, GPL 5.

**Result: 96 modules ingested, 52 excluded**, 615,459 entries.

### Ingested (96)

Dictionaries and encyclopedias: `Easton` (1897), `Smith`, `ISBE`
(International Standard Bible Encyclopedia), `AmTract` (American Tract Society),
`CBC` (Condensed Biblical Cyclopedia), `Webster1806`, `Webster1828`,
`Webster1913` (114,712 headwords, the largest single work),
`Hitchcock` (Bible names), `StrongsGreek`, `StrongsHebrew`.

Lexicons and morphology: `AbbottSmith`, `AbbottSmithStrongs`,
`BDBGlosses_Strongs`, `Dodson`, `MLStrong`, `Robinson`, `Packard`, `OSHM`
(Open Scriptures Hebrew Morphology), `FreRobinson`, `FrePackard`,
`VieStrongsGreek`, `VieRobinson`, `Swe1917Of`, `FVDPVietAnh`, `Cawdrey` (1604).

Topical and cross-reference: `Nave`, `Torrey`, `TCR` (Thompson Chain), `TSK`
(Treasury of Scripture Knowledge), `Daily` (Bagster's *Daily Light*), `SME`
(Spurgeon's *Morning and Evening*), `SAOA`, `QuotingPassages`.

Commentaries: `MHC` (Matthew Henry Complete, 39 M characters), `MHCC`,
`CalvinCommentaries`, `Clarke`, `JFB`, `Barnes`, `KD` (Keil & Delitzsch),
`Luther`, `Wesley`, `Lightfoot`, `Burkitt`, `Catena` (Catena Aurea),
`TDavid` (Spurgeon's *Treasury of David*), `Scofield`, `DTN` (Darby notes),
`TFG` (Fourfold Gospel), `PNT` (People's New Testament), `Abbott`,
`VulgGlossa` (Glossa Ordinaria), `Spurious` (Tischendorf), `Sentiment`
(CC BY 4.0 semantic annotation of every verse), `VarApp` (CC0 NT variant
apparatus), `Rieger`, `MAK`, `DutKant`, `FreJer`, `FreChry`, `FreAug`.

Reference and devotional prose (GenBook): `Summa`, `Institutes`, `Josephus`,
`Pilgrim`, `Imitation`, `Practice`, `Passion` (Anne Catherine Emmerich),
`Orthodoxy`, `Heretics`, `Enoch`, `GezEnoch`, `Jubilees`, `Didache`,
`FreDidache`, `FreFlavius`, `FrePilgrim`, `Concord`, `LawGospel`,
`Westminster`, `BaptistConfession1646`, `BaptistConfession1689`,
`DarkNightOfTheSoul`, `Finney`, `JCRHoliness`, `JEAffections`, `JESermons`,
`JOChrist`, `JOCommGod`, `JOGlory`, `JOMortSin`, `EMBReality`, `Phaistos`.

### Excluded (52) — see `modules_excluded.csv` for the machine-readable list

| reason | count | examples |
|---|---|---|
| "Permission to distribute granted to CrossWire" only | 14 | `RWP` (Robertson's Word Pictures — copyrighted), `FreCJE`, `MollColossians`, Portuguese/Russian/Italian/Vietnamese modules |
| Free non-commercial distribution | 10 | `KingComments`, `RWP`, `GreekHebrew`/`HebrewGreek` (Septuagint lexicons), `SBLGNTApp`, `alzat` |
| Blank `DistributionLicense` and no PD statement | 9 | `FreBailly` (copyright line names Chaeréphon), `Family`, `Geneva`, `2BabDict`, `ABS_Essay_GoodSam_SWB`, `Personal`, `br_en`, `en_eu`, `la_en` |
| "Freely distributable" but copyrighted | 8 | `Westminster21`, `FreGBM`, `FreLitCal2025/2026`, `ChisStrongsGreek/Hebrew`, `ChitStrongsGreek/Hebrew` |
| "See README file" | 3 | `ZhEnglish`, `ZhHanzi`, `ZhPinyin` |
| CC BY-NC-ND 4.0 | 2 | `GerStrongsGreek`, `SloHenoh` |
| "Copyrighted" with no grant | 2 | `NETnotesfree`, `GerHfaLex2002` |
| Non-commercial SWORD-format only | 3 | `FreStrongsGreek`, `FreStrongsHebrew`, `FreDAW` |
| Not in the public `rawzip` mirror | 2 | modules listed in `mods.d` but absent from the mirror |

Nothing was excluded for being hard, large, or poorly marked up — only for
licence.

---

## 2. Non-SWORD sources surveyed — findings and dispositions

The brief was to look everywhere, so each candidate was opened and tested rather
than assumed. Results:

### Perseus Digital Library — Liddell-Scott-Jones (`PerseusDL/lexica`)

`https://raw.githubusercontent.com/PerseusDL/lexica/master/CTS_XML_TEI/perseus/pdllex/grc/lsj/grc.lsj.perseus-eng1.xml`
— **HTTP 200, 42.9 MB TEI XML, public domain**, reachable and parseable.
Full LSJ with the Perseus encoding of Greek headwords and English definitions.
This is the single largest genuine lexicon not present in the SWORD archive and
is the next ingest candidate (see `NOT_INCLUDED.md`).

### Open Scriptures

* `openscriptures/strongs` — `strongsgreek.xml` (2.6 MB) and
  `StrongHebrewG.xml` (6.4 MB): the upstream of the SWORD `StrongsGreek` /
  `StrongsHebrew` modules already ingested. **Duplicate of what we have; not
  re-ingested.**
* `openscriptures/HebrewLexicon` — `BrownDriverBriggs.xml` (2.7 MB),
  `HebrewStrong.xml`, `LexicalIndex.xml`, `AugIndex.xml`, plus a pre-built
  `sinri/json/StrongHebrewDictionary.json` (3.7 MB). BDB in full structured
  form. SWORD ships only **BDB glosses** (`BDBGlosses_Strongs`), so the full BDB
  is **additional content**, not a duplicate — next ingest candidate.

### STEPBible (Tyndale House Cambridge) — `STEPBible/STEPBible-Data`

Reachable. Data files: `TBESG` Translators Brief lexicon of Extended Strong's for
Greek (4.7 MB), `TBESH` Hebrew (3.3 MB), `TFLSJ` full LSJ formatted (23.8 MB +
8.4 MB extra), `TIPNR` proper names with every reference (8.2 MB), `MounceGithubTouched`,
`OGNT-Analytical_Lexicon`. Licence: **CC BY 4.0** — free but attribution-required,
so it fits the standing "explicitly free" rule and is flagged accordingly.
Not ingested in this revision; recorded as the highest-value pending non-SWORD
addition alongside LSJ and BDB.

### e-Sword, theWord, MySword (third-party module libraries)

`e-sword.net/downloads.html` — 200, browsable. `theword.net` — 511 (blocked).
`wiki.mysword.info` — no DNS resolution. These libraries mirror a large part of
the same public-domain corpus that CrossWire already distributes (Barnes, Clarke,
JFB, MHCC, Strong's, etc.) and their licence metadata is per-module and often
absent. **Disposition: the same works are already sourced, with better provenance,
from CrossWire; no additional unique public-domain work was identified there.**

### CCEL (Christian Classics Ethereal Library)

`ccel.org` is up (author and index pages return 200, e.g.
`/ccel/easton`), but the old ThML endpoints (`/ccel/easton/ebd.xml`,
`/ccel/easton/ebd.html`) now return **404**; the site has moved to an
application-style URL space. Its public-domain reference corpus is largely the
same works (Easton, Smith, ISBE, Nave, Torrey, Matthew Henry, Calvin, Clarke,
JFB, Barnes, Keil & Delitzsch). **Disposition: no unique work identified; the
SWORD route is cleaner to parse and carries licence metadata.**

### Project Gutenberg

`gutendex.com` API returns **403** to this sandbox's egress. Gutenberg's
reference-adjacent public-domain texts (Smith's Bible Dictionary, Easton, Foxe,
Josephus, etc.) are already covered by the SWORD corpus, and its plain-text files
are not entry-structured. **Disposition: not needed for coverage.**

### Wikisource / Wikidot reconciliation lists

Carried over from the bibles research; used there for translations, not for
reference works. **Disposition: nothing additional for this dataset.**

### Bible Odyssey / Bible Analyzer / other vendor bundles

Vendor bundles repackage the same public-domain works under proprietary
installers without per-work licence statements. **Disposition: rejected on
provenance grounds; identical works already sourced.**

---

## 3. Why SWORD as the backbone

* Every work arrives **born-digital and already entry-segmented** — no OCR, and
  the headword/verse key comes from the module itself, not a guess.
* `DistributionLicense`, `Copyright` and `Version` are recorded **per work**, in
  machine-readable form, alongside the data.
* One uniform ingest path (`mod2imp`) works for lexicons, dictionaries,
  commentaries and general books alike; the only per-work work is markup
  normalisation, which the shared `normalize.py` handles for TEI, OSIS and ThML.
