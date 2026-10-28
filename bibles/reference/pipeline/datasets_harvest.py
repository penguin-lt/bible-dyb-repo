"""Structured reference datasets: morphology, semantic domains, cross-references,
lexical indexes and place-name gazetteers.

These are not prose works — they are parsing codes, domain tags and reference
indexes — but they belong in the same database because they are what turns text
into analysable data. Each one lands as its own partition with the same ten
columns, and `topic` in the manifest says which of the twenty coverage areas it
serves.

    TEGMC   STEPBible Greek morphology codes expanded            CC BY 4.0
    TEHMC   STEPBible Hebrew morphology codes expanded           CC BY 4.0
    TBESH   (already ingested) — carries the SDBH sense numbers
    OHLEX   Open Scriptures Hebrew LexicalIndex (Strong->BDB->SDBH)   public domain
    XREF    OpenBible.info cross references, 340k votes           CC BY
    PLEIA   Pleiades ancient place name index                    CC BY 3.0

    python3 datasets_harvest.py [--only XREF,TEGMC]
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from normalize import clean  # noqa: E402
from harvest import SCHEMA, OUT  # noqa: E402

DL = os.environ.get("REF_CACHE", "/home/user/scratch/cache/ds")
UA = {"User-Agent": "bible-reference-harvest/1.0 (+https://github.com/penguin-lt/bible-dyb-repo)"}

STEP = "https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/"
SOURCES = {
    "TEGMC": {
        "url": STEP + "Morphology%20codes/TEGMC%20-%20Translators%20Expansion%20of%20"
                      "Greek%20Morphhology%20Codes%20-%20STEPBible.org%20CC%20BY.txt",
        "file": "TEGMC.txt", "name": "STEPBible Greek morphology codes (expanded)",
        "topic": "Morphology & Parsing Data", "license": "Creative Commons: BY 4.0",
        "lang": "grc", "kind": "tsv_codes",
        "about": "Every Greek morphology code used in STEPBible tagging, with its expansion.",
    },
    "TEHMC": {
        "url": STEP + "Morphology%20codes/TEHMC%20-%20Translators%20Expansion%20of%20"
                      "Hebrew%20Morphhology%20Codes%20-%20STEPBible.org%20CC%20BY.txt",
        "file": "TEHMC.txt", "name": "STEPBible Hebrew morphology codes (expanded)",
        "topic": "Morphology & Parsing Data", "license": "Creative Commons: BY 4.0",
        "lang": "he", "kind": "tsv_codes",
        "about": "Every Hebrew/Aramaic morphology code used in STEPBible tagging, with its expansion.",
    },
    "OHLEX": {
        "url": ("https://raw.githubusercontent.com/openscriptures/HebrewLexicon/"
                "master/LexicalIndex.xml"),
        "file": "LexicalIndex.xml", "name": "Open Scriptures Hebrew lexical index",
        "topic": "Lexical Datasets (Domain/Semantic)", "license": "Public Domain",
        "lang": "he", "kind": "lexindex",
        "about": ("Strong's number to BDB article and SDBH semantic-domain entry, "
                  "with Hebrew/Greek lemmas and transliterations."),
    },
    "XREF": {
        "url": "https://a.openbible.info/data/cross-references.zip",
        "file": "cross-references.zip", "name": "OpenBible.info cross references",
        "topic": "Cross-Reference Systems", "license": "Creative Commons: BY 4.0",
        "lang": "en", "kind": "xrefs",
        "about": ("340,000+ congregation-voted cross references between verses, "
                  "the data behind openbible.info/labs/cross-references."),
    },
    "PLEIA": {
        "url": ("https://raw.githubusercontent.com/isawnyu/pleiades.datasets/main/"
                "data/indexes/name_index.json"),
        "file": "pleiades_name_index.json", "name": "Pleiades ancient place name index",
        "topic": "Maps & Geography", "license": "Creative Commons: BY 4.0",
        "lang": "en", "kind": "pleiades",
        "about": ("Index of ancient place names from the Pleiades gazetteer "
                  "(80,000 names), the standard reference for classical geography."),
    },
}


def fetch(spec):
    os.makedirs(DL, exist_ok=True)
    p = os.path.join(DL, spec["file"])
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        return p
    req = urllib.request.Request(spec["url"], headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r, open(p, "wb") as fh:
        while True:
            c = r.read(1 << 20)
            if not c:
                break
            fh.write(c)
    return p


CODE_RE = re.compile(r"^[A-Z0-9:@\-\u0300-\u036f]{1,14}\t")


def rows_tsv_codes(path):
    keys, texts = [], []
    for line in open(path, encoding="utf-8-sig", errors="replace").read().split("\n"):
        if not CODE_RE.match(line):
            continue
        c = line.split("\t")
        k = c[0].strip()
        body = " — ".join(x.strip() for x in c[1:] if x.strip())
        if k and body:
            keys.append(k)
            texts.append(clean(body, keep_linebreaks=False))
    return keys, texts


def rows_lexindex(path):
    """Open Scriptures LexicalIndex: entry id, <w xlit>, <pos>, <def>, and an
    <xref bdb=".." strong=".." twot=".."/> that is the join to BDB and Strong's."""
    import xml.etree.ElementTree as ET

    def tag(e):
        return e.tag.split("}")[-1]

    keys, texts = [], []
    for _, el in ET.iterparse(path, events=("end",)):
        if tag(el) != "entry":
            continue
        xref = next((c for c in el if tag(c) == "xref"), None)
        strong = (xref.get("strong") if xref is not None else None) or el.get("id")
        parts = []
        w = next((c for c in el if tag(c) == "w"), None)
        if w is not None and (w.text or "").strip():
            xlit = w.get("xlit")
            parts.append(f"{w.text.strip()}" + (f" ({xlit})" if xlit else ""))
        for c in el:
            t = tag(c)
            if t == "pos" and (c.text or "").strip():
                parts.append("pos " + c.text.strip())
            elif t == "def" and (c.text or "").strip():
                parts.append(c.text.strip())
            elif t == "etym" and (c.text or "").strip():
                parts.append("root " + c.text.strip())
        if xref is not None:
            for a in ("bdb", "twot"):
                if xref.get(a):
                    parts.append(f"{a} {xref.get(a)}")
        body = "; ".join(parts)
        if strong and body:
            keys.append("H" + str(strong).zfill(4) if str(strong).isdigit() else str(strong))
            texts.append(clean(body, keep_linebreaks=False))
        el.clear()
        el.tail = None
    return keys, texts


