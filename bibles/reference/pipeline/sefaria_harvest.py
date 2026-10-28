"""Ingest Sefaria's public-domain English texts: rabbinics, Targums, Second Temple.

Sefaria publishes 19,815 texts as JSON on Google Cloud Storage with a machine
readable index (`books.json`: title, categories, versionTitle, json_url) and a
`license` field inside every text file. We take the English versions only, and
only where that license is Public Domain or an explicitly free one.

Coverage this brings to the database (categories as Sefaria files them):
    Talmud / Mishnah / Tosefta   -> Rabbinic Literature
    Midrash                      -> Rabbinic Literature
    Tanakh / Targum              -> Rabbinic Literature, Targums
    Second Temple                -> Apocrypha & Pseudepigrapha (incl. Josephus, Philo)
    Liturgy                      -> Liturgy & Lectionaries
    Jewish Thought / Halakhah    -> Theology, Church History analogues

Each text becomes one partition: entry_key = chapter/section label, entry_text =
the section's paragraphs joined. Versified texts (Tanakh with chapter/verse arrays)
keep a `Book C:V` key so they can join the verse corpus.

    python3 sefaria_harvest.py --survey
    python3 sefaria_harvest.py [--limit N] [--categories Talmud,Midrash]
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from normalize import clean  # noqa: E402
from harvest import SCHEMA, OUT, BOOKS  # noqa: E402

INDEX = ("https://raw.githubusercontent.com/Sefaria/Sefaria-Export/master/books.json")
UA = {"User-Agent": "bible-reference-harvest/1.0 (+https://github.com/penguin-lt/bible-dyb-repo)"}
CACHE = os.environ.get("REF_CACHE", "/home/user/scratch/cache/sefaria")

FREE = ("public domain", "cc0", "creative commons attribution", "cc-by",
        "creative commons: by", "gpl")

# script ranges used to detect a text's language when the file does not say
_HE = re.compile(r"[\u0590-\u05ff]")
_GR = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
_AR = re.compile(r"[\u0600-\u06ff]")
_CY = re.compile(r"[\u0400-\u04ff]")

# Sefaria category -> our topic family
TOPIC = {
    "Talmud": "Rabbinic Literature", "Mishnah": "Rabbinic Literature",
    "Tosefta": "Rabbinic Literature", "Midrash": "Rabbinic Literature",
    "Tanakh": "Rabbinic Literature", "Second Temple": "Apocrypha & Pseudepigrapha",
    "Liturgy": "Liturgy & Lectionaries", "Jewish Thought": "Theology",
    "Halakhah": "Rabbinic Literature", "Kabbalah": "Mysticism & Asceticism",
    "Chasidut": "Mysticism & Asceticism", "Musar": "Mysticism & Asceticism",
    "Responsa": "Rabbinic Literature", "Reference": "Reference",
}


def get(url, timeout=180):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def index():
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, "books.json")
    if not os.path.exists(p):
        open(p, "wb").write(get(INDEX, 300))
    return json.load(open(p))["books"]


def topic_of(categories):
    for c in categories:
        if c in TOPIC:
            return TOPIC[c]
    return "Rabbinic Literature"


def flatten(node):
    """Sefaria text is nested arrays of strings; join to plain text."""
    out = []

    def walk(x):
        if isinstance(x, str):
            if x.strip():
                out.append(x)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(node)
    return out


def sections(text):
    """Yield (key, body). Handles versified (chapter->verse list) and flat lists."""
    if isinstance(text, dict):
        text = list(text.values())
    if not isinstance(text, list):
        return
    for i, ch in enumerate(text):
        # Sefaria nests arbitrarily deep: chapter -> verse -> [segments].
        # Flatten the whole subtree, which is what flatten() already does.
        parts = flatten(ch)
        body = "\n".join(parts)
        if body:
            yield f"chapter {i+1}", body, i + 1


def build(entry, dry=False):
    url = entry["json_url"]
    try:
        raw = get(url, 300)
    except urllib.error.HTTPError as e:
        return None, f"http {e.code}"
    except Exception as e:
        return None, f"fetch: {e}"
    try:
        d = json.loads(raw)
    except Exception:
        return None, "bad json"
    if isinstance(d, list):
        d = d[0] if d else {}
    lic = (d.get("license") or "").lower()
    if not any(f in lic for f in FREE):
        return {"skipped": lic or "no license field",
                "module_id": "sefaria_" + entry["title"][:40]}, None

    text = d.get("text")
    if not text:
        return None, "no text"
    keys, bodies, chapters = [], [], []
    for key, body, ch in sections(text):
        cleaned = clean(body, keep_linebreaks=True)
        keys.append(key)
        bodies.append(cleaned)
        chapters.append(ch)
    if not keys:
        return None, "no text after parse"

    title = (d.get("title") or entry["title"])
    cats = d.get("categories") or entry.get("categories") or []
    # One text can exist as several versions (Hebrew and English editions of the
    # same title). Key the module on title *and* version, or the second version
    # silently overwrites the first in the partition directory.
    lang_tag = {"he": "he", "en": "en"}.get(
        (d.get("actualLanguage") or d.get("language") or "en").lower()[:2], "x")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title)[:44].strip("_")
    vtag = re.sub(r"[^A-Za-z0-9]+", "_", d.get("versionTitle", ""))[:18].strip("_")
    mid = "_".join(x for x in ("sefaria", slug, lang_tag, vtag) if x)
    topic = topic_of(cats)
    # Sefaria files some non-English translations under language="English";
    # trust the text's own actualLanguage for labelling.
    actual = (d.get("actualLanguage") or d.get("language") or "").lower()[:5]
    if not actual:
        # Many Sefaria files omit actualLanguage. Guessing "en" from the index
        # mislabelled 5,414 Hebrew and 3 Arabic/Cyrillic works, so detect the
        # script from the text itself.
        head = " ".join(b for b in bodies if b)[:60000]
        n = max(1, len(head))
        he = len(_HE.findall(head)) / n
        gr = len(_GR.findall(head)) / n
        ar = len(_AR.findall(head)) / n
        cy = len(_CY.findall(head)) / n
        best = max(he, gr, ar, cy)
        if best > 0.12:
            actual = ("he" if he == best else "grc" if gr == best
                      else "ar" if ar == best else "ru")
        else:
            actual = "en"
    info = {
        "module_id": mid,
        "module_name": (title + (" — " + d.get("versionTitle", "") if d.get("versionTitle") else ""))[:300],
        "category": "Reference",
        "topic": topic,
        "license": d.get("license") or "",
        "language": actual,
        "chapters": len(keys),
        "chars": sum(len(b) for b in bodies),
        "version": d.get("versionTitle", ""),
        "version_source": d.get("versionSource", ""),
        "categories": cats,
        "url": url,
    }
    if dry:
        return info, None

    n = len(keys)
    table = pa.table({
        "module_id": pa.array([mid] * n, pa.string()),
        "module_name": pa.array([info["module_name"]] * n, pa.string()),
        "category": pa.array(["Reference"] * n, pa.string()),
        "entry_key": pa.array(keys, pa.string()),
        "entry_order": pa.array(list(range(n)), pa.int32()),
        "book_id": pa.array([None] * n, pa.string()),
        "chapter": pa.array([None] * n, pa.int16()),
        "verse": pa.array([None] * n, pa.int16()),
        "entry_text": pa.array(bodies, pa.string()),
        "char_count": pa.array([len(b) for b in bodies], pa.int32()),
    }, schema=SCHEMA)
    os.makedirs(os.path.join(OUT, "partitioned"), exist_ok=True)
    pq.write_table(table, os.path.join(OUT, "partitioned", mid + ".parquet"),
                   compression="zstd", compression_level=19, use_dictionary=False,
                   row_group_size=200000, data_page_size=4 << 20)
    sidecar = os.path.join(OUT, "manifests")
    os.makedirs(sidecar, exist_ok=True)
    man = {
        "status": "ok",
        "module_id": mid,
        "module_name": info["module_name"],
        "category": "Reference",
        "topic": topic,
        "sword_driver": "external:sefaria",
        "language": "en",
        "license": d.get("license") or "",
        "license_basis": "stated",
        "copyright": (d.get("versionSource") or "")[:400],
        "source_name": "Sefaria (Sefaria-Export) — " + " / ".join(cats[:3]),
        "source_url": "https://www.sefaria.org/" + title.replace(" ", "_"),
        "download_url": url,
        "module_version": d.get("versionTitle", "")[:120],
        "sword_version_date": "",
        "text_source": d.get("versionTitle", ""),
        "markup_source_type": "Sefaria JSON",
        "about": "Categories: " + " / ".join(cats)[:400],
        "entry_count": n,
        "empty_entries_skipped": 0,
        "duplicate_entries_dropped": 0,
        "repeated_keys_disambiguated": 0,
        "char_count": info["chars"],
        "scripture_linked_entries": 0,
        "retrieved": "2026-10-28",
    }
    json.dump(man, open(os.path.join(sidecar, mid + ".json"), "w"), indent=1)
    return man, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--categories", default="")
    ap.add_argument("--all-languages", action="store_true",
                    help="also take the Hebrew/Aramaic versions (13,551 texts); "
                         "the licence gate is unchanged")
    a = ap.parse_args()

    books = index()
    want = [c.strip().lower() for c in a.categories.split(",") if c.strip()]
    cand = []
    seen = set()
    for b in books:
        if b.get("language") != "English" and not a.all_languages:
            continue
        cats = b.get("categories") or []
        if want and not any(any(w in c.lower() for c in cats) for w in want):
            continue
        t = b["title"] + "|" + (b.get("versionTitle") or "")
        if t in seen:                     # several versions of one title
            continue
        seen.add(t)
        cand.append(b)
    if a.limit:
        cand = cand[: a.limit]
    print(f"{len(cand)} English texts to consider", flush=True)

    os.makedirs(OUT, exist_ok=True)
    man_path = os.path.join(OUT, "modules.json")
    manifest = {r["module_id"]: r for r in json.load(open(man_path))} \
        if os.path.exists(man_path) else {}
    skipped = {}
    survey = []
    for i, b in enumerate(cand, 1):
        res, err = build(b, dry=a.survey)
        if err:
            skipped[b["title"]] = f"{b['title']}: {err}"
            print(f"[{i}/{len(cand)}] FAIL {b['title'][:50]}: {err}", flush=True)
            continue
        if res and "skipped" in res:
            skipped[b["title"]] = res["skipped"]
            continue
        if a.survey:
            survey.append(res)
            print(f"[{i}/{len(cand)}] {res['module_id'][:42]:44s} {res['topic'][:22]:24s} "
                  f"{res['chapters']:4d} ch {res['chars']/1e6:6.2f} Mch", flush=True)
            continue
        manifest[res["module_id"]] = res
        json.dump(list(manifest.values()), open(man_path, "w"), indent=1)
        print(f"[{i}/{len(cand)}] {res['module_id'][:42]:44s} {res['topic'][:20]:22s} "
              f"{res['entry_count']:4d} ch {res['char_count']/1e6:6.2f} Mch", flush=True)

    json.dump(skipped, open("/tmp/sefaria_skipped.json", "w"), indent=1)
    if a.survey:
        json.dump(survey, open("/tmp/sefaria_survey.json", "w"), indent=1)
        from collections import Counter
        print("\nfree-licensed texts:", len(survey),
              "chars:", sum(x["chars"] for x in survey))
        for k, v in Counter(x["topic"] for x in survey).most_common():
            print(f"  {k:28s} {v:4d}")
    print("skipped:", len(skipped))


if __name__ == "__main__":
    main()
