#!/usr/bin/env python3
"""Build PDF_ONLY_SOURCES.md — pre-1929 English Bible translations for which no
born-digital, verse-segmented text exists (only page scans, or nothing at all).

Sources
  pipeline/research_scan_links.json          Google/IA ids per catalogue page
  pipeline/research_ia_pdf_meta.json         Internet Archive file lists
  pipeline/research_ia_search_groupd.json    IA searches for titles whose
                                             catalogue record lists no scan
  pipeline/research_wikidot_text.json.gz     cached catalogue entry text (806 pages,
                                             gzipped; the raw HTML tree was dropped to
                                             keep the workspace inside its size limit)

Every Internet Archive PDF is range-requested and the file must start with
"%PDF-" before it is printed as a link. Google Books PDF endpoints answered
HTTP 429 from this sandbox, so Google links are records, not downloads, and are
labelled as such.
"""
from __future__ import annotations

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI = "https://bibles.wikidot.com/"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

# slug -> (description, year, kind)
A = {
    "hammond": ("Henry Hammond, A Paraphrase and Annotations Upon all the Books of the New Testament", 1653, "New Testament"),
    "whitby": ("Daniel Whitby, A Paraphrase and Commentary on the New Testament (2 vols)", 1703, "New Testament"),
    "stanhope": ("George Stanhope, A Paraphrase and Comment upon the Epistles and Gospels", 1705, "Lectionary / Gospels & Epistles"),
    "locke": ("John Locke, A Paraphrase and Notes on the Epistles of St. Paul", 1707, "Epistles"),
    "wells": ("Edward Wells, An Help for the more Easy and Clear Understanding of the Holy Scriptures", 1718, "Portions"),
    "nary": ("Cornelius Nary, The New Testament … in the Vulgar English", 1718, "New Testament"),
    "guyse": ("John Guyse, The Practical Expositor, or an Exposition of the New Testament in the Form of a Paraphrase (2nd ed. 1761; the scan is the 1797 printing)", 1761, "New Testament"),
    "purver": ("Anthony Purver, A New and Literal Translation of All the Books of the Old and New Testament", 1764, "Whole Bible"),
    "wynne": ("Richard Wynne, The New Testament: Carefully Collated with the Greek, and Corrected", 1764, "New Testament"),
    "doddridge": ("Philip Doddridge, A Translation of the New Testament (Family Expositor)", 1765, "New Testament"),
    "pyle": ("Thomas Pyle, A Paraphrase on the Acts of the Apostles and the Epistles", 1765, "Portions"),
    "harwood": ("Edward Harwood, A Liberal Translation of the New Testament", 1768, "New Testament"),
    "macknight": ("James Macknight, A Harmony of the Four Gospels / Apostolical Epistles, newly translated", 1756, "New Testament"),
    "wakefield": ("Gilbert Wakefield, A Translation of the New Testament (2 vols)", 1791, "New Testament"),
    "newcome": ("Archbishop William Newcome, An Attempt Toward Revising Our English Translation of the Greek Scriptures", 1796, "New Testament"),
    "scarlett": ("Nathaniel Scarlett, A Translation of the New Testament from the Original Greek", 1798, "New Testament"),
    "geddes": ("Alexander Geddes, The Holy Bible … (Judges–2 Chronicles, Prayer of Manasseh)", 1797, "Old Testament portions"),
    "ray": ("David Macrae / J. M. Ray, A Revised Translation and Interpretation of the Sacred Scriptures (Vol. 1)", 1799, "Old Testament portion"),
    "kneeland": ("Abner Kneeland, The New Testament, being the English only of the Greek and English Testament", 1823, "New Testament"),
    "campbella": ("Alexander Campbell, The Sacred Writings of the Apostles and Evangelists (Living Oracles)", 1826, "New Testament"),
    "campbellg": ("George Campbell, The Four Gospels, translated from the Greek (2 vols)", 1789, "Gospels"),
    "palfrey": ("John Gorham Palfrey, The New Testament in the Common Version, Conformed to Griesbach's Greek", 1828, "New Testament"),
    "shuttleworth": ("Philip Nicholas Shuttleworth, A Paraphrastic Translation of the Apostolic Epistles", 1829, "Epistles"),
    "lingard": ("John Lingard, Roman Catholic NT / Gospels", 1836, "New Testament / Gospels"),
    "penn": ("Granville Penn, The Book of the New Covenant … a critical revision", 1836, "New Testament"),
    "barlee": ("Edward Barlee, A Free and Explanatory Version of the Epistles", 1837, "Epistles"),
    "sharpe": ("Samuel Sharpe, The New Testament translated from Griesbach's Text", 1840, "New Testament"),
    "taylor": ("Edgar Taylor, The New Testament … Revised from the Authorized Version", 1840, "New Testament"),
    "craik": ("Henry Craik, An Amended Translation of the Epistle to the Hebrews", 1847, "Single book"),
    "heinfetter": ("Herman Heinfetter (Frederick Parker), Literal Translations on Definite Rules (Romans, Matthew, Luke, John …)", 1848, "Portions"),
    "whiting": ("N. N. Whiting, The Good News of Our Lord Jesus, the Anointed (from the critical Greek text)", 1849, "New Testament"),
    "kenrick": ("Francis Patrick Kenrick, The Four Gospels translated from the Latin Vulgate", 1849, "Gospels"),
    "cone": ("Spencer Cone / William Wyckoff, The Commonly Received Version of the NT revised", 1850, "New Testament"),
    "livermore": ("Abiel Abbot Livermore, The Epistle to the Romans, with Commentary and Revised Translation", 1854, "Single book"),
    "norton": ("Andrews Norton, A Translation of the Gospels (with notes)", 1855, "Gospels"),
    "jowett": ("Benjamin Jowett, The Epistles of St. Paul to the Thessalonians, Galatians, Romans", 1855, "Epistles"),
    "shadwell": ("Lancelot Shadwell, The Gospel According to Matthew, from a Revised Greek Text", 1859, "Gospel"),
    "colenso": ("J. W. Colenso, St. Paul's Epistle to the Romans newly translated", 1861, "Single book"),
    "thorn": ("Leonard Thorn, The New Testament … as Revised and Corrected by The Spirit of Truth", 1861, "New Testament"),
    "highton": ("Henry Highton, Revised Translation of the New Testament", 1862, "New Testament"),
    "abufirst-first": ("American Bible Union NT — First Revision (Vol. I, Gospels)", 1862, "New Testament portion"),
    "abufirst-quartos": ("American Bible Union NT Quartos (2 Peter, 1–3 John, Jude)", 1852, "Portion"),
    "green": ("Thomas Sheldon Green, The Twofold New Testament", 1865, "New Testament"),
    "abufirst-second": ("American Bible Union NT — Second Revision (text basis of the included ABU1865; this is the scan)", 1865, "New Testament"),
    "htanderson": ("H. T. Anderson, The New Testament Translated From the Original Greek", 1864, "New Testament"),
    "ainslie": ("Robert Ainslie, The New Testament: translated from the Greek Text of Tischendorf", 1869, "New Testament"),
    "godwin": ("John H. Godwin, The Gospel according to Saint Mark. A New Translation", 1869, "Gospel"),
    "bowes": ("John Bowes, The New Testament: Translated from the purest Greek", 1870, "New Testament"),
    "davidson": ("Samuel Davidson, The New Testament. Translated from the Critical Text of Von Tischendorf", 1875, "New Testament"),
    "abufirst-third": ("American Bible Union NT — Third Revision", 1883, "New Testament"),
    "hansonjw": ("J. W. Hanson, The New Covenant (New Testament translation)", 1884, "New Testament"),
    "joynson": ("The New Testament of Our Lord and Saviour Jesus Christ (Joynson, 1892)", 1892, "New Testament"),
    "hayman": ("Henry Hayman, The Epistles of the New Testament in current and popular idiom", 1900, "Epistles"),
    "weekes": ("Robert D. Weekes, The New Dispensation. The New Testament", 1897, "New Testament"),
    "stevens": ("George Barker Stevens, The Epistles of Paul in Modern English", 1898, "Epistles"),
    "rutherford": ("W. G. Rutherford, St. Paul's Epistle to the Romans. A New Translation", 1900, "Single book"),
    "mswiney": ("James M'Swiney, Translation of the Psalms and Canticles", 1901, "Psalms"),
    "smithww": ("William Wye Smith, The New Testament in Braid Scots", 1901, "New Testament (Scots)"),
    "lloyd": ("Samuel Lloyd, The Authorised Version of the New Testament in 'Revised English'", 1904, "New Testament"),
    "kelly": ("William Kelly, The Psalms — A New Version with Short Notes", 1904, "Psalms"),
    "weaver": ("S. Townsend Weaver, The University New Testament in Modern Historical and Literary Form", 1909, "New Testament"),
    "abufirst-bible": ("American Bible Union — Complete Bible, An Improved Edition (1912)", 1912, "Whole Bible"),
    "clarke": ("Edward Clarke, The New Testament. The Authorized Version, Corrected", 1913, "New Testament"),
    "pryse": ("James Morgan Pryse, The Restored New Testament", 1914, "New Testament portions"),
    "abufirst-ot": ("American Bible Union OT Portions (The Book of Job)", 1856, "Old Testament portion"),
    "abufirst-fourth": ("American Bible Union NT — Fourth Revision", 1885, "New Testament"),
    "williams": ("Samuel Williams, The New Testament … translated out of the Greek (1881)", 1881, "New Testament"),
    "way": ("Arthur S. Way, The Letters of St. Paul to Seven Churches and Three Friends", 1901, "Epistles"),
    "moulton": ("Richard G. Moulton, The Modern Reader's Bible (modern literary arrangement)", 1895, "Whole Bible (by book)"),
}

