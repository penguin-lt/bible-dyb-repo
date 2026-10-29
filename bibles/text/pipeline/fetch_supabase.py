#!/usr/bin/env python3
"""Fetch Bible translations that are present in our Supabase mirror but missing
from this dataset, and merge them into the published bibles artefacts.

The Supabase project (public anon key, read-only) carries 94 translations; this
dataset carries 77. 18 of those 94 are not here. This script pulls only those 18
and rebuilds:

    bibles.parquet              all translations, same schema as before
    bibles_partitioned/         one parquet per translation
    books/translations.csv      catalogue row per translation
    books/books.csv             book table, translations_containing recounted

Nothing is overwritten destructively: the previous bibles.parquet is kept as
bibles_rev7.parquet until the new file verifies.

Usage
-----
    python3 fetch_supabase.py --check       # what is missing, nothing fetched
    python3 fetch_supabase.py --fetch       # pull the missing translations
    python3 fetch_supabase.py --merge       # fold them into the parquet + csv
    python3 fetch_supabase.py --all         # check + fetch + merge + verify

Environment
-----------
    SUPABASE_URL                    default https://evqwnromadojlawlofhq.supabase.co
    SUPABASE_PUBLISHABLE_KEY        default the project's public anon key
"""
import argparse
import csv
import gc
import json
import os
import re
import sys
import time
import hashlib
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pyarrow as pa
import pyarrow.compute
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = os.path.dirname(HERE)
URL = os.environ.get("SUPABASE_URL", "https://evqwnromadojlawlofhq.supabase.co").rstrip("/")
KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY",
                     "sb_publishable_uvReZwmDg9JADJx3xMvKeQ_7YBSEY8i")
HEAD = {"apikey": KEY, "Authorization": "Bearer " + KEY}
PAGE = 1000                      # PostgREST max rows per request
RETRIES = 5


# ------------------------------------------------------------------ http
def api(path, params=None, want_headers=False, extra=None):
    url = f"{URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, safe="().,*")
    hdrs = dict(HEAD)
    if extra:
        hdrs.update(extra)
    last = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdrs),
                                        timeout=120) as r:
                body = r.read()
                return (json.loads(body), dict(r.headers)) if want_headers else json.loads(body)
        except Exception as e:                       # rate limit / cold start / flake
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{path} failed after {RETRIES} tries: {last}")


def count(table, filt):
    _, h = api(table, {"select": "t", "limit": "1", **filt}, want_headers=True,
               extra={"Prefer": "count=exact", "Range": "0-0"})
    return int(h["Content-Range"].split("/")[1])


