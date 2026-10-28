"""Ingest non-SWORD reference works that are public domain / explicitly free.

Three sources, each reaching the dataset as a normal partition plus a manifest
row, so combine.py and verify.py pick them up without special-casing:

    LSJ      Perseus Digital Library, full Liddell-Scott-Jones, TEI XML, 42.9 MB
             public domain            -> module_id `LSJ`
    BDB      Open Scriptures full Brown-Driver-Briggs, XML, 2.9 MB
             public domain            -> module_id `BDB`
    TBESG    STEPBible Translators Brief lexicon, Extended Strong's, Greek
             CC BY 4.0                -> module_id `TBESG`
    TBESH    STEPBible Translators Brief lexicon, Extended Strong's, Hebrew
             CC BY 4.0                -> module_id `TBESH`

Downloads go to /tmp; only the Parquet partitions and manifest rows are kept.

    python3 opensource_harvest.py [--only LSJ,BDB,TBESG,TBESH]
"""
import argparse
import html
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

DL = os.environ.get("REF_CACHE", "/home/user/scratch/cache/od")
UA = {"User-Agent": "bible-reference-harvest/1.0 (+https://github.com/penguin-lt/bible-dyb-repo)"}

SOURCES = {
    "LSJ": {
        "url": ("https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/"
                "Lexicons/TFLSJ%20%200-5624%20-%20Translators%20Formatted%20full%20LSJ%20"
                "Bible%20lexicon%20-%20STEPBible.org%20CC%20BY.txt"),
        "file": "TFLSJ.txt",
        "module_name": "Liddell-Scott-Jones Greek-English Lexicon (full, biblical vocabulary)",
        "category": "Lexicon",
        "language": "grc",
        "license": "Creative Commons: BY 4.0",
        "copyright": ("LSJ text public domain (1940); this formatting CC BY 4.0, "
                      "STEPBible.org / Tyndale House Cambridge. Attribution required."),
        "source_name": "STEPBible-Data (Tyndale House Cambridge) — TFLSJ",
        "source_url": "https://github.com/STEPBible/STEPBible-Data",
        "text_source": "TFLSJ Translators Formatted full LSJ Bible lexicon",
        "markup_source_type": "TSV with inline HTML",
        "about": ("The complete LSJ articles for every biblical Greek word "
                  "(Extended Strong's G0001-G5624), with citations and links. "
                  "20.3 M characters. The Perseus machine-readable LSJ covers "
                  "alpha only, so this formatted edition is used instead."),
        "version": "STEPBible-Data master",
    },
    "BDB": {
        "url": ("https://raw.githubusercontent.com/openscriptures/HebrewLexicon/"
                "master/BrownDriverBriggs.xml"),
        "file": "BrownDriverBriggs.xml",
        "module_name": "Brown-Driver-Briggs Hebrew and English Lexicon (full)",
        "category": "Lexicon",
        "language": "he",
        "license": "Public Domain",
        "copyright": "Public domain (1906). Structured text from Open Scriptures.",
        "source_name": "Open Scriptures — openscriptures/HebrewLexicon",
        "source_url": "https://github.com/openscriptures/HebrewLexicon",
        "text_source": "BrownDriverBriggs.xml",
        "markup_source_type": "custom XML (morphhb namespace)",
        "about": ("The complete Brown-Driver-Briggs lexicon. The SWORD corpus "
                  "carries only BDB glosses keyed to Strong's numbers; this is the "
                  "full article text with roots, definitions and citations."),
        "version": "openscriptures master",
    },
    "TBESG": {
        "url": ("https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/"
                "Lexicons/TBESG%20-%20Translators%20Brief%20lexicon%20of%20Extended%20"
                "Strongs%20for%20Greek%20-%20STEPBible.org%20CC%20BY.txt"),
        "file": "TBESG.txt",
        "module_name": "Translators Brief lexicon of Extended Strong's — Greek",
        "category": "Lexicon",
        "language": "grc",
        "license": "Creative Commons: BY 4.0",
        "copyright": ("CC BY 4.0, STEPBible.org / Tyndale House Cambridge. "
                      "Attribution required."),
        "source_name": "STEPBible-Data (Tyndale House Cambridge)",
        "source_url": "https://github.com/STEPBible/STEPBible-Data",
        "text_source": "TBESG tab-separated lexicon",
        "markup_source_type": "TSV with inline HTML",
        "about": ("Brief lexicon for every Extended Strong's Greek number, with "
                  "transliteration, morphology and LSJ-based gloss and definition."),
        "version": "STEPBible-Data master",
    },
    "TBESH": {
        "url": ("https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/"
                "Lexicons/TBESH%20-%20Translators%20Brief%20lexicon%20of%20Extended%20"
                "Strongs%20for%20Hebrew%20-%20STEPBible.org%20CC%20BY.txt"),
        "file": "TBESH.txt",
        "module_name": "Translators Brief lexicon of Extended Strong's — Hebrew",
        "category": "Lexicon",
        "language": "he",
        "license": "Creative Commons: BY 4.0",
        "copyright": ("CC BY 4.0, STEPBible.org / Tyndale House Cambridge. "
                      "Attribution required."),
        "source_name": "STEPBible-Data (Tyndale House Cambridge)",
        "source_url": "https://github.com/STEPBible/STEPBible-Data",
        "text_source": "TBESH tab-separated lexicon",
        "markup_source_type": "TSV with inline HTML",
        "about": ("Brief lexicon for every Extended Strong's Hebrew number, with "
                  "transliteration, morphology and a numbered sense list."),
        "version": "STEPBible-Data master",
    },
}

NUMKEY = re.compile(r"^[GH]?\d{3,5}[A-Za-z]?$")