B = {
    "lowth": ("Robert Lowth, Isaiah: A New Translation", 1778),
    "scott": ("Thomas Scott, The Book of Job, in English Verse", 1771),
    "horsley": ("Samuel Horsley, Hosea, Translated from the Hebrew", 1801),
    "lee": ("Chauncey Lee, The Trial of Virtue (paraphrase of Job)", 1806),
    "noyes": ("George R. Noyes, An Amended Version of the Book of Job", 1827),
    "alexander": ("Joseph Addison Alexander, The Psalms Translated and Explained", 1850),
    "moore": ("T. V. Moore, The Prophets of the Restoration (Haggai, Zechariah, Malachi)", 1856),
    "waddell": ("P. Hately Waddell, The Psalms: Frae Hebrew Intil Scottis", 1871),
    "coleman": ("John Noble Coleman, The Poem of Job", 1871),
    "challis": ("James Challis, A Translation of the Epistle to the Romans", 1871),
    "howard": ("John Eliot Howard, The Epistle to the Hebrews. A Revised Translation", 1872),
    "terrot": ("C. H. Terrot, The Epistle to the Romans", 1828),
    "cheyne": ("T. K. Cheyne, The Book of Psalms Translated", 1884),
    "dewitt": ("John De Witt, Praise Songs of Israel (Psalms)", 1884),
    "haley": ("John W. Haley / Lowell Hebrew Club, The Book of Esther, A New Translation", 1885),
    "paley": ("F. A. Paley, The Gospel of St. John; A Verbatim Translation from the Vatican Ms.", 1887),
    "genung": ("John Franklin Genung, The Epic of the Inner Life (Job)", 1891),
    "lewis": ("Agnes Smith Lewis, A Translation of the Four Gospels from the Syriac of the Sinaitic Palimpsest", 1894),
    "driver": ("S. R. Driver, The Parallel Psalter (a new version of the Psalms)", 1898),
    "polychrome": ("Polychrome Bible (The Sacred Books of the Old Testament) — series entry point; the volume scanned here is Leviticus (Driver & White)", 1898),
    "polychrome-isaiah": ("Polychrome Bible — Isaiah (Cheyne)", 1898),
    "polychrome-judges": ("Polychrome Bible — Judges (Moore)", 1898),
    "polychrome-leviticus": ("Polychrome Bible — Leviticus (Driver & White)", 1898),
    "polychrome-psalms": ("Polychrome Bible — Psalms (Wellhausen & Furness)", 1898),
    "polychrome-ezekiel": ("Polychrome Bible — Ezekiel (Toy)", 1899),
    "polychrome-joshua": ("Polychrome Bible — Joshua (Bennett)", 1899),
    "nisbet": ("Murdoch Nisbet, The New Testament in Scots (Purvey's revision in Scots, c. 1520)", 1901),
    "margolis": ("Max L. Margolis, Micah (Holy Scriptures with Commentary)", 1908),
    "glazebrook": ("M. G. Glazebrook, Studies in the Book of Isaiah", 1910),
    "paterson": ("T. Whyte Paterson, The Wyse-Sayin's o' Solomon (Proverbs in Scots)", 1916),
    "mcfadyen": ("John Edgar McFadyen, The Psalms in Modern Speech", 1916),
    "boylan": ("Patrick Boylan, The Psalms (the Vulgate Psalter in the light of the Hebrew)", 1920),
    "ball": ("C. J. Ball, The Book of Job, a revised text and version", 1922),
    # portions whose catalogue page listed no scan; IA copies located by search
    "perowne": ("J. J. Stewart Perowne, The Book of Psalms: A New Translation", 1878),
    "elzas": ("A. Elzas, The Proverbs of Solomon, translated from the Hebrew Text", 1871),
    "kalisch": ("M. M. Kalisch, Historical and Critical Commentary on the Old Testament, with a new translation (Genesis)", 1858),
    "jastrow": ("Morris Jastrow, A Gentle Cynic (Ecclesiastes)", 1919),
    "summer-school": ("The Prophecy of Malachi: a Revised Translation in Parallel Columns with the Authorized Version", 1881),
    "stewart": ("The Psalter: A Revised Edition of the Scottish Metrical Version of the Psalms", 1880),
    "ben-tehillim": ("Ben-Tehillim, The Book of Psalms in English Blank Verse", 1883),
    "baxter": ("Richard Baxter, A Paraphrase on the New Testament, with Notes", 1685),
    "blackmore": ("Richard Blackmore, A Paraphrase on the Book of Job, and on the Songs of Moses, Deborah and David (2nd ed., revised)", 1716),
    "dickinson": ("Rodolphus Dickinson, A New and Corrected Version of the New Testament", 1833),
    "folsom": ("Nathaniel S. Folsom, The Four Gospels: Translated from the Greek text of Tischendorf", 1869),
    "greenfield": ("William Greenfield, The Book of Genesis, in English-Hebrew (interlinear)", 1831),
    "conquest": ("John Conquest, The Holy Bible … with Twenty Thousand Emendations", 1841),
    "ballentine": ("Frank Schell Ballentine, Good News: The Four Gospels in a Modern American Dress", 1897),
    "wade": ("G. Woosung Wade, The Book of Genesis, edited with a revised translation", 1896),
    "thomson-wm": ("William Thomson, The New Testament translated from the Greek (3 vols, 1816)", 1816),
    "dawson": ("Abraham Dawson, A New English Translation … of the Three First Chapters of Genesis", 1763),
}

