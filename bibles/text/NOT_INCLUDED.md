# Notable English translations NOT included, and why

_Current as of revision 5 (73 translations, 2026-10-28)._

This dataset includes every public-domain or freely-licensed (CC0 / CC BY / CC BY-SA)
English Bible translation for which a reliable, verse-segmented machine-readable text was
found — minus, since revision 2 (2026-10-28), spelling/repackage variants that duplicate a
kept translation (listed at the end). The translations below were investigated and
deliberately excluded.

## Excluded by licence (not public domain and not a free licence)

These are translation copyrights whose terms permit some use but are not free licences
(non-commercial, no-derivatives, custom "permission" licences, or all-rights-reserved):

- **NET Bible**, **Lexham English Bible (LEB)**, **Modern Literal Version (MLV)**,
  **International Standard Version (ISV)**, **English Majority Text Version (EMTV)**,
  **A Faithful Version (AFV)**, **The Scriptures 2009 (TS2009)**,
  **EasyEnglish Bible**, **Jubilee Bible 2000**, **Green's Literal Translation (LITV/MKJV)**,
  **King James 2000 (KJ2000)**, **Jonathan [JMNT]**, **God's Word**,
  **Analytical-Literal Translation** and the major commercial translations
  (NIV, ESV, NASB, NRSV, etc.).
- **2001 Translation** (current text is CC BY-NC-ND), **TKJU** (unaltered-only
  distribution), **Lighthouse Bible** (no verifiable licence), and assorted
  "fan revision" KJV edits (VW, BSV, ATM…) without a curated source and a clear free licence.
- 12 further eBible.org English texts classified as restricted during catalogue review
  (per the licence statements on their eBible.org details pages).

## Excluded because no trustworthy verse-parseable text exists

Scans/OCR exist for most of these, but there is no reliable verse-segmented transcription.
Guessing verse boundaries from OCR of blackletter print was judged worse than omitting them:

- ~~**Moffatt New Testament / Bible** (1913–1926)~~ — **now included** (revision 4) as
  `MOFFATT`, from the unrestricted MyBible module `NTM.SQLite3`, which carries the 1913
  NT as one row per verse. This supersedes the earlier notes about the login-gated
  e-Sword module and the unreliable OCR of the margin verse numbers. Moffatt's 1924 Old
  Testament and the full 1926 Bible remain out of scope (no born-digital verse-segmented
  text located).
- **Goodspeed New Testament (An American Translation, 1923)** — **now available as clean
  text** (revision 6 round: studybible.info serves it, one verse per page, no OCR; its
  Matthew is only 0.7 % word-identical to anything in the dataset, so it is a genuinely
  distinct text). It is held out on copyright grounds alone: the 1923 printing is public
  domain in the US since 2019, but the digital text in circulation is the 1925/1937
  edition, which is not verifiably free. It can be added in one build if you want the
  1923 printing treated as PD without edition-level proof.
- **Ferrante Bible** (NT 1900–1904 etc.).
- **Douay-Rheims Bible, original printings** (NT 1582, OT 1609–10) — the *Challoner*
  revision that displaced them IS included (`DRA`).
- **Taverner's Bible** (1539), **Whittingham New Testament** (1557).
- ~~**King James Version, 1611 first-edition spelling**~~ — **now included** (revision 2)
  as `KJV1611`, from a theWord module transcription of the first edition (66 books; the
  Apocrypha as printed in 1611 is represented by the 1769-text `KJVA`). Most "1611" texts
  online are modernised-spelling later editions; this one checks out against first-edition
  readings and spelling ("Heauen", "Iesus", u/v as printed).
- **Wiksource's in-progress Tyndale transcription** (via CrossWire/scrollmapper) currently
  contains only 10 books; the complete surviving Tyndale corpus is included from the
  fuller MySword transcription instead (`Tyndale`).

## Excluded as duplicates (detected at build time)

- **WYCPORTIONS** (ebible `engWycliffe` portions release) — a 99.5%-identical strict subset
  of `WYCLIFFE`; dropped automatically, see `QA_REPORT.md`.
- **RWebster** — a CrossWire redistribution of `Webster` under a different module name.

## Removed in revision 2 deduplication (2026-10-28)

These were in the first release but were removed as spelling/repackage variants of a kept
translation. Similarity = % of verses word-identical to the kept equivalent after light
normalisation (Genesis, Matthew, John, Romans sampled). All remain freely available from
their original sources (see the v1 manifest in git history / `QA_REPORT.md`).