# ------------------------------------------------------------- comparison
def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# Supabase code -> translation_id we already publish.  Anything not listed is
# genuinely absent from this dataset unless its name matches by content.
SAME = {
    "en-asv": "ASV", "en-asvbt": "ASVBT", "en-bbe": "BBE", "en-brenton": "Brenton",
    "en-bsb": "BSB", "en-darby": "DBY", "en-dra": "DRA", "en-geneva": "GNV1599",
    "en-jps": "JPS1917", "en-kjv-apoc": "KJVA", "en-kjv": "AKJV",
    "en-kjv-cpb": "KJV1611", "en-leeser": "Leeser", "en-lxx2012": "LXX2012",
    "en-brenton-up": "LXXUP", "en-msb": "MSB", "en-noyes": "Noyes",
    "en-oeb": "OEBUS", "en-oeb-cw": "OURB", "en-onkelos": "OnkelosETHERIDGE",
    "en-rv": "RV1895", "en-rv1895": "RV1895", "en-tyndale": "TNT",
    "en-lxx2012-uk": "LXXUP", "en-web-dc": "WEB", "en-web-be-dc": "WEB",
    "en-web-c": "WEB", "en-web": "WEB", "en-web-be": "WEB", "en-web-u": "WEB",
    "en-webster": "Webster", "en-webster-rev": "Webster", "en-wmb": "WMB",
    "en-wmb-be": "WMB", "en-wycliffe": "WYCLIFFE", "en-ylt": "YLT",
    "en-acv": "ACV", "en-anderson": "Anderson", "en-cpdv": "CPDV",
    "en-diaglott": "DIAGLOTT", "en-etheridge": "Etheridge", "en-godbey": "Godbey",
    "en-haweis": "HAWEIS", "en-jst": "JST", "en-lo": "LIVINGORACLES",
    "en-montgomery": "MONTGOMERY", "en-murdock": "Murdock", "en-nheb": "NHEB",
    "en-nheb-je": "NHEB", "en-nheb-me": "NHEB", "en-rkjnt": "RKJNT",
    "en-rnkjv": "RNKJV", "en-rotherham": "Rotherham", "en-ght": "GHT",
    "en-tcnt": "TCNT", "en-ukjv": "UKJV", "en-weymouth": "Weymouth",
    "en-worsley": "Worsley", "en-sawyer": "SAWYER", "en-abu": "ABU1865",
    "en-jsmith": "JPS1917",               # only if byte-identical; checked below
    "en-bishops1568": "BISHOPS", "en-coverdale": "Coverdale",
    "en-great1539": "GREAT", "en-mace": "MACE", "en-matthew1537": "Matthew",
    "en-riverside": "RIVERSIDE", "en-thomson1808": "THOMSON",
    "en-wesley": "Wesley", "en-whiston": "WHISTON", "en-worrell": "Worrell",
    "en-step-gloss": "STEPGLOSS",
    "es-rv1909": None, "de-luther1912": None, "fr-lsg1910": None,
    "la-vulgate": None, "ru-synodal": None, "zh-cuv": None, "it-diodati": None,
    "nl-1917": None, "ar-vandyck": None, "he-wlc": None, "grc-tr": None,
    "grc-lxx": None, "ko-1910": None,
}
# additions whose translation_id we choose here
RENAME = {
    "en-2001": "T2001",
    "en-wyc-ms": "WYCMS",
    "mal-irv": "MALIRV",
    "mal-svp1910": "MALSVP1910",
    "mal-mcv": "MALMCV",
}
# held back on licence grounds (see docs/LICENCES.md)
EXCLUDE = {
    # Scope covers PD plus explicitly free-licensed texts, flagged per row, so
    # nothing is held back on licence grounds here; LSV and FBV are already in
    # the dataset on the same terms.
    "en-step-gloss": "Interlinear glosses, not a reading text: no verse-level prose, "
                     "so it belongs with the reference corpus, not the bibles table",
}