def fetch(spec):
    os.makedirs(DL, exist_ok=True)
    path = os.path.join(DL, spec["file"])
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return path
    req = urllib.request.Request(spec["url"], headers=UA)
    with urllib.request.urlopen(req, timeout=900) as r, open(path, "wb") as fh:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    return path


def rows_lsj(path):
    """Perseus TEI: one <entryFree> per headword, @key is Beta Code."""
    key, text = [], []
    for _, el in ET.iterparse(path, events=("end",)):
        # only react to the container tag: clearing children on their own 'end'
        # event would empty the entry before it is serialised
        if el.tag.endswith("entryFree"):
            k = (el.get("key") or "").strip()
            body = ET.tostring(el, encoding="unicode")
            body = re.sub(r"^<[^>]+>|</[^>]+>$", "", body)
            t = clean(body, keep_linebreaks=False)
            if k and t:
                key.append(k)
                text.append(t)
            el.clear()
            el.tail = None
    return key, text


BDB_NS = "{http://openscriptures.github.com/morphhb/namespace}"


def rows_bdb(path):
    """Open Scriptures BDB: <entry id="a.aa.aa"> with <w> headword and <def> etc."""
    key, text = [], []
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag == BDB_NS + "entry":  # container only — never clear children
            body = ET.tostring(el, encoding="unicode")
            # <status p="1">done</status> is the editor's progress flag, not text;
            # ET.tostring re-prefixes the namespace, so match it loosely
            body = re.sub(r"<[^>]*status[^>]*>[^<]*</[^>]*status[^>]*>", " ", body,
                          flags=re.I)
            body = re.sub(r"<[^>]*status[^>]*/>", " ", body, flags=re.I)
            t = clean(body, keep_linebreaks=False)
            if t:
                w = el.find(BDB_NS + "w")
                head = (w.text or "").strip() if w is not None else ""
                k = head or (el.get("id") or "")
                key.append(k)
                text.append(t)
            el.clear()
            el.tail = None
    return key, text


def rows_stepbible(path):
    """STEPBible TSV: skip the header block, keep rows whose first cell is a number."""
    key, text = [], []
    raw = open(path, encoding="utf-8-sig", errors="replace").read().split("\n")
    for line in raw:
        if "\t" not in line:
            continue
        c = line.split("\t")
        k = c[0].strip()
        if not NUMKEY.match(k):
            continue
        # column 2 carries the individualised Extended Strong number (G0001G);
        # it distinguishes homographs that share a base Strong's number
        ext = c[2].strip() if len(c) > 2 else ""
        if ext and NUMKEY.match(ext) and ext != k:
            k = ext
        word = c[3].strip() if len(c) > 3 else ""
        translit = c[4].strip() if len(c) > 4 else ""
        morph = c[5].strip() if len(c) > 5 else ""
        gloss = c[6].strip() if len(c) > 6 else ""
        desc = c[7].strip() if len(c) > 7 else ""
        parts = []
        if word or translit:
            parts.append(f"{word} ({translit})" if translit else word)
        if morph:
            parts.append(morph)
        if gloss:
            parts.append(gloss)
        if desc:
            desc = re.sub(r'<a\b[^>]*>(.*?)</a>', r"\1", desc, flags=re.S | re.I)
            desc = re.sub(r"\[\s*Refs?[^\]]*\]", "", desc)   # STEPBible link stubs
            parts.append(clean(desc))
        t = "\n".join(p for p in parts if p).strip()
        if t:
            key.append(k)
            text.append(t)
    return key, text


PARSERS = {"LSJ": rows_stepbible, "BDB": rows_bdb, "TBESG": rows_stepbible,
           "TBESH": rows_stepbible}


def build(mod):
    spec = SOURCES[mod]
    path = fetch(spec)
    print(f"  parsed from {path} ({os.path.getsize(path)/1e6:.1f} MB)", flush=True)
    keys, texts = PARSERS[mod](path)
    if not keys:
        raise SystemExit(f"no rows for {mod}")
    # repeated keys are legitimate here (homographs): qualify them
    seen, k2, t2, dropped = {}, [], [], 0
    for k, t in zip(keys, texts):
        base = k
        if k in seen:
            if seen[k] == t:
                dropped += 1
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
        "module_name": pa.array([spec["module_name"]] * n, pa.string()),
        "category": pa.array([spec["category"]] * n, pa.string()),
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
                   compression="zstd", compression_level=19,
                   use_dictionary=False, row_group_size=200000,
                   data_page_size=4 << 20)
    man = {
        "status": "ok",
        "module_id": mod,
        "module_name": spec["module_name"],
        "category": spec["category"],
        "sword_driver": "external:" + mod,
        "language": spec["language"],
        "license": spec["license"],
        "copyright": spec["copyright"],
        "source_name": spec["source_name"],
        "source_url": spec["source_url"],
        "download_url": spec["url"],
        "module_version": spec["version"],
        "sword_version_date": "",
        "text_source": spec["text_source"],
        "markup_source_type": spec["markup_source_type"],
        "about": spec["about"],
        "entry_count": n,
        "empty_entries_skipped": 0,
        "duplicate_entries_dropped": dropped,
        "repeated_keys_disambiguated": sum(1 for k in k2 if re.search(r" \(\d+\)$", k)),
        "char_count": sum(len(t) for t in t2),
        "scripture_linked_entries": 0,
        "retrieved": "2026-10-28",
    }
    print(f"  {mod:6s} {n:7d} entries {man['char_count']/1e6:7.2f} Mchars  "
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
        print(f"[{m}] fetching + parsing", flush=True)
        manifest[m] = build(m)
        json.dump(list(manifest.values()), open(man_path, "w"), indent=1)
    print("done:", ", ".join(mods))


if __name__ == "__main__":
    main()