| removed | kept instead | identical |
|---|---|---:|
| `KJV` (1769 text, 66 books) | `KJVA` (same text + Apocrypha) | 100% |
| `KJVPCE` (Pure Cambridge Edition) | `KJVA` | 99.4% |
| `KJVCPB` (Cambridge Paragraph Bible) | `KJVA` | 94.8% |
| `RLT` (Revised Literal Translation) | `KJVA` | 92.5% |
| `WEBC`, `WEBP` (canon subsets of the WEB text) | `WEB` | 96.3% (100% to `WEBU`) |
| `WEBU` (WEB Updated) | `WEB` | 96.3% |
| `WEBBE`, `WEBPB` (British-spelling WEB) | `WEB` | 87.5% |
| `WMBB` (British World Messianic Bible) | `WMB` | 91.4% |
| `NHEBJE`, `NHEBME` (NHEB name variants) | `NHEB` | 95.6% / 87.7% |
| `OEBCW` (Commonwealth-spelling OEB) | `OEBUS` | 94.4% |
| `LXX2012UK` (British-spelling LXX2012) | `LXX2012` | 96.3% |
| `DRC` (Challoner, CrossWire text) | `DRA` (Challoner, American ed.) | 92.4% |

Deliberately **kept** despite family resemblance, as genuinely distinct translations or
editions: `GNV1560`+`GNV1599`, `ASV`+`ASVBT`, `BSB`+`MSB`, `TNT`+`Tyndale`,
`Brenton`+`LXXUP`+`LXX2012`, and the historic KJV revisions (`Webster`, `AKJV`, `UKJV`,
`RNKJV`, `RKJNT`, `JST`).

## Revision 3 check of the user's 250-title candidate list (2026-10-28)

The uploaded `data.csv` was reconciled against revision 2. Three listed titles met the
dataset's licence, distinctness and born-digital verse-segmented-text requirements and
were added: **American Bible Union New Testament** (`ABU1865`), **Worrell New Testament**
(`Worrell`) and **Riverside New Testament** (`RIVERSIDE`). The list's apparent
“Amercian Bible Ballentine Union” entry was not treated as a fourth translation; it
appears to conflate the American Bible Union and Ballantine names for material covered
by the ABU/Riverside entries.

No other title from that list was added in revision 3. Apart from titles already in the
dataset (often under a different name or edition date) and the repetition variants named
above, the remaining entries were modern copyrighted or otherwise non-libre translations,
commentaries/study-Bible packages/harmonies/adaptations rather than distinct translations,
or historic public-domain works for which no reliable born-digital verse-segmented text was
located in the searched catalogues. In particular:

- **Concordant Literal Version** — a module is available, but it does not establish that
  its text is the 1926 first-edition New Testament rather than the later revised CLV,
  for which the publisher asserts copyright. It was therefore not treated as a verified
  public-domain or freely licensed text.
- **Purver's Quaker Bible**, ~~**Whiston's Primitive New Testament**~~ (added in revision 5 —
  see `WIKIDOT_RECONCILIATION.md` and the section below), **Harwood's Liberal
  Translation**, **Wakefield**, **Kneeland**, **George Campbell's Gospels**,
  **Newcome**, **Boothroyd**, **Sharpe**, **Davidson's New Testament**, **J. W. Hanson's
  New Testament**, the **Jewish School and Family Bible**, **John Cheke's Matthew** and
  similar historic candidates remain in the “no trustworthy verse-parseable born-digital
  text found in this search” category; scan/OCR conversion was not used.
- **Moffatt** was later added in revision 4 (see the revision-4 section below); the 1930s
  and later translations on the list that are still in copyright were left out.

## Revision 4 check of the MyBible (ph4.org) English catalogue (2026-10-28)

The 194 Bible rows of the MyBible English module catalogue were screened for pre-1929
public-domain or explicitly free-licensed translations. Two met every rule and were added
from their unrestricted SQLite modules: **Moffatt New Testament** (`MOFFATT`, 1913) and
**Panin Numeric New Testament** (`PANIN`, 1914). Every other row was left out for one of
these reasons:

- **Already present** (usually under another code or edition): Wycliffe, Tyndale,
  Coverdale, Matthew, Great, Bishops', Geneva, KJV/1611/1769 families, Webster, Darby,
  Rotherham, Weymouth, Twentieth Century, Worrell, Montgomery, Noyes, Godbey, Anderson,
  Living Oracles, Murdock, Etheridge, Leeser, JPS, Young, Julia Smith, Diaglott, Riverside,
  BBE, NHEB/WEB/WMB families, OJB, LSV, FBV, ULT/UST, T4T, CPDV, LXX/Brenton, Thomson.
- **Still in copyright, no free licence** — e.g. RSV/NRSV/NASB/NIV/ESV/NKJV/NLT/CEV/NEB/NJB/
  NABRE, Phillips, The Message, Amplified, LEB, ISV, CSB, CEB, EHV, NTE/Wright, TPT,
  Passion, Tree of Life, Names of God, NET, Jubilee, Klingon-style revisions of the KJV such
  as MEV/TMB/BSV, and the modern "literal/updated" revisions (LITV, MLV, KJ3, ALT, DLNT,
  EMTV, WPNT, VW, LBP/Lamsa). Catalogue listing is not licence evidence.
- **Restricted licence terms rather than a free licence** — checked individually:
  **Common Edition NT** (Timothy E. Clontz, 1999) is "all rights reserved", may not be
  altered, may not be sold and caps quotation at 10,000 words / 20% of a sold document;
  **Restored Holy Bible** (RHB) is a copyrighted Webster revision; the **Context Group
  Version** (2010, 66 books) publishes no free licence and its module metadata states none.
  None of these can be redistributed as a full-text dataset.