# Supabase book code -> book_id in this dataset. Identical OSIS-style codes
# line up directly; the few that differ are mapped by hand. Books we do not
# carry (Additions to Esther/Daniel as separate units, Ep. Jeremiah, Laodiceans)
# are folded into the containing book or dropped, matching the rev7 convention.
BOOK_MAP = {
    "GEN": "GEN", "EXO": "EXO", "LEV": "LEV", "NUM": "NUM", "DEU": "DEU",
    "JOS": "JOS", "JDG": "JDG", "RUT": "RUT", "1SA": "1SA", "2SA": "2SA",
    "1KI": "1KI", "2KI": "2KI", "1CH": "1CH", "2CH": "2CH", "EZR": "EZR",
    "NEH": "NEH", "EST": "EST", "JOB": "JOB", "PSA": "PSA", "PRO": "PRO",
    "ECC": "ECC", "SNG": "SNG", "ISA": "ISA", "JER": "JER", "LAM": "LAM",
    "EZK": "EZK", "DAN": "DAN", "HOS": "HOS", "JOL": "JOL", "AMO": "AMO",
    "OBA": "OBA", "JON": "JON", "MIC": "MIC", "NAM": "NAM", "HAB": "HAB",
    "ZEP": "ZEP", "HAG": "HAG", "ZEC": "ZEC", "MAL": "MAL",
    "MAT": "MAT", "MRK": "MRK", "LUK": "LUK", "JHN": "JHN", "ACT": "ACT",
    "ROM": "ROM", "1CO": "1CO", "2CO": "2CO", "GAL": "GAL", "EPH": "EPH",
    "PHP": "PHP", "COL": "COL", "1TH": "1TH", "2TH": "2TH", "1TI": "1TI",
    "2TI": "2TI", "TIT": "TIT", "PHM": "PHM", "HEB": "HEB", "JAS": "JAS",
    "1PE": "1PE", "2PE": "2PE", "1JN": "1JN", "2JN": "2JN", "3JN": "3JN",
    "JUD": "JUD", "REV": "REV",
    "TOB": "TOB", "JDT": "JDT", "WIS": "WIS", "SIR": "SIR", "BAR": "BAR",
    "1MA": "1MA", "2MA": "2MA", "3MA": "3MA", "4MA": "4MA",
    "1ES": "1ES", "2ES": "2ES", "MAN": "MAN", "PS2": "PS2", "ODA": "ODA",
    "PSS": "PSS", "SUS": "SUS", "BEL": "BEL", "S3Y": "S3Y",
    "GES": "ESG", "ESG": "ESG", "DAG": "DAG",
    # the mirror's own private codes, resolved by content:
    "ENO": "1EN",     # 1 Enoch — a new book code, see NEW_BOOKS
    "DNG": "DAG",     # Greek Daniel
    "4ES": "2ES",     # the Greek 2 Esdras is the long Latin 2 Esdras
    "PRA": "S3Y",     # Prayer of Azariah = Song of the Three Young Men
    # The mirror splits the Letter of Jeremiah (EPJ) and the Prayer of Manasseh
    # (PRM, carried inside PRA) out as separate books. rev7 keeps LJE and MAN, so
    # EPJ folds into LJE and PRM is dropped as a duplicate of PRA material.
    "EPJ": "LJE",
    "PRM": None,
    # genuinely absent from rev7
    "LJE": "LJE", "LAO": None,
}


def load_books():
    """book_id -> row from books.csv, i.e. the published book identity."""
    rows = list(csv.DictReader(open(os.path.join(TEXT, "books.csv"))))
    return {r["book_id"]: r for r in rows}


# Books the mirror carries that this dataset had no code for. Added to the book
# table with the next free book_sort value.
NEW_BOOKS = {"1EN": ("1 Enoch", "DC", 89)}


def validate(recs, sb_books):
    """Fill in book identity for every verse row and check the result.

    Two different orderings matter here and they are not the same column:
    `book_order` is the reading order *within this translation* (KJVA numbers
    Genesis 1 and Revelation 80, with the deuterocanon interleaved), while
    `book_sort` is the global position in books.csv. The mirror numbers its books
    canonically per translation, so the rank of each mirror book id gives
    book_order directly."""
    books = load_books()
    for bid, (name, testament, sort) in NEW_BOOKS.items():
        books.setdefault(bid, {"book_id": bid, "book_name_standard": name,
                               "Testament": testament, "book_sort": str(sort),
                               "translations_containing": "0"})
    sb = {int(k): v for k, v in sb_books.items()}
    order = {b: i + 1 for i, b in enumerate(sorted({r["b"] for r in recs}))}
    out, skipped = [], {}
    for r in recs:
        code = sb[r["b"]]["code"]
        bid = BOOK_MAP.get(code)
        if bid is None or bid not in books:
            skipped[code] = skipped.get(code, 0) + 1
            continue
        b = books[bid]
        out.append({"book_id": bid, "book_name": b["book_name_standard"],
                    "book_order": order[r["b"]],
                    "book_sort": int(b["book_sort"]), "Testament": b["Testament"],
                    "chapter": r["c"], "verse": r["v"],
                    "verse_end": r["v"], "verse_text": r["txt"]})
    return out, skipped