# Dialect editions. One catalogue page can cover several separate works (the Bonaparte
# series page), and a scan's own title page decides which work it belongs to, so these are
# listed explicitly: slug, description, year, IA identifier, extra Google Books ids.
C_LIST = [
    ("bonaparte-lowland-scotch", "Henry Scott Riddell, The Book of Psalms in Lowland Scotch", 1857,
     "bookofpsalmsinlo00ridd", []),
    ("bonaparte-lowland-scotch", "Henry Scott Riddell, The Song of Solomon in Lowland Scotch", 1860,
     "songsolomoninlo00riddgoog", []),
    ("bonaparte-lowland-scotch", "George Henderson, The Gospel of St. Matthew translated into Lowland Scotch", 1857,
     "gospelofstmatthe00hend", []),
    ("bonaparte", "Henry Scott Riddell, The Gospel of St. Matthew in Lowland Scotch", 1856,
     None, ["leJUAAAAcAAJ"]),
    ("bonaparte-craven", "Henry Anthony Littledale, The Song of Solomon in the Dialect of Craven", 1859,
     None, ["BeBUAAAAcAAJ"]),
    ("bonaparte-lancashire", "James Taylor Staton, The Song of Solomon in the Lancashire Dialect (Bolton)", 1859,
     "songofsolomoninl00statrich", []),
    ("bonaparte-devonshire", "Henry Baird, The Song of Solomon and the Gospel of Matthew in the Devonshire Dialect", 1860,
     None, ["At1UAAAAcAAJ"]),
    ("bonaparte-northumberland", "James Philip Robson, The Song of Solomon versified in the Northumberland Dialect", 1860,
     "songofsolomonver00robs", ["sN1UAAAAYAAJ"]),
]

