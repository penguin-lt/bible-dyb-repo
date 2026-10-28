"""Ingest the Christian Classics Ethereal Library (CCEL) as reference works.

CCEL publishes each book as one ThML XML file (`/ccel/<author>/<work>.xml`) plus
Dublin Core metadata inside it: `DC.Title`, `DC.Creator`, `DC.Rights`,
`DC.Subject`, `DC.Language`.  Structure is flat — `<div1>` chapters containing
`<p>` paragraphs — and citations are `<scripRef passage="Jas 1:19">Jas 1:19</scripRef>`.

Only works whose `DC.Rights` says Public Domain are ingested; everything else is
recorded in /tmp/ccel_skipped.json with the rights string that excluded it.

Mapping to the shared ten-column schema:
    module_id    `<author>_<work>` (CCEL's own identifier)
    entry_key    the div1 title, else "chapter N"
    book_id/chapter/verse   parsed when a chapter is a single scripture passage
    category     from DC.Subject, see category_of()

    python3 ccel_harvest.py --survey        # enumerate + classify, no download
    python3 ccel_harvest.py --limit 20      # trial run
    python3 ccel_harvest.py                 # full run
"""
import argparse
import json
import os
import re
import string
import sys
import time
import urllib.error
import urllib.request

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from normalize import clean  # noqa: E402
from harvest import SCHEMA, OUT  # noqa: E402

UA = {"User-Agent": "bible-reference-harvest/1.0 (+https://github.com/penguin-lt/bible-dyb-repo)"}
BASE = "https://www.ccel.org/ccel/"
INDEX = "https://www.ccel.org/index/title/"
CACHE = os.environ.get("REF_CACHE", "/home/user/scratch/cache/ccel")

CATEGORY_RULES = [
    ("Patristics", ("early church", "fathers of the church", "apostolic fathers",
                    "ante-nicene", "nicene", "post-nicene", "patristic",
                    "christian literature, early")),
    ("Church History", ("church history", "history of the christian church",
                        "historiography", "reformation", "crusades", "missions",
                        "history of doctrines")),
    ("Sermons", ("sermon", "homilet", "preaching", "discourse")),
    ("Liturgy", ("liturg", "worship", "hymn", "prayer book", "sacrament", "psalter")),
    ("Devotional", ("devotional", "mystic", "ascetic", "meditation",
                    "christian life", "piety", "consolation", "prayer")),
    ("Creeds & Confessions", ("creed", "confession", "catechism", "articles of religion",
                              "westminster standards")),
    ("Commentary", ("commentary", "exposition", "annotation", "exegetical",
                    "bible. n.t.", "bible. o.t.", "testament", "notes",
                    "epistle", "gospel", "expositor")),
    ("Theology", ("theology", "dogmatic", "doctrine", "systematic", "apologetic",
                  "polemic", "philosophy", "ethics")),
    ("Reference", ("dictionary", "encyclopedia", "lexicon", "concordance",
                   "reference", "biography", "literature")),
]


def classify(subjects, title, desc=""):
    blob = " ".join(subjects + [title, desc[:400]]).lower()
    for cat, keys in CATEGORY_RULES:
        if any(k in blob for k in keys):
            return cat
    return "Reference"


def classify_refined(parsed):
    """DC.Subject drives this when it is informative; the title breaks the tie.

    CCEL slaps the same broad LCSH on thousands of books ("Christianity",
    "Early Christian Literature"), so a plain keyword scan over subject+title
    puts Barnes' commentary in "Reference".  Prefer the specific LCSH heads and
    only fall back to the title.
    """
    subjects = [x for x in parsed["subjects"]
                if x.lower() not in ("christianity", "religion", "theology",
                                     "all; proofed;", "classic;")]
    cat = classify(subjects, parsed["module_name"])
    if cat == "Reference":                     # nothing specific in the subjects
        cat = classify([], parsed["module_name"])
    return cat


def fetch(url, path, timeout=180):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 500:
        return path
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r, open(path, "wb") as fh:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    return path