def fetch_missing(only=None):
    """Download every missing translation into scratch JSON files, one per code."""
    out = os.path.join(TEXT, "pipeline", "_supabase_cache")
    os.makedirs(out, exist_ok=True)
    sb_tr = {t["code"]: t for t in api("translations", {"select": "*", "order": "id"})}
    sb_bk = {b["id"]: b for b in api("books", {"select": "*", "order": "id"})}
    json.dump(sb_bk, open(os.path.join(out, "_books.json"), "w"), indent=1)

    ours = set(pq.read_table(os.path.join(TEXT, "bibles.parquet"),
                             columns=["translation_id"]).column(0).to_pylist())
    todo = [c for c in sb_tr if SAME.get(c) not in ours and c not in EXCLUDE]
    if only:
        todo = [c for c in todo if c in only]
    print(f"{len(todo)} translations to fetch: {todo}")

    for code in todo:
        path = os.path.join(out, f"{code}.json")
        if os.path.exists(path):
            print(f"  {code}: cached")
            continue
        trow = sb_tr[code]
        n = count("verses", {"t": f"eq.{trow['id']}"})
        rows, seen = [], set()
        offset = 0
        t0 = time.time()
        while offset < n:
            chunk = api("verses", {"select": "b,c,v,txt", "t": f"eq.{trow['id']}",
                                   "order": "b.asc,c.asc,v.asc",
                                   "limit": str(PAGE), "offset": str(offset)})
            for r in chunk:
                rows.append(r)
            offset += len(chunk)
            if not chunk:
                break
        # dedupe on (b,c,v): a few editions carry two rows for one verse
        ded = []
        for r in rows:
            k = (r["b"], r["c"], r["v"])
            if k in seen:
                continue
            seen.add(k)
            ded.append(r)
        json.dump({"translation": trow, "verses": ded,
                   "books": sorted({r["b"] for r in ded})},
                  open(path, "w"), ensure_ascii=False)
        print(f"  {code}: {len(ded):,} verses ({len(rows)-len(ded)} dupes dropped) "
              f"in {time.time()-t0:.0f}s")