# Titles that now have a born-digital text (studybible.info, dataset revision 6) and
# so are no longer "scan only"; kept here so a rebuild does not re-list them.
HAS_DIGITAL_TEXT = {
    "mace": "MACE (revision 6, studybible.info)",
    "sawyer": "SAWYER (revision 6, studybible.info)",
    "ottley": "OTTLEY (revision 6, studybible.info)",
    "tegid": "TEG (revision 7, bible.com/BFBS via bibliatodo's catalogue)",
}

# items located through Internet Archive search (catalogue page listed no scan)
IA_OVERRIDE = {
    "alford": ("newtestamentof00alfo", "Henry Alford, The New Testament … newly compared with the original Greek and revised (1878)"),
    "weaver": ("universitynewtes00weav", None),
    "way": ("in.ernet.dli.2015.1221", None),
    "moulton": ("in.ernet.dli.2015.262622", None),
    "perowne": ("cu31924029297482", None),
    "elzas": ("proverbsofsolomo00elzauoft", None),
    "kalisch": ("ahistoricalandc00kaligoog", None),
    "jastrow": ("agentlecynicbei00jastgoog", None),
    "summer-school": ("prophecymalachi00chicgoog", None),
    "stewart": ("psalterarevised00assegoog", None),
    "baxter": ("baxternewtestament", None),
    "whitby": ("paraphrasecoment0000dani", None),
    "stanhope": ("bim_eighteenth-century_a-paraphrase-and-comment_stanhope-george_1726_1", None),
    "campbellg": ("fourgospelstrans02camp", None),
    "abufirst-fourth": ("newtestamentofou00amer_0", None),
    "folsom": ("fourgospelstran00tiscgoog", None),
    "davidson": ("newtestamenttran00davi", None),
    "guyse": ("bim_eighteenth-century_the-practical-expositor_1797_1", None),
    "scarlett": ("bim_eighteenth-century_a-translation-of-the-new_1798", None),
    "ben-tehillim": ("bookofpsalmsinen00edin", None),
    "dawson": ("bim_eighteenth-century_bible-ot-genesis-1-_1763", None),
    "blackmore": ("bim_eighteenth-century_a-paraphrase-on-the-book_1716", None),
}