def enumerate_works():
    """All (author, work) slugs from CCEL's title index."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "works.json")
    if os.path.exists(path):
        return json.load(open(path))
    works = {}
    for L in string.ascii_uppercase:
        h = fetch(INDEX + L, os.path.join(CACHE, "idx_" + L + ".html")).__str__()
        h = open(h, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r'<a href="/ccel/([a-z0-9_]+)/([a-z0-9_]+)\.html">\s*([^<]{0,120})', h):
            works.setdefault(f"{m.group(1)}/{m.group(2)}", " ".join(m.group(3).split()))
    json.dump(works, open(path, "w"), indent=1)
    return works


DC = re.compile(r"<DC\.([A-Za-z]+)([^>]*)>(.*?)</DC\.\1>", re.S)


def dc_meta(xml):
    meta = {}
    for tag, attrs, val in DC.findall(xml):
        sub = re.search(r'sub="([^"]+)"', attrs)
        key = tag.lower() + ("_" + sub.group(1).lower().replace(" ", "_") if sub else "")
        meta.setdefault(key, []).append(" ".join(val.split()))
    return {k: (v[0] if len(v) == 1 else v) for k, v in meta.items()}


DIV1 = re.compile(r'<div1\b([^>]*)>(.*?)(?=<div1\b|</ThML\.body>)', re.S)
ATTR = re.compile(r'([a-zA-Z_]+)="([^"]*)"')
SCRIP = re.compile(r'<scripRef[^>]*passage="([^"]*)"[^>]*>(.*?)</scripRef>', re.S | re.I)


def parse_work(xml, slug):
    meta = dc_meta(xml)
    title = meta.get("title") or slug
    subjects = meta.get("subject") or []
    if isinstance(subjects, str):
        subjects = [subjects]
    rights = meta.get("rights") or ""
    lang = (meta.get("language") or "eng")
    if isinstance(lang, list):
        lang = lang[0]
    creators = meta.get("creator") or []
    if isinstance(creators, str):
        creators = [creators]

    body = xml
    m = re.search(r"<ThML\.body[^>]*>(.*)</ThML\.body>", xml, re.S)
    if m:
        body = m.group(1)
    keys, texts, refs = [], [], []
    divs = DIV1.findall(body)
    if not divs:
        divs = [("", body)]
    for i, (attrs, chunk) in enumerate(divs):
        a = dict(ATTR.findall(attrs))
        key = a.get("title") or a.get("shorttitle") or a.get("n") or f"chapter {i+1}"
        key = " ".join(key.split()) or f"chapter {i+1}"
        # keep scripture references as printed text, then strip the tags
        chunk = SCRIP.sub(lambda mm: mm.group(2), chunk)
        t = clean(chunk, keep_linebreaks=True)
        if not t:
            continue
        keys.append(key)
        texts.append(t)
        refs.append(parse_passage(key, a))
    return {
        "module_id": slug.replace("/", "_"),
        "module_name": title[:300],
        "category": classify(subjects, title),
        "license": rights or "",
        "language": lang,
        "creators": creators,
        "subjects": subjects,
        "publisher": meta.get("publisher", ""),
        "source_url": BASE + slug + ".xml",
        "keys": keys,
        "texts": texts,
        "refs": refs,
        "dc": {k: v for k, v in meta.items() if k in
               ("title", "publisher", "date_created", "type", "source",
                "identifier_url", "rights", "language")},
    }


PASSAGE = re.compile(r"^(?:[1-3]\s*)?([A-Za-z][A-Za-z .]+?)\s+(\d+)(?::(\d+))?(?:[-–]|$)")


def parse_passage(key, attrs):
    """A div1 title like 'Homily 12' is not scripture; 'James 1:19' is."""
    m = PASSAGE.match(key.strip())
    if not m:
        return None, None, None
    from harvest import BOOKS
    b = BOOKS.get(m.group(1).strip().lower())
    if not b:
        return None, None, None
    return b, int(m.group(2)), int(m.group(3)) if m.group(3) else 0


PRINT_YEAR = re.compile(r"(1[4-9]\d{2}|20[0-2]\d)")


def print_year(xml):
    """Year of the print edition CCEL digitised, from <printSourceInfo><published>."""
    m = re.search(r"<printSourceInfo>(.*?)</printSourceInfo>", xml, re.S)
    if not m:
        return None
    years = PRINT_YEAR.findall(m.group(1))
    return int(years[-1]) if years else None


def is_public_domain(rights, xml=None, include_unstated=False):
    """Return (ok, reason, basis).

    basis is 'stated' when the work says Public Domain / CC in DC.Rights, and
    'inferred_pre1929' when the field is empty but the digitised print edition
    predates 1929, which is the US public-domain threshold.  The second class is
    opt-in and is flagged in the manifest so it can be filtered out.
    """
    r = (rights or "").lower()
    if "public domain" in r:
        return True, "public domain", "stated"
    if "creative commons" in r and ("cc0" in r or " by" in r or r.startswith("creative")):
        return True, r[:60], "stated"
    if "copyright" in r and "public domain" not in r:
        return False, r[:80], None
    year = print_year(xml) if xml else None
    if include_unstated and year and year <= 1928:
        return True, f"print edition {year}, CCEL rights field empty", "inferred_pre1929"
    if not r:
        return False, "no rights statement", None
    return False, r[:80], None


def build_one(slug, title_hint, dry=False, include_unstated=False):
    path = os.path.join(CACHE, slug.replace("/", "_") + ".xml")
    try:
        fetch(BASE + slug + ".xml", path)
    except urllib.error.HTTPError as e:
        return None, f"http {e.code}"
    except Exception as e:
        return None, f"fetch failed: {e}"
    try:
        xml = open(path, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return None, f"read failed: {e}"
    if len(xml) < 1000:
        return None, "empty xml"
    parsed = parse_work(xml, slug)
    ok, why, basis = is_public_domain(parsed["license"], xml, include_unstated)
    parsed["license_basis"] = basis
    parsed["print_year"] = print_year(xml)
    if not ok:
        os.remove(path)
        return {"skipped": why, "module_id": parsed["module_id"],
                "module_name": parsed["module_name"], "rights": parsed["license"]}, None
    if dry:
        os.remove(path)
        return {"dry": True, **{k: parsed[k] for k in
                                ("module_id", "module_name", "category", "license",
                                 "language")},
                "chapters": len(parsed["keys"]),
                "chars": sum(len(t) for t in parsed["texts"])}, None
    parsed["category"] = classify_refined(parsed)
    # Some CCEL volumes are page images with no extractable text; ThML still
    # carries "Image of page i" placeholders.  Refuse those rather than ingest
    # a scan as if it were text.
    joined = "\n".join(parsed["texts"])
    if joined.count("Image of page") >= 3:
        leftover = joined.replace("Image of page", "")
        letters = sum(c.isalpha() for c in leftover)
        if letters / max(1, len(leftover)) <= 0.55 or len(leftover.strip()) < 5000:
            os.remove(path)
            return {"skipped": "image-only scan, no extractable text",
                    "module_id": parsed["module_id"],
                    "module_name": parsed["module_name"]}, None
    keys, texts, refs = parsed["keys"], parsed["texts"], parsed["refs"]
    if not keys:
        return None, "no text"
    n = len(keys)
    table = pa.table({
        "module_id": pa.array([parsed["module_id"]] * n, pa.string()),
        "module_name": pa.array([parsed["module_name"]] * n, pa.string()),
        "category": pa.array([parsed["category"]] * n, pa.string()),
        "entry_key": pa.array(keys, pa.string()),
        "entry_order": pa.array(list(range(n)), pa.int32()),
        "book_id": pa.array([r[0] for r in refs], pa.string()),
        "chapter": pa.array([r[1] for r in refs], pa.int16()),
        "verse": pa.array([r[2] for r in refs], pa.int16()),
        "entry_text": pa.array(texts, pa.string()),
        "char_count": pa.array([len(t) for t in texts], pa.int32()),
    }, schema=SCHEMA)
    os.makedirs(os.path.join(OUT, "partitioned"), exist_ok=True)
    # one JSON file per work, so parallel harvesters never overwrite each other
    pq.write_table(table, os.path.join(OUT, "partitioned", parsed["module_id"] + ".parquet"),
                   compression="zstd", compression_level=19, use_dictionary=False,
                   row_group_size=200000, data_page_size=4 << 20)
    man = {
        "status": "ok",
        "module_id": parsed["module_id"],
        "module_name": parsed["module_name"],
        "category": parsed["category"],
        "sword_driver": "external:ccel",
        "language": parsed["language"],
        "license": (parsed["license"] or
                    ("Public Domain (inferred, print edition %s)" % parsed["print_year"]
                     if parsed["license_basis"] == "inferred_pre1929" else "Public Domain")),
        "license_basis": parsed["license_basis"] or "",
        "copyright": ("CCEL electronic edition; print source: "
                      + str(parsed["dc"].get("publisher", "")))[:400],
        "source_name": "Christian Classics Ethereal Library (CCEL)",
        "source_url": "https://www.ccel.org/ccel/" + slug,
        "download_url": BASE + slug + ".xml",
        "module_version": "CCEL ThML",
        "sword_version_date": "",
        "text_source": "CCEL ThML XML",
        "markup_source_type": "ThML",
        "about": ("; ".join(parsed["creators"])[:300] + " — " +
                  "; ".join(parsed["subjects"])[:300])[:600],
        "entry_count": n,
        "empty_entries_skipped": 0,
        "duplicate_entries_dropped": 0,
        "repeated_keys_disambiguated": 0,
        "char_count": sum(len(t) for t in texts),
        "scripture_linked_entries": sum(1 for r in refs if r[0]),
        "retrieved": "2026-10-28",
    }
    sidecar = os.path.join(OUT, "manifests")
    os.makedirs(sidecar, exist_ok=True)
    json.dump(man, open(os.path.join(sidecar, parsed["module_id"] + ".json"), "w"), indent=1)
    os.remove(path)
    return man, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--include-unstated", action="store_true",
                    help="also take works with an empty DC.Rights whose print edition "
                         "predates 1929; they are flagged license_basis=inferred_pre1929")
    a = ap.parse_args()

    works = enumerate_works()
    items = sorted(works.items())
    if a.only:
        want = {x.strip() for x in a.only.split(",")}
        items = [(k, v) for k, v in items if k in want]
    if a.limit:
        items = items[: a.limit]
    print(f"{len(items)} works to consider", flush=True)

    os.makedirs(OUT, exist_ok=True)
    man_path = os.path.join(OUT, "modules.json")
    manifest = {r["module_id"]: r for r in json.load(open(man_path))} \
        if os.path.exists(man_path) else {}
    skipped_path = "/tmp/ccel_skipped.json"
    skipped = json.load(open(skipped_path)) if os.path.exists(skipped_path) else {}
    survey = []

    for i, (slug, hint) in enumerate(items, 1):
        mid = slug.replace("/", "_")
        if not a.survey and mid in manifest and manifest[mid].get("status") == "ok":
            print(f"[{i}/{len(items)}] skip (done) {mid}", flush=True)
            continue
        t0 = time.time()
        try:
            res, err = build_one(slug, hint, dry=a.survey,
                                 include_unstated=a.include_unstated)
        except Exception as e:  # never let one work kill the run
            print(f"[{i}/{len(items)}] FAIL {slug}: {e}", flush=True)
            skipped[slug] = {"reason": f"exception: {e}"}
            continue
        if err:
            print(f"[{i}/{len(items)}] FAIL {slug}: {err}", flush=True)
            skipped[slug] = {"reason": err}
            continue
        if res and "skipped" in res:
            skipped[slug] = {"reason": "licence: " + str(res["skipped"]),
                             "module_id": res["module_id"],
                             "module_name": res["module_name"]}
            continue
        if a.survey:
            survey.append(res)
            print(f"[{i}/{len(items)}] {res['module_id'][:34]:36s} "
                  f"{res['category']:14s} {res['chapters']:4d} ch "
                  f"{res['chars']/1e6:6.2f} Mch", flush=True)
            continue
        manifest[res["module_id"]] = res
        json.dump(list(manifest.values()), open(man_path, "w"), indent=1)
        print(f"[{i}/{len(items)}] {res['module_id'][:34]:36s} {res['category']:14s} "
              f"{res['entry_count']:4d} ch {res['char_count']/1e6:6.2f} Mch "
              f"{time.time()-t0:5.1f}s", flush=True)

    json.dump(skipped, open(skipped_path, "w"), indent=1)
    if a.survey:
        json.dump(survey, open("/tmp/ccel_survey.json", "w"), indent=1)
        from collections import Counter
        c = Counter(x["category"] for x in survey)
        print("\nPD works:", len(survey), "chars:", sum(x["chars"] for x in survey))
        for k, v in c.most_common():
            print(f"  {k:16s} {v:4d} works")
    print("skipped (non-PD or failed):", len(skipped))


if __name__ == "__main__":
    main()
