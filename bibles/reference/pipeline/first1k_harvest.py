"""First Thousand Years of Greek (First1KGreek) — pagan and Jewish Greek sources.

The early Christian writers quote, argue with and write in the idiom of a much
larger Greek library: Homer, Hesiod, the tragedians, Herodotus, Thucydides,
Plato, Aristotle, the Septuagint, Philo, Josephus, the New Testament apocrypha
and the apostolic fathers. Those are the texts a reader of the Fathers actually
needs on the shelf, and CCEL does not carry them.

First1KGreek (Harvard, Open Greek and Latin) publishes them as TEI XML, licensed
CC BY-SA 4.0. One work becomes one partition; `entry_key` is chapter or line
range, `entry_text` the plain Greek.

    python3 first1k_harvest.py --survey          # list works, write nothing
    python3 first1k_harvest.py [--limit N] [--only tlg0012,tlg0011]
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from normalize import clean  # noqa: E402
from harvest import SCHEMA, OUT  # noqa: E402

DL = os.environ.get("REF_CACHE", "/home/user/scratch/cache/first1k")
UA = {"User-Agent": "bible-reference-harvest/1.0 (+https://github.com/penguin-lt/bible-dyb-repo)"}
RAW = "https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/"
META = RAW + "new_edition_metadata.csv"
LICENSE = "Creative Commons: BY-SA 4.0"
TEI = "{http://www.tei-c.org/ns/1.0}"

# Authors whose presence in the corpus is what makes it biblically useful.
TOPIC_BY_AUTHOR = {
    "homer": ("Historical & Cultural Background", "classical Greek epic"),
    "plato": ("Systematic Theology & Dogmatics", "philosophy the Fathers argue with"),
    "aristotle": ("Systematic Theology & Dogmatics", "philosophy the Fathers argue with"),
}


def get(url, timeout=300):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def metadata():
    text = get(META).decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    return rows


def text_of(div):
    """Concatenate all leaf text under a div, one line per paragraph."""
    paras = []
    for p in div.iter():
        if p.tag in (TEI + "p", TEI + "l", TEI + "ab"):
            s = "".join(p.itertext())
            s = re.sub(r"\s+", " ", s).strip()
            if s:
                paras.append(s)
    if not paras:
        s = re.sub(r"\s+", " ", "".join(div.itertext())).strip()
        if s:
            paras.append(s)
    return "\n".join(paras)


def sections(root):
    """Yield (label, text) for each top-level div of the edition body."""
    body = root.find(".//" + TEI + "text/" + TEI + "body")
    if body is None:
        return
    divs = body.findall(TEI + "div")
    # a single wrapper div is common; descend one level so chapter keys survive
    while len(divs) == 1 and divs[0].findall(TEI + "div"):
        divs = divs[0].findall(TEI + "div")
    if not divs:
        yield "1", text_of(body)
        return
    for i, d in enumerate(divs, 1):
        label = (d.get("n") or d.get("{http://www.w3.org/XML/1998/namespace}id")
                 or f"section {i}")
        head = d.find(TEI + "head")
        htxt = re.sub(r"\s+", " ", "".join(head.itertext())).strip() if head is not None else ""
        label = f"{label} {htxt}".strip()[:120]
        yield label, text_of(d)


def build(row, dry=False):
    fn = row["Filename"]
    urn = row["URN"]
    title = row.get("Title", "") or urn
    author = row.get("Author", "")
    year = (row.get("Publication Year") or "").strip()
    # tree layout is data/<author-urn>/<work-urn>/<file>. The metadata CSV
    # names the *suggested CTS* file (…opp-grc1.xml); the file actually on disk
    # is the 1st1K one, so try both and keep whichever resolves.
    parts = fn.split(".")
    sub = parts[1] if len(parts) > 1 else ""
    base = f"{parts[0]}.{parts[1]}" if len(parts) > 1 else parts[0]
    cands = [f"{RAW}data/{parts[0]}/{sub}/{base}.1st1K-grc1.xml",
             f"{RAW}data/{parts[0]}/{sub}/{base}.1st1K-eng1.xml",
             f"{RAW}data/{parts[0]}/{sub}/{base}.opp-grc1.xml",
             f"{RAW}data/{parts[0]}/{sub}/{fn}"]
    url, raw = None, None
    for c in cands:
        try:
            raw = get(c)
            url = c
            break
        except Exception:
            continue
    if raw is None:
        try:
            raw = get(f"{RAW}data/{parts[0]}/{fn}")
        except Exception as e:
            return None, f"fetch {type(e).__name__}"
    try:
        root = ET.fromstring(raw)
    except Exception:
        return None, "bad xml"

    keys, texts = [], []
    for label, body in sections(root):
        body = clean(body, keep_linebreaks=True)
        if len(body) < 20:
            continue
        keys.append(label)
        texts.append(body)
    if not keys:
        return None, "no text"

    slug = re.sub(r"[^A-Za-z0-9]+", "_", urn.split(":")[-1])[:48].strip("_")
    mid = "f1k_" + slug
    topic, note = TOPIC_BY_AUTHOR.get(author.lower(), ("Patristics & Early Church Fathers", ""))
    if "apocryph" in title.lower() or author.lower() in ("philo", "josephus"):
        topic = "Apocrypha & Pseudepigrapha"
    info = {
        "module_id": mid,
        "module_name": f"{author}: {title}"[:300],
        "category": "Reference",
        "topic": topic,
        "license": LICENSE,
        "language": "grc",
        "entry_count": len(keys),
        "char_count": sum(len(t) for t in texts),
        "source_url": url,
        "about": f"{author}, {title}. Editor {row.get('Editor','')}; "
                 f"{row.get('Publisher','')} {year}. {note}".strip(),
        "edition_year": year,
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
        "entry_text": pa.array(texts, pa.string()),
        "char_count": pa.array([len(t) for t in texts], pa.int32()),
    }, schema=SCHEMA)
    os.makedirs(os.path.join(OUT, "partitioned"), exist_ok=True)
    pq.write_table(table, os.path.join(OUT, "partitioned", mid + ".parquet"),
                   compression="zstd", compression_level=19, use_dictionary=False,
                   row_group_size=200000, data_page_size=4 << 20)
    man = {
        "status": "ok", "module_id": mid, "module_name": info["module_name"],
        "category": "Reference", "topic": topic,
        "sword_driver": "external:first1kgreek", "language": "grc",
        "license": LICENSE, "license_basis": "stated",
        "copyright": f"First1KGreek, CC BY-SA 4.0; edition {year}",
        "source_name": "First Thousand Years of Greek (Harvard / Open Greek and Latin)",
        "source_url": "https://github.com/OpenGreekAndLatin/First1KGreek",
        "download_url": url, "module_version": urn, "sword_version_date": "",
        "text_source": fn, "markup_source_type": "TEI XML",
        "about": info["about"], "entry_count": n, "empty_entries_skipped": 0,
        "duplicate_entries_dropped": 0, "repeated_keys_disambiguated": 0,
        "char_count": info["char_count"], "scripture_linked_entries": 0,
        "retrieved": "2026-10-28",
    }
    sidecar = os.path.join(OUT, "manifests")
    os.makedirs(sidecar, exist_ok=True)
    json.dump(man, open(os.path.join(sidecar, mid + ".json"), "w"), indent=1)
    return man, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--missing-only", action="store_true",
                    help="only retry editions with no partition yet")
    a = ap.parse_args()
    rows = metadata()
    want = [w.strip() for w in a.only.split(",") if w.strip()]
    if want:
        rows = [r for r in rows if any(w in r["URN"] for w in want)]
    if a.limit:
        rows = rows[: a.limit]
    if a.missing_only:
        have = set(os.listdir(os.path.join(OUT, "partitioned")))
        rows = [r for r in rows if f"f1k_{re.sub(r'[^A-Za-z0-9]+','_',r['URN'].split(':')[-1])[:48].strip('_')}.parquet" not in have]
    print(f"{len(rows)} editions to consider", flush=True)
    done = skipped = 0
    chars = 0
    sk = {}
    for i, r in enumerate(rows, 1):
        res, err = build(r, dry=a.survey)
        if err:
            skipped += 1
            sk[r["URN"]] = err
            if skipped % 50 == 0:
                print(f"  [{i}] skipped {skipped}", flush=True)
            continue
        done += 1
        chars += res["char_count"]
        if done % 25 == 0 or done < 5:
            print(f"[{i}/{len(rows)}] {res['module_id'][:40]:42s} "
                  f"{res['entry_count']:5d} sec {res['char_count']/1e6:6.2f} Mch", flush=True)
    print(f"\nworks: {done}  skipped: {skipped}  chars: {chars:,}")
    if a.survey:
        json.dump(sk, open("/home/user/scratch/first1k_skipped.json", "w"), indent=1)


if __name__ == "__main__":
    main()
