# Internet Bible Catalog (bibles.wikidot.com) — reconciliation against this dataset

_Source: <https://bibles.wikidot.com/indexpage>, fetched 2026-10-28. The page lists
1,030 entries (translations, editions, and translator names) across 806 linked entry
pages; every entry page was downloaded and read._

## Result of the reconciliation

| Outcome | Count |
|---|---:|
| Catalogue entries recorded in this dataset (`wikidot_catalogue.csv`) | 1,030 |
| Distinct entry pages read (`pipeline/research_wikidot_text.json.gz`) | 806 |
| **Added in revision 5** | **1 — `WHISTON`** |
| Already in the dataset (same text, under another code/edition) | ~120 entries |
| Still in copyright, no free licence | ~530 entries |
| Pre-1929 but no born-digital verse-segmented text (scans/OCR only) | ~330 entries |
| Portions, dialects, interlinears, lectionaries, commentaries, study Bibles | remainder |

Machine-readable working files (kept in `pipeline/`): `wikidot_catalogue.csv`
(entry + link), `wikidot_pages_meta.csv` (per-page first/max year, date lines,
contents, external text links), `research_wikidot_text.json.gz` (the 806 cached
pages as plain text; the raw HTML tree was 22.7 MB and was dropped to keep the
workspace small),
`theword_modules_meta.csv` + `research_wayback_nt_names.txt` (module inventory
used to look for digital texts of the gaps).

## The addition

**`WHISTON` — William Whiston, *Mr. Whiston's Primitive New Testament* (1745)**, 7,957
verses / 27 books / 178,194 words. Public domain (published 1745). Text: the
`WhistonNT[1745]` MySword/theWord module (one line per NT verse slot, born-digital, no
OCR). Distinct from every kept translation: closest existing is `KJVA` at 24.0%
word-identical verses (normalised), far below the ~90%+ that identified the revision-2
duplicates. It supersedes the previous "no trustworthy text" note: this text is
verse-segmented and complete, and the Internet Archive scan
(<https://archive.org/details/primitivenewtest00whisuoft>) was used only to confirm
identification, never as the source.

## Why the other pre-1929 titles were not added

**1. Already in the dataset** (often under a different code or edition): Wycliffe/Purvey,
Tyndale (incl. the Hexapla text), Coverdale, Matthew, Great, Bishops', Geneva 1557/1560/1599,
KJV families (1611, 1769, Cambridge, Clarified, 21st Century, 2000, Updated, Restored Name,
American), Webster (1833 and RWB), Darby, Rotherham, Weymouth, Twentieth Century (incl.
the 1898–1901 preliminary edition), Worrell, Worsley, Wesley, Haweis, Living Oracles,
Anderson, Godbey, Noyes, Murdock, Etheridge, Leeser, JPS 1917, Young (1862/1898), Julia
E. Smith, Diaglott, Riverside, Montgomery, Moffatt, Panin, American Bible Union (all four
revisions form the basis of the ABU text already added; only the second revision is the
full NT), Brenton/Septuagint texts, Thomson, BBE, CPDV, OJB, LSV, FBV, ULT/UST, T4T,
NHEB/WEB/WMB families, ACV, RNKJV, AKJV, UKJV, RKJNT, JST (Inspired Version), Emphasized
Bible, Concordant (1966 edition — see NOT_INCLUDED.md), Third Millennium Bible, Lamsa.

**2. Pre-1929 public domain but only scans exist — OCR is excluded by rule.** These are
catalogued at wikidot with Internet Archive / Google Books / HathiTrust page images and no
verse-segmented digital text was found in any searched catalogue (eBible.org, CrossWire,
MyBible/ph4, theWord-modules, gratis.bible, Zefania, Project Gutenberg, bolls.life):

Ainslie (NT, 1865) · Alexander (Psalms, 1850) · Alford (NT, 1869) · Ballentine (Gospels,
1892) · Barlee (Epistles, 1837) · Baxter (NT, 1615) · Belsham (NT/Epistles, 1817) ·
Benisch · Blackmore (Job) · Boothroyd · Bowes (1804) · Boylan (Psalms, 1920) · Brady & Tate
(Psalms, 1696) · Braga (Psalter, 1915) · Buchanan (Gospels, 1914) · Bullinger (Job, 1903) ·
Cassirer (NT, 1903) · Challis (Romans) · Cheke (Matthew) · Chenault (NT, 1922) ·
Clementson (NT, 1880) · Coleman (Job) · Colenso (Romans) · Conant · Conquest ·
Crickmer · Davidson · DeWitt · Doddridge · Ferrar Fenton · Gardiner · Genung · Godwin ·
Greenfield · J. W. Hanson (NT, 1883) · Harwood (1768) · Heinfetter · Howard · Kelly ·
Kneeland (1727) · Livermore · Locke · Mace (1729)* · Magil · Margolis (1908) ·
McFadyen (1916) · Newcome (1796/1817) · Nisbet · Palfrey · Penn (1817) ·
Powis Smith (OT, 1927) · Pryse (1914) · Purver (1764) · Pyle · Ramsay (1911) ·
Renan (Job) · Rodwell (Job) · Rutherford (Romans, 1900) · Sawyer (1858) · Scott (Job) ·
Shadwell · Sharpe (NT, 1834) · Shuttleworth · William Wye Smith (NT, 1901) ·
Spencer (Gospels, 1898) · Spurrell (OT, 1885) · Stanhope · Stevens (Paul, 1898) ·
Stewart (Psalms) · Taylor (NT, 1793) · Terrot · Thorn (NT, 1861) · Torrey (Gospels) ·
Turnbull · Waddell (Psalms) · Wade (Genesis) · Wakefield (NT, 1795/1820) ·
Walmesley · Way · Weaver (NT, 1909) · Weekes · Wellbeloved · Wells · Whitby ·
Whiting · Williams (NT, 1881) · Charles B. Williams (NT, 1937 – not PD) · Wiseman ·
Wynne (1764) · and the Bonaparte provincial-dialect series (23 dialect Soots/English
versions of Song of Solomon, Ruth, Matthew and the Parables).

\* Daniel Mace's 1729 NT is the one case where a digital module is advertised
(`Mace.nt.exe` on theword.net) but the file hosts only a Windows installer, not the plain
text module, and no other born-digital copy was located; the Google Books edition is a scan.

**3. Still in copyright, no free licence** (the bulk of the modern catalogue): RSV/NRSV/
NRSVA/NRSV-CE, NASB/NASU/NASB 2020, NIV/TNIV/NIrV, ESV/ESV-UK, NKJV, NLT, CEV/CEVD, NEB,
REB, NJB, NABRE, NAB, TLV, NOG, CJB, TPT, The Message, Amplified, LEB, ISV, CSB, HCSB, CEB,
EHV, NTE/Wright, NET, GW/GWN, NCV/ICB, NLV, ERV, GNT/GNB, TLB, Phillips, Barclay, Knox,
Byington (Watchtower), NWT, Weymouth revisions, Wuest, Williams (1937), Cassirer (1989 ed.),
Koren, ArtScroll/Stone, Alter, Fox, Stern, Swaggart, Scofield notes, and the many
modern "literal/updated" revisions of the KJV (MEV, TMB, KJ3, LITV, MLV, ALT, DLNT, EMTV,
WPNT, VW, Lighthouse, BSV, KJ2000, MKJV, KJV-Clarified).

**4. Not translations of the text** — interlinears, diglots, harmonies, lectionaries,
shorthand editions, dialect curiosities, study-Bible annotations, devotional paraphrases,
commentaries and book-length treatments catalogued alongside the translations.