- **Free licence but not parseable as plain reading text without editorial invention** —
  the **Spoken English New Testament** (J. Webb Mealy, CC BY-SA) is eligible by licence and
  is not a duplicate (≤0.2% identical verses to any kept text), but its module text
  interleaves section headings and book titles inside verse text ("MATTHEW'S ACCOUNT The
  Family Line of Jesus the Messiah This is a record of…") and leaves footnote letters
  attached to words ("servanta", "God-" with a hyphen break). Removing those without
  guessing at boundaries was judged to be text editing rather than format conversion, so it
  was held back; it can be revisited if a clean verse-only export appears.
- **Scanned/OCR or otherwise non-born-digital only** — Goodspeed, Ferrante, Fenton,
  Whiston, Purver, Wakefield, Kneeland, Boothroyd, Sharpe, Davidson, Hanson and the other
  historic titles already listed above; MyBible has no row for Goodspeed, Ferrante, Fenton,
  Whiston, Purver or Wakefield at all. The catalogue's **Concordant** row is dated 1966, not
  the 1926 first edition, so the earlier licence/edition caution stands.
- **Commentary, dictionary, devotional and heading-only modules** were excluded as not being
  verse-segmented translations.

## Revision 5 reconciliation of the Internet Bible Catalog (2026-10-28)

Every entry of <https://bibles.wikidot.com/indexpage> — 1,030 entries on 806 entry pages —
was downloaded and reconciled against this dataset; the full per-entry disposition is in
**`WIKIDOT_RECONCILIATION.md`**. Exactly one pre-1929 title still lacked a born-digital
verse-segmented text and now has one:

- **Whiston's Primitive New Testament (1745)** — added as `WHISTON` (7,957 verses, 27
  books) from the `WhistonNT[1745]` MySword/theWord module. Previously excluded on the
  belief that only page scans existed; the module is plain text, verse-segmented, and
  verified distinct (closest kept translation `KJVA` at 24.0%).

A second source was swept in revision 6: **studybible.info** (162 version codes, 105 of
them English). Every code was scraped and matched against the dataset — the full
disposition is in `STUDYBIBLE_SOURCES.md`. Three texts were both absent and clean:
Mace (1729), Sawyer (1858) and Ottley's Isaiah from the Septuagint (1904) — all added.
Four English texts are clean but still under copyright and are deliberately excluded:
Goodspeed (1925/1937 printing), C. B. Williams (1937), Lamsa (1933) and the Concordant
Literal Version (1926+); the ISV and LEB are excluded as © works with free-looking
distribution but no PD status. One more, `Common` ("The Common Edition", © Timothy E.
Clontz 1999), says "All rights reserved" on its own version page, so it stays out too.

Two further catalogues were swept in revision 7, neither of which yielded text
beyond one title:

- **bibliatodo.com** (English list, 3,520 versions overall) — added **Ioan Tegid's
  Isaiah** (`TEG`, 1830/1842), fetched from the same British & Foreign Bible Society
  edition on bible.com because bibliatodo is behind a Cloudflare challenge. Held out:
  *St Paul from the Trenches 1916* (Cornish, 1–2 Corinthians and Ephesians 1–4:7) — first
  published 1937 and © BFBS 2014 despite the 1916 translation date; and every modern
  version on the list. Disposition of every English entry: `BIBLIATODO_SOURCES.md`.
- **arc.dbs.org / the Digital Bible Society `data` repo** — a publication inventory
  (6,829 records, 241 English, 129 marked public domain). Every public-domain record
  either matches a translation already in the dataset or is a paraphrase, metrical
  psalter or orthography experiment rather than a translation of the running text;
  Taverner's Bible and Cheke's Matthew are catalogued with only page scans behind them.
  Details: `DBS_SOURCES.md`.

Everything else in that catalogue falls into one of four groups, all recorded entry by
entry in `WIKIDOT_RECONCILIATION.md`: already in the dataset (~120 entries, often under a
different code or edition), still in copyright with no free licence (~530), pre-1929 but
scan/OCR only (~330 — OCR remains excluded by rule), or not a translation of the running
text (interlinears, diglots, harmonies, lectionaries, shorthand and dialect editions,
study-Bible annotation). Notable individual findings:

- **Daniel Mace NT (1729)** — a digital module (`Mace.nt.exe`) is advertised on theword.net
  but the host serves only a Windows installer, not the plain-text module, and no other
  born-digital copy was found; the Google Books edition is a scan.
- **E. S. Buchanan (1914)**, **E. W. Bullinger (Job)**, **F. A. Spencer (Gospels, 1898)**,
  **S. T. Byington**, **G. W. Wade**, **J. N. Darby's French/German work**: catalogued, but
  either in copyright (Byington: Watchtower) or scan-only.
- **Provincial-dialect series (Bonaparte, 1856–1863)** — 23 entries for Song of Solomon,
  Ruth, Matthew and the Parables in dialect English/Scots; not translations of the full
  running text and available only as scans.