# Google Books ids recovered from raw page HTML for entries with no IA copy
GOOGLE_OVERRIDE = {
    "conquest": "HVdbAAAAQAAJ",
    "greenfield": "YjQvqf7r4jwC",
}

# Titles for which neither a scan nor a digital text could be found anywhere
NO_COPY = [
    ("Richard Turnbull", "The Epistles of Paul the Apostle, An Original Translation", 1854),
    ("Charles Wellbeloved", "The Holy Bible, A New Translation (Pentateuch and more)", 1838),
    ("T. C. Joynson", "The New Testament of Our Lord and Saviour Jesus Christ (Liverpool, 1892)", 1892),
    ("Cornelius Nary", "The New Testament … in the Vulgar English (1718) — the catalogue lists it, but no digitised copy was found in IA, Google Books or HathiTrust", 1718),
    ("Henry Hayman", "The Epistles of the New Testament in current and popular idiom (1900)", 1900),
    ("Samuel Williams", "The New Testament … translated out of the Greek (1881)", 1881),
    ("S. C. Malan / other privately printed NTs", "Privately printed 19th-century revisions with no located copy", 1880),
    ("J. M. Rodwell", "The Book of Job, translated from the Hebrew (2nd ed.)", 1868),
    ("M. Letteris", "The Story of Esther (Hebrew/English)", 1852),
    ("J. McReynolds", "Word Study Greek-English New Testament", 1785),
    ("C. H. Toy and other Polychrome volumes", "Numbers, Deuteronomy, Samuel, Kings, Jeremiah, Hosea–Malachi, etc. (Polychrome Bible volumes not digitised as PDFs)", 1898),
    ("The Five Clergymen", "The Gospel According to St. John, after the Authorized Version, newly compared", 1858),
]