def rows_xrefs(path):
    """One row per source verse: all its targets, votes included."""
    zf = zipfile.ZipFile(path)
    name = [n for n in zf.namelist() if n.endswith(".txt")][0]
    per = {}
    with zf.open(name) as fh:
        for i, raw in enumerate(fh):
            if i == 0:
                continue
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            src, dst, votes = parts[0], parts[1], parts[2]
            per.setdefault(src, []).append((dst, votes))
    keys, texts = [], []
    for src, tgts in per.items():
        tgts.sort(key=lambda t: -int(t[1] or 0))
        keys.append(src)
        texts.append("; ".join(f"{d} ({v})" for d, v in tgts))
    return keys, texts


def rows_pleiades(path):
    data = json.load(open(path, encoding="utf-8"))
    keys, texts = [], []
    for name, pid in data:
        if not name or not pid:
            continue
        keys.append(str(name))
        texts.append(f"Pleiades ID {pid}; https://pleiades.stoa.org/places/{pid}")
    return keys, texts


PARSERS = {"tsv_codes": rows_tsv_codes, "lexindex": rows_lexindex,
           "xrefs": rows_xrefs, "pleiades": rows_pleiades}


def build(mod):
    spec = SOURCES[mod]
    path = fetch(spec)
    keys, texts = PARSERS[spec["kind"]](path)
    if not keys:
        raise SystemExit("no rows for " + mod)
    seen, k2, t2 = {}, [], []
    for k, t in zip(keys, texts):
        base = k
        if k in seen:
            if seen[k] == t:
                continue
            n = 2
            while k in seen:
                k = f"{base} ({n})"
                n += 1
        seen[k] = t
        k2.append(k)
        t2.append(t)
    n = len(k2)
    table = pa.table({
        "module_id": pa.array([mod] * n, pa.string()),
        "module_name": pa.array([spec["name"]] * n, pa.string()),
        "category": pa.array(["Reference"] * n, pa.string()),
        "entry_key": pa.array(k2, pa.string()),
        "entry_order": pa.array(list(range(n)), pa.int32()),
        "book_id": pa.array([None] * n, pa.string()),
        "chapter": pa.array([None] * n, pa.int16()),
        "verse": pa.array([None] * n, pa.int16()),
        "entry_text": pa.array(t2, pa.string()),
        "char_count": pa.array([len(t) for t in t2], pa.int32()),
    }, schema=SCHEMA)
    os.makedirs(os.path.join(OUT, "partitioned"), exist_ok=True)
    pq.write_table(table, os.path.join(OUT, "partitioned", mod + ".parquet"),
                   compression="zstd", compression_level=19, use_dictionary=False,
                   row_group_size=200000, data_page_size=4 << 20)
    man = {
        "status": "ok", "module_id": mod, "module_name": spec["name"],
        "category": "Reference", "topic": spec["topic"],
        "sword_driver": "external:dataset", "language": spec["lang"],
        "license": spec["license"], "license_basis": "stated",
        "copyright": "", "source_name": spec["name"], "source_url": spec["url"],
        "download_url": spec["url"], "module_version": "",
        "sword_version_date": "", "text_source": spec["file"],
        "markup_source_type": "structured (TSV/JSON/XML/CSV)",
        "about": spec["about"], "entry_count": n, "empty_entries_skipped": 0,
        "duplicate_entries_dropped": 0, "repeated_keys_disambiguated": 0,
        "char_count": sum(len(t) for t in t2), "scripture_linked_entries": 0,
        "retrieved": "2026-10-28",
    }
    print(f"  {mod:6s} {n:7d} rows {man['char_count']/1e6:7.2f} Mchars "
          f"{os.path.getsize(os.path.join(OUT, 'partitioned', mod + '.parquet'))/1e6:.1f} MB",
          flush=True)
    sidecar = os.path.join(OUT, "manifests")
    os.makedirs(sidecar, exist_ok=True)
    json.dump(man, open(os.path.join(sidecar, man["module_id"] + ".json"), "w"), indent=1)
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    mods = [m.strip() for m in a.only.split(",") if m.strip()] or list(SOURCES)
    os.makedirs(OUT, exist_ok=True)
    man_path = os.path.join(OUT, "modules.json")
    manifest = {r["module_id"]: r for r in json.load(open(man_path))} \
        if os.path.exists(man_path) else {}
    for m in mods:
        print(f"[{m}]", flush=True)
        manifest[m] = build(m)
        json.dump(list(manifest.values()), open(man_path, "w"), indent=1)
    print("done:", ", ".join(mods))


if __name__ == "__main__":
    main()
