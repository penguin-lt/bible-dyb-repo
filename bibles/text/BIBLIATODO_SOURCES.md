# bibliatodo.com as a source — the English catalogue, version by version

Source: <https://www.bibliatodo.com/en/the-bible> (English version list read
2026-10-28). bibliatodo claims 3,520 versions in 2,214 languages; its **English**
list is what matters here. Two facts shaped this round:

1. **The sites' texts are British & Foreign Bible Society (BFBS) digital
   editions.** Their catalogue descriptions quote BFBS verbatim ("digitised for
   the Bible Society in 2021", "digitised with the help of MissionAssist in
   2014"), and the same editions are served by YouVersion.
2. **bibliatodo itself cannot be scraped.** Every page returns a Cloudflare
   challenge (HTTP 403 to plain requests; only a challenge page comes back), and
   its `robots.txt` carries `Content-Signal: ai-train=no`. The identical texts are
   however served, unmetered and verse-segmented, at `bible.com/bible/<id>/…`
   (robots.txt allows those paths), so that is where the text was taken from.
   Fetcher: `pipeline/biblecom_fetch.py`; cache: `pipeline/biblecom_raw/`.

**One English title on that list was missing from the dataset and out of
copyright: John Jones ("Ioan Tegid"), *Isaiah* (1830/1842) — added in revision 7 as
`TEG`.** Everything else is already in the dataset, is a KJV-family respelling,
is in copyright, or is not an English translation of the running text.

## 1. Added in revision 7 (76 → 77 translations)

| bibliatodo entry | id | translator, work | year | rows | YouVersion |
|---|---|---|---:|---:|---|
| *Isaiah 1830 - 1842 (John Jones alias Ioan Tegid)* | `TEG` | John Jones of Bala ("Ioan Tegid"), Isaiah from van der Hooght's Hebrew | 1830 | 1,292 | version 3010, code `TEG` |

Isaiah only, 66 chapters, 1,292 verses, 37,323 words. Scraped from
`data-usfm="ISA.ch.v"` verse spans — no OCR, nothing retyped. Duplicate screen
over Isaiah against all 44 translations that have the book: closest is `KJVA` at
**5.3 %** word-identical verses, then `RNKJV` 4.6 %, `ASV` 4.6 %. A genuinely new
witness.

## 2. Already in the dataset (32 entries)

KJV (Oxford 1769) · KJV with Apocrypha, American edition · KJV American edition ·
KJV 1611 · ASV 1901 · ASV 2015 · RV with Apocrypha 1895 · RV 1885 · Darby ·
YLT 1862 · YLT 1898 · Rotherham 1902 · Twentieth Century NT 1904 · Weymouth ·
Worrell · Godbey · Moffatt NT · Murdock · Emphatic Diaglott · Anderson ·
ABU (`ABU1865`) · Noyes · Julia E. Smith (`SLT`) · Webster 1833 (two entries) ·
CPDV · Douay–Rheims 1899 · Douay–Rheims–Challoner · Geneva 1560/1599 ·
Bishops 1568 · Coverdale 1535 (two entries) · Matthew's 1537 · Great 1539 ·
Wycliffe (1382 and the modern-spelling edition) · Tyndale (NT and 1534 Bible) ·
OJB · WEB · WMB · NHEB · BSB · MSB · BLB · ACV · FBV · PEV · LSV · OEB ·
T4T · CPDV · Text-Critical English NT (`TCENT`) · F35 · OURB · Brenton ·
Leeser · Etheridge · Thomson · Whiston · Wesley · Worsley · Haweis ·
Living Oracles · JPS 1917 · Wycliffe's Bible with Modern Spelling (`WYCMS`,
kept as part of `WYCLIFFE`'s family) · Complete Apostles' Bible (`CAB`, a KJV
repackaging — excluded under the dedup rule, see §3).

## 3. KJV-family respellings and repackagings — excluded by the balanced-dedup rule

Same rule that dropped the KJV/WEB families in revision 2: a modernised KJV is not
a new translation of the text.

`New King James Version` · `Modern King James Version` · `King James 2000` ·
`King James 3 (Literal Translation)` · `American King James Version` ·
`Updated King James Version` · `Revised King James New Testament` ·
`King James Version: Pure Cambridge Edition` · `King James Bible with Strong
Numbers` · `Modern English Version` · `Legacy Standard Bible` ·
`Lighthouse Bible 2006` · `Israeli Authorized Version` · `Hebraic Roots Version` ·
`Hebrew Names Version (HNV)` · `New Heart English Bible (YHWH Sabaoth Edition)` ·
`New Messianic Version Bible` · `Word of Yahweh` · `The Scriptures 1998/2009` ·
`Y'all Version Bible` · `American Standard Version 2015` ·
`English Majority Text Version (2009 and later)` · `The English Standard Version`
(ESV, in copyright anyway) · `Jubilee Bible` · `Scottish Metrical Paraphrases
1781` and `Psalms of David in Metre 1650` (metrical psalms — not the running text).

## 4. Still in copyright — no free licence

`Amplified Bible` (+ Classic) · `Common English Bible` · `Good News Translation`
(+ US, + Good News Bible in four editions) · `God's Word` · `HCSB` · `CSB` (+
Anglicised) · `Lexham English Bible` · `The Message` · `NASB 1995` (+ Strong's,
+ NASB 2020) · `New Century Version` · `NET` · `NIRV` · `NIV` (+ Anglicised) ·
`NLT` · `CEV 1995` (+ 2012, + Interconfessional + the 2006 "conservative" entry) ·
`Easy-to-Read Version` (and `Easy To Read Version`) · `Good News Bible (Catholic
edition)` · `NAB revised` · `NRSV` (+ Catholic Interconfessional, + Updated
Edition 2021) · `RSV` (+ RSV-CI, + two duplicate entries) · `TLV` · `Passion
Translation` · `First Nations Version` · `The Books of the Bible NT` · `Radiate
NT` · `EasyEnglish Bible 2018` · `International Children's Bible` ·
`New Living Translation 2015` · `The Orthodox Jewish Bible 2002` (the dataset's
`OJB` is the 2002 text under its free distribution terms; the 2011 edition listed
here is a later revision and adds nothing).

## 5. Not the running text, or not English

* **Old Testament only:** `Translation into English of Orthodox Yiddish Torah
  (OYTORAH)` — a Yiddish-line interlinear; `The third line … Orthodox Yiddish
  Brit Chadashah` — the same for the NT.
* **Interlinear / study apparatus:** `Interlinear Bible` pages, `Biblical
  Dictionary`, `Bible commentaries`, `Amazing Facts`, `Christian News` etc. are
  not scripture text.
* **Old English:** `Wessex Gospels c. 1175` — pre-1150 West Saxon, outside the
  "English translation" scope used for every other row (and its verses carry
  editorial Latin apparatus); the same text exists on studybible.info.
* **St Paul from the Trenches 1916 (GWC)** — Gerald Warre Cornish's rendering of
  1–2 Corinthians and Ephesians 1–4:7 only. **Held out on licensing, not on
  quality**: the translation was made in 1916 but *first published in 1937 by
  W. Heffer & Sons*, and BFBS's own digital-edition page states "© British and
  Foreign Bible Society 2014". It is also a portion of three epistles.
* **Non-English sections** (Hebrew 6, Greek 22, and the other language blocks on
  the same page) — out of scope.

## Method notes

* Chapter pages were fetched one at a time with `pipeline/biblecom_fetch.py`
  (1.2 s spacing). Verse ids come from `data-usfm`; a verse that the printed
  edition sets as several poetic lines is emitted as several spans with the same
  id, and the fetcher joins them, so the ingested text is the whole verse.
* Isaiah 1–66 were all retrieved (66/66 chapters); no chapter came back short.
* The cache (`pipeline/biblecom_raw/TEG/ISA.json`, 70 KB) is kept so the build
  can be reproduced without re-fetching.