def verify(ident: str, fname: str):
    url = f"https://archive.org/download/{ident}/{fname}"
    for u in (url,):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90) as r:
                head = r.read(16)
                if head.startswith(b"%PDF"):
                    return url, True
                return url, False
        except Exception:
            # some items 500 on the download host; try the item's own server
            try:
                meta = json.loads(urllib.request.urlopen(
                    urllib.request.Request(f"https://archive.org/metadata/{ident}",
                                           headers=UA), timeout=60).read())
                srv, d = meta.get("server"), meta.get("dir")
                alt = f"https://{srv}{d}/{fname}"
                with urllib.request.urlopen(urllib.request.Request(alt, headers=UA), timeout=90) as r:
                    return alt, r.read(16).startswith(b"%PDF")
            except Exception:
                return url, False


def pick_ia(slug, scan, iam, desc):
    if slug in IA_OVERRIDE:
        ident = IA_OVERRIDE[slug][0]
        if not ident.startswith(("bwb_", "unset", "isbn_")):
            m = iam.get(ident)
            if m is None:
                try:
                    m = json.loads(urllib.request.urlopen(
                        urllib.request.Request(f"https://archive.org/metadata/{ident}",
                                               headers=UA), timeout=60).read())
                    m = {"pdf": [f["name"] for f in m.get("files", []) if f["name"].lower().endswith(".pdf")]}
                except Exception:
                    m = None
            if m and m.get("pdf"):
                full = [p for p in m["pdf"] if not p.endswith("_text.pdf")] or m["pdf"]
                return ident, full[0]
    ids = scan.get(slug, {}).get("ia", [])
    want = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", desc)}
    scored = []
    for i in ids:
        m = iam.get(i)
        if not m or not m.get("pdf"):
            continue
        title = (str(m.get("title", "")) + " " + str(m.get("creator", ""))).lower()
        full = [p for p in m["pdf"] if not p.endswith("_text.pdf")] or m["pdf"]
        scored.append((sum(1 for w in want if w in title), i, full[0]))
    if not scored:
        return None
    scored.sort(key=lambda t: (-t[0], t[1]))
    return scored[0][1], scored[0][2]