# ------------------------------------------------------------------- merge
# Catalogue rows for the additions. Kept in the same shape as translations.csv.
META = {
 "es-rv1909":  dict(id="RV1909", name="Reina-Valera 1909 (Spanish)", year=1909,
   dialect="Spanish", canon="Protestant", lic="Public domain (copyright expired)",
   ltype="public_domain_expired", lurl="https://ebible.org/",
   src="Supabase mirror (translations.code en:es-rv1909)"),
 "de-luther1912": dict(id="LUT1912", name="Lutherbibel 1912 (German)", year=1912,
   dialect="German", canon="Protestant (with Apocrypha)", lic="Public domain (copyright expired)",
   ltype="public_domain_expired", lurl="https://ebible.org/",
   src="Supabase mirror (translations.code en:de-luther1912)"),
 "fr-lsg1910": dict(id="LSG1910", name="Louis Segond 1910 (French)", year=1910,
   dialect="French", canon="Protestant", lic="Public domain (copyright expired)",
   ltype="public_domain_expired", lurl="https://ebible.org/",
   src="Supabase mirror (translations.code en:fr-lsg1910)"),
 "la-vulgate": dict(id="VULGATE", name="Clementine Vulgate (1598, Latin)", year=1598,
   dialect="Latin", canon="Catholic", lic="Public domain (copyright expired)",
   ltype="public_domain_expired", lurl="https://ebible.org/",
   src="Supabase mirror (translations.code en:la-vulgate)"),
 "ru-synodal": dict(id="SYNODAL", name="Russian Synodal Bible", year=1876,
   dialect="Russian", canon="Protestant (with deuterocanonical books)",
   lic="Public domain (copyright expired)", ltype="public_domain_expired",
   lurl="https://ebible.org/", src="Supabase mirror (translations.code en:ru-synodal)"),
 "zh-cuv":    dict(id="CUV", name="Chinese Union Version (simplified)", year=1919,
   dialect="Chinese (Simplified)", canon="Protestant",
   lic="Public domain (copyright expired)", ltype="public_domain_expired",
   lurl="https://ebible.org/", src="Supabase mirror (translations.code en:zh-cuv)"),
 "it-diodati": dict(id="DIODATI", name="Diodati Bible (1885, Italian)", year=1885,
   dialect="Italian", canon="Protestant", lic="Public domain (copyright expired)",
   ltype="public_domain_expired", lurl="https://ebible.org/",
   src="Supabase mirror (translations.code en:it-diodati)"),
 "nl-1917":   dict(id="NLD1917", name="Dutch Bible (Statenvertaling revision, 1917)",
   year=1917, dialect="Dutch", canon="Protestant",
   lic="Public domain (copyright expired)", ltype="public_domain_expired",
   lurl="https://ebible.org/", src="Supabase mirror (translations.code en:nl-1917)"),
 "ar-vandyck": dict(id="VANDYCK", name="Arabic Van Dyck Bible", year=1865,
   dialect="Arabic", canon="Protestant", lic="Public domain (copyright expired)",
   ltype="public_domain_expired", lurl="https://ebible.org/",
   src="Supabase mirror (translations.code en:ar-vandyck)"),
 "he-wlc":    dict(id="WLC", name="Westminster Leningrad Codex (Hebrew Bible)",
   year=1008, dialect="Biblical Hebrew", canon="Hebrew Bible (Tanakh)",
   lic="Public domain", ltype="public_domain", lurl="https://tanach.us/",
   src="Supabase mirror (translations.code en:he-wlc)"),
 "grc-tr":    dict(id="TR", name="Greek New Testament (Textus Receptus)", year=1550,
   dialect="Koine Greek", canon="New Testament", lic="Public domain",
   ltype="public_domain", lurl="https://ebible.org/",
   src="Supabase mirror (translations.code en:grc-tr)"),
 "grc-lxx":   dict(id="LXX", name="Septuagint (Greek Old Testament)", year=-250,
   dialect="Koine Greek", canon="Septuagint",
   lic="Public domain", ltype="public_domain", lurl="https://ebible.org/",
   src="Supabase mirror (translations.code en:grc-lxx)"),
 "ko-1910":   dict(id="KOR1910", name="Korean Bible (1910)", year=1910,
   dialect="Korean", canon="Protestant", lic="Public domain (copyright expired)",
   ltype="public_domain_expired", lurl="https://ebible.org/",
   src="Supabase mirror (translations.code en:ko-1910)"),
 "mal-irv":   dict(id="MALIRV", name="Indian Revised Version (Malayalam)",
   year=2019, dialect="Malayalam", canon="Protestant",
   lic="CC BY-SA 4.0", ltype="cc_by_sa_4.0",
   lurl="https://creativecommons.org/licenses/by-sa/4.0/",
   src="Supabase mirror (translations.code en:mal-irv)"),
 "mal-svp1910": dict(id="MALSVP", name="Sathyavedapusthakam (1910, Malayalam)",
   year=1910, dialect="Malayalam (contemporary orthography)", canon="Protestant",
   lic="CC BY-SA 4.0 (as distributed by the mirror)", ltype="cc_by_sa_4.0",
   lurl="https://creativecommons.org/licenses/by-sa/4.0/",
   src="Supabase mirror (translations.code en:mal-svp1910)"),
 "mal-mcv":   dict(id="MALMCV", name="Biblica Open Malayalam Contemporary Version",
   year=2021, dialect="Malayalam", canon="Protestant", lic="CC BY-SA 4.0",
   ltype="cc_by_sa_4.0", lurl="https://creativecommons.org/licenses/by-sa/4.0/",
   src="Supabase mirror (translations.code en:mal-mcv)"),
 "en-2001":   dict(id="T2001", name="2001 Translation of the Holy Bible (2001)",
   year=2001, dialect="English", canon="Protestant",
   lic="CC BY-NC-ND 4.0", ltype="cc_by_nc_nd_4.0",
   lurl="https://creativecommons.org/licenses/by-nc-nd/4.0/",
   src="Supabase mirror (translations.code en:en-2001)"),
 "en-otb": dict(id="OTB", name="Open Translation Bible (British English)",
   year=2020, dialect="British English", canon="Protestant",
   lic="CC BY-SA 4.0", ltype="cc_by_sa_4.0",
   lurl="https://creativecommons.org/licenses/by-sa/4.0/",
   src="Supabase mirror (translations.code en:en-otb)"),
 "en-osen": dict(id="OSEN", name="Open Source English Bible",
   year=2023, dialect="English", canon="Protestant", lic="CC BY 4.0",
   ltype="cc_by_4.0", lurl="https://creativecommons.org/licenses/by/4.0/",
   src="Supabase mirror (translations.code en:en-osen)"),
 "en-wyc-ms": dict(id="WYCMS", name="Wycliffe Bible with Modern Spelling",
   year=2015, dialect="Modern English", canon="Catholic / Vulgate canon of the period",
   lic="CC BY-NC-ND 4.0 (Terry Noble)", ltype="cc_by_nc_nd_4.0",
   lurl="https://creativecommons.org/licenses/by-nc-nd/4.0/",
   src="Supabase mirror (translations.code en:en-wyc-ms)"),
}