def main() -> int:
    scan = json.loads((ROOT / "pipeline/research_scan_links.json").read_text())
    iam = json.loads((ROOT / "pipeline/research_ia_pdf_meta.json").read_text())

    entries = []
    for group, table in (("A", A), ("B", B)):
        for slug, row in table.items():
            desc, year = row[0], row[1]
            kind = row[2] if len(row) > 2 else ("Old Testament portion" if group == "B" else "Dialect edition")
            if slug in IA_OVERRIDE and IA_OVERRIDE[slug][1]:
                desc = IA_OVERRIDE[slug][1]
            entries.append({"group": group, "slug": slug, "desc": desc, "year": year,
                            "kind": kind, "ia": pick_ia(slug, scan, iam, desc),
                            "google": [GOOGLE_OVERRIDE[slug]] if slug in GOOGLE_OVERRIDE
                            else scan.get(slug, {}).get("google", [])})

    for slug, desc, year, ident, gids in C_LIST:
        entries.append({"group": "C", "slug": slug, "desc": desc, "year": year,
                        "kind": "Dialect edition", "ia": None, "google": list(gids),
                        "_fix_ia": ident})

    for e in entries:
        ident = e.pop("_fix_ia", None)
        if not ident:
            continue
        m = iam.get(ident)
        if m is None:
            try:
                raw = json.loads(urllib.request.urlopen(
                    urllib.request.Request(f"https://archive.org/metadata/{ident}",
                                           headers=UA), timeout=60).read())
                m = {"pdf": [f["name"] for f in raw.get("files", []) if f["name"].lower().endswith(".pdf")]}
            except Exception:
                m = None
        if m and m.get("pdf"):
            full = [p for p in m["pdf"] if not p.endswith("_text.pdf")] or m["pdf"]
            e["ia"] = (ident, full[0])

    todo = [e for e in entries if e["ia"]]
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(lambda e: verify(e["ia"][0], e["ia"][1]), todo))
    for e, (url, ok) in zip(todo, res):
        e["pdf_url"], e["ok"] = url, ok
    for e in entries:
        if not e["ia"]:
            e["pdf_url"], e["ok"] = None, False

    ok = [e for e in entries if e.get("ok")]
    nopdf = [e for e in entries if not e.get("ok")]
    google_only = [e for e in nopdf if e["google"]]
    nothing = [e for e in nopdf if not e["google"]]
    entries.sort(key=lambda e: (e["year"], e["desc"]))

    L = []
    add = L.append
    add("# Pre-1929 English Bible translations with **no digital text** — PDF / scan links")
    add("")
    add("_Compiled 2026-10-28 from the Internet Bible Catalog "
        "([bibles.wikidot.com](https://bibles.wikidot.com/indexpage), all 1,030 entries on 806 "
        "pages read). Each title was searched for a born-digital, verse-segmented text in "
        "eBible.org, CrossWire/SWORD, MySword, MyBible (ph4.org), theWord-modules.com (196 "
        "module pages), gratis.bible, Zefania, Project Gutenberg (GUTINDEX.ALL, Oct 2026), "
        "bolls.life, GitHub and the commercial module sites — and, since revision 6, "
        "the studybible.info parallel-text library (162 version codes, see "
        "`STUDYBIBLE_SOURCES.md`). None was found: the only known witness is a page "
        "scan, or nothing at all._")
    add("")
    add(f"- **{len(ok)}** entries with a **verified** downloadable PDF (link resolved and the "
        f"response begins `%PDF-`)")
    add(f"- **{len(google_only)}** entries whose only located copy is a **Google Books record** "
        "(its PDF endpoint refused this sandbox with HTTP 429 — the link is a catalogue entry, "
        "not a tested download)")
    add(f"- **{len(nothing)}** entries where no digital copy of any kind was found (they are "
        "repeated in section D so that the list is complete on its own)")
    add(f"- **{len(NO_COPY)}** further titles with **no copy anywhere** (listed at the end)")
    add("")
    add("> ⚠️ **Scans are page images with an OCR text layer — not clean text.** Measured on "
        "Whiston 1745, the one volume where both forms are available: the scan's text layer "
        "recovers **61.6 %** of the correct words (long-s → f, w → vv, one text object per "
        "word, running heads and catchwords mixed into verses), against **99.7 %** from a "
        "born-digital PDF. Every entry here needs OCR correction or manual transcription "
        "before it can enter the dataset. That is why they are excluded from it.")
    add("")
    add("Links: **PDF** = direct download (HTTP-verified) · **Item** = Internet Archive details "
        "page (DjVu text, other formats, sometimes a better scan) · **Google** = Google Books "
        "record · **Catalog** = the wikidot entry with full bibliographic detail. Years are "
        "publication dates; where the catalogue is inconsistent the printing described in its "
        "`Date:` line is used.")
    add("")

    def row(e):
        bits = []
        if e.get("ok"):
            ident = e["ia"][0]
            bits.append(f"[PDF]({e['pdf_url']}) · [Item](https://archive.org/details/{ident})")
        elif e["ia"]:
            ident = e["ia"][0]
            bits.append(f"[Item](https://archive.org/details/{ident}) (PDF returned an error)")
        for g in e["google"][:2]:
            bits.append(f"Google [{g}](https://books.google.com/books?id={g})")
        bits.append(f"[Catalog]({WIKI}{e['slug']})")
        return f"| {e['desc']} | {e['year']} | {e['kind']} | " + " · ".join(bits) + " |"

    for gid, title, blurb in (
        ("A", "A. New Testaments and whole Bibles",
         "Complete or substantially complete translations of the New Testament, and whole Bibles."),
        ("B", "B. Single books and portions",
         "Psalters, Prophets, Job, Gospels, Epistles and other single-book translations, including "
         "the Polychrome Bible fascicles."),
        ("C", "C. Dialect editions",
         "Nineteenth-century Scots and English-dialect renderings (Bonaparte series and similar)."),
    ):
        add(f"## {title}")
        add("")
        add(blurb)
        add("")
        add("| Translation | Year | Extent | Links |")
        add("|---|---|---:|---|")
        for e in [x for x in entries if x["group"] == gid]:
            add(row(e))
        add("")

    add("## D. No copy located anywhere")
    add("")
    add("These titles are recorded in the catalogue with full bibliographic detail but no scan "
        "or digital text could be found in any of the searched repositories:")
    add("")
    add("| Translator / work | Title | Year |")
    add("|---|---|---:|")
    for who, what, year in NO_COPY:
        add(f"| {who} | {what} | {year} |")
    add("")

    add("## Deliberately not listed — a digital text does exist")
    add("")
    add("**Taverner's Bible (1539)** and **John Cheke's Matthew (1550)** appear in the "
        "Digital Bible Society inventory but still have only page scans behind them, so "
        "they stay scan-only (see `DBS_SOURCES.md`).")
    add("")
    add("**Mace 1729**, **Sawyer 1858** and **Ottley 1904** were on this list in earlier "
        "revisions and are no longer: studybible.info serves all three as born-digital, "
        "verse-segmented text, and they are now in the dataset (`MACE`, `SAWYER`, "
        "`OTTLEY` — see `STUDYBIBLE_SOURCES.md`). The scans linked here for them were "
        "never ingested.")
    add("")
    add("Already in the dataset, so a scan is not the only route: Wycliffe/Purvey, Tyndale, "
        "Coverdale, Matthew, Great, Bishops', Geneva, the KJV families, Webster, Darby, "
        "Rotherham, Weymouth, Twentieth Century NT, Worrell, Worsley, Wesley, Haweis, Living "
        "Oracles (Campbell), Godbey, Noyes (complete Bible), Murdock, Etheridge, Leeser, "
        "JPS 1917, Young, Julia E. Smith, Emphatic Diaglott, Brenton, Thomson, Riverside, "
        "Montgomery, Moffatt, Panin, American Bible Union (2nd revision), ACV, LSV, FBV, "
        "ULT/UST, T4T, NHEB/WEB/WMB, CPDV, OJB, BBE. **Whiston 1745** is the same case — its "
        "scan exists but the module text is already in the dataset.")
    add("")
    add("Still in copyright in the US, so neither scan nor module is a lawful ingestion route: "
        "Goodspeed (1923), Torrey (1933), C. B. Williams (1937), Westminster Version, Knox, "
        "Conf raternity / CCD, the 1969 Kingdom Interlinear, Newberry, Scofield, the Numerical "
        "Bible, Kent's Historical Bible, Byington (Watchtower, 1972) and the modern versions.")
    add("")
    add("## How the links were checked")
    add("")
    add("Each Internet Archive item was resolved through its metadata API, the full PDF file "
        "name read from that metadata, and the file requested directly; a link is printed as a "
        "**PDF** only when the response began with `%PDF-`. Items that answered with an error "
        "are shown as **Item** links so the record is still reachable. Google Books PDF "
        "downloads could not be tested: every endpoint (`books.google.com/books/download/…`, "
        "the country mirrors, and title-based URLs) returned HTTP 429 from this sandbox, and "
        "the Books API likewise; only the `jscmd=SearchWithinVolume2` endpoint answered, which "
        "yields snippets rather than text. Titles whose catalogue page listed no scan at all "
        "were searched through the Internet Archive advanced-search API.")
    add("")
    add("Machine-readable data: `pipeline/research_scan_links.json`, "
        "`pipeline/research_ia_pdf_meta.json`, `pipeline/research_ia_search_groupd.json`, "
        "`pipeline/research_no_digital_copy.json`; the builder is "
        "`pipeline/build_pdf_only_list.py`.")
    add("")

    out = ROOT / "PDF_ONLY_SOURCES.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes) — verified PDFs {len(ok)}, "
          f"Google-only {len(google_only)}, nothing {len(nothing)}")
    for e in nothing:
        print("   no link:", e["slug"], e["desc"][:60])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