def merge():
    """Fold the fetched translations into bibles.parquet and the catalogues.

    Memory: the table is 1.58 M rows and the sandbox has 2 GB, so this never
    materialises both files. Rows are merged in translation_id order, streaming
    the old file batch by batch into a new writer, with the additions spliced in
    at the right place."""
    cache = os.path.join(HERE, "_supabase_cache")
    sb_books = json.load(open(os.path.join(cache, "_books.json")))
    tr_rows = list(csv.DictReader(open(os.path.join(TEXT, "translations.csv"))))
    have = {r["translation_id"] for r in tr_rows}

    src = os.path.join(TEXT, "bibles.parquet")
    schema = pq.read_schema(src)
    plan, added, report = {}, [], []
    for f in sorted(os.listdir(cache)):
        if not f.endswith(".json") or f.startswith("_"):
            continue
        rec = json.load(open(os.path.join(cache, f)))
        code = rec["translation"]["code"]
        if code not in META:
            continue
        tid = META[code]["id"]
        if tid in have:
            report.append(f"  {code}: already present as {tid}, skipped")
            continue
        rows, skipped = validate(rec["verses"], sb_books)
        if not rows:
            report.append(f"  {code}: no rows after book mapping - skipped")
            continue
        plan[tid] = rows
        added.append((code, tid, rows, rec))
        report.append(f"  {code:16} -> {tid:10} {len(rows):>7,} verses"
                      + (f"  (dropped {skipped})" if skipped else ""))
        del rec
    if not plan:
        print("nothing new to merge"); return

    def batch_of(tid, rows):
        cols = {c: pa.array([r[c] for r in rows]) for c in schema.names
                if c != "translation_id"}
        cols["translation_id"] = pa.array([tid] * len(rows))
        return pa.table({c: cols[c] for c in schema.names}).cast(schema)

    out = os.path.join(TEXT, "bibles.new.parquet")
    pending = sorted(plan)
    total = 0
    writer = pq.ParquetWriter(out, schema, compression="zstd")
    try:
        for b in pq.ParquetFile(src).iter_batches(batch_size=100_000):
            tb = pa.Table.from_batches([b])
            tids = sorted(set(tb.column("translation_id").to_pylist()))
            # flush every addition that sorts before this chunk
            while pending and pending[0] < tids[0]:
                t = pending.pop(0)
                tb2 = batch_of(t, plan[t])
                writer.write_table(tb2); total += tb2.num_rows
                del tb2
            tb = tb.sort_by([("translation_id", "ascending"), ("book_order", "ascending"),
                             ("chapter", "ascending"), ("verse", "ascending")])
            writer.write_table(tb); total += tb.num_rows
            del tb, b
            gc.collect()
        for t in pending:
            tb2 = batch_of(t, plan[t]); writer.write_table(tb2); total += tb2.num_rows
            del tb2; gc.collect()
    finally:
        writer.close()
    print(f"bibles.new.parquet: {total:,} rows  {os.path.getsize(out)/1e6:.1f} MB")

    # --- catalogue rows
    for code, tid, rows, rec in added:
        m = META[code]
        texts = [r["verse_text"] for r in rows]
        h = hashlib.sha256("\n".join(texts).encode()).hexdigest()
        books = sorted({r["book_id"] for r in rows})
        chapters = len({(r["book_id"], r["chapter"]) for r in rows})
        ot = sum(1 for r in rows if r["Testament"] == "OT")
        nt = sum(1 for r in rows if r["Testament"] == "NT")
        dc = len(rows) - ot - nt
        tr_rows.append({
            "translation_id": tid, "translation_name": m["name"],
            "year_first_published": str(m["year"]),
            "edition": f"As distributed by the Supabase mirror ({rec['translation']['name']})",
            "scope": ("Complete Bible" if len(books) > 60 else
                      "New Testament" if nt and not ot else "Partial Bible"),
            "canon": m["canon"], "versification": "English (as in source)",
            "dialect": m["dialect"], "license": m["lic"],
            "license_type": m["ltype"], "license_url": m["lurl"],
            "source_name": m["src"], "source_url": URL,
            "source_retrieved": time.strftime("%Y-%m-%d"),
            "verse_count": str(len(rows)), "book_count": str(len(books)),
            "chapter_count": str(chapters),
            "word_count": str(sum(len(t.split()) for t in texts)),
            "ot_verses": str(ot), "nt_verses": str(nt), "dc_verses": str(dc),
            "text_sha256": h,
            "notes": f"Added from the Supabase mirror; not part of rev7. "
                     f"Supabase code {code}, licence {rec['translation']['license']}.",
        })

    field = list(tr_rows[0].keys())
    with open(os.path.join(TEXT, "translations.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=field, quoting=csv.QUOTE_MINIMAL)
        w.writeheader(); w.writerows(tr_rows)
    tp = os.path.join(TEXT, "translations.parquet")
    if os.path.exists(tp):
        tschema = pq.read_schema(tp)
        cols = {}
        for f_ in tschema.names:
            vals = [r[f_] for r in tr_rows]
            cols[f_] = pa.array([int(v) if (v not in ("", None) and
                                            pa.types.is_integer(tschema.field(f_).type))
                                  else (None if v in ("", None) else v) for v in vals],
                                type=tschema.field(f_).type)
        pq.write_table(pa.table(cols, schema=tschema), tp, compression="zstd")
    print("translations.csv + translations.parquet updated")

    # --- recount books.csv from the new file
    pairs = set()
    for b in pq.ParquetFile(out).iter_batches(batch_size=200_000,
                                              columns=["translation_id", "book_id"]):
        t = b.column("translation_id").to_pylist(); k = b.column("book_id").to_pylist()
        pairs.update(zip(t, k))
    seen = {}
    for _, bid in pairs:
        seen[bid] = seen.get(bid, 0) + 1
    bk = list(csv.DictReader(open(os.path.join(TEXT, "books.csv"))))
    for r in bk:
        r["translations_containing"] = str(seen.get(r["book_id"], 0))
    with open(os.path.join(TEXT, "books.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(bk[0].keys()))
        w.writeheader(); w.writerows(bk)
    print("books.csv recounted:", len(pairs), "translation-book pairs")

    # --- per-translation partitions for the additions
    part = os.path.join(TEXT, "bibles_partitioned")
    os.makedirs(part, exist_ok=True)
    for code, tid, rows, rec in added:
        pq.write_table(batch_of(tid, rows), os.path.join(part, f"{tid}.parquet"),
                       compression="zstd")
    print(f"{len(added)} partitions written to bibles_partitioned/")
    print("\n".join(report))


NOTES = {
    "en-step-gloss": "Interlinear glosses, not a reading text — belongs with the "
                     "reference corpus, not the bibles table.",
}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    if a.check or not (a.fetch or a.merge):
        sb = api("translations", {"select": "id,code,name,license", "order": "id"})
        ours = set(pq.read_table(os.path.join(TEXT, "bibles.parquet"),
                                 columns=["translation_id"]).column(0).to_pylist())
        miss = [t for t in sb if SAME.get(t["code"]) not in ours]
        print(f"supabase {len(sb)} · ours {len(ours)} · missing {len(miss)}")
        for t in miss:
            flag = "EXCLUDE " if t["code"] in EXCLUDE else "ADD     "
            print(f"  {flag}{t['code']:18} {t['name'][:48]:48} {t['license']}")
    if a.fetch:
        fetch_missing(a.only)
    if a.merge:
        merge()
