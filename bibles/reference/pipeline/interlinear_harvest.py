"""STEPBible tagged originals: Greek NT and Hebrew OT interlinears.

STEPBible (Tyndale House Cambridge) publishes word-by-word tagged originals under
CC BY 4.0. This harvester turns them into genuine interlinear rows — one row per
verse, each showing the original-language word, its transliteration, its gloss
and its morphology, aligned in reading order. That is the "Interlinears & Reverse
Interlinears" area, which was empty before.

    TAGNT   Greek NT  (Matthew-John, Acts-Revelation)   ~137k words
    TAHOT   Hebrew OT (Genesis-Deuteronomy, ...)        ~305k words

Each line of the source is one *word*:

    Job.1.3#01=L \\t וַ/יְהִ֣י \\t va/y.Hi \\t and/ it was \\t H9001/{H1961} \\t Hc/Vqw3ms ...

so a verse is assembled by grouping on the first three dot-separated columns.
The whole-word rendering keeps the source's own segmentation slash: the database
stores plain reading text, and a tagged original is exactly the case where the
segmentation *is* the content.

    python3 interlinear_harvest.py [--only TAGNT,TAHOT]
    python3 interlinear_harvest.py --survey     # count words and verses, write nothing
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harvest import SCHEMA, OUT  # noqa: E402

DL = os.environ.get("REF_CACHE", "/home/user/scratch/cache/step")
UA = {"User-Agent": "bible-reference-harvest/1.0 (+https://github.com/penguin-lt/bible-dyb-repo)"}
BASE = "https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/Translators%20Amalgamated%20OT%2BNT/"

SOURCES = {
    "TAGNT_Mat-Jhn": {
        "file": "TAGNT Mat-Jhn - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt",
        "name": "STEPBible TAGNT — Translators Amalgamated Greek NT (Matthew–John), interlinear",
        "lang": "grc", "topic": "Interlinears & Reverse Interlinears", "split": "TAGNT",
    },
    "TAGNT_Act-Rev": {
        "file": "TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt",
        "name": "STEPBible TAGNT — Translators Amalgamated Greek NT (Acts–Revelation), interlinear",
        "lang": "grc", "topic": "Interlinears & Reverse Interlinears", "split": "TAGNT",
    },
    "TAHOT_Gen-Deu": {
        "file": "TAHOT Gen-Deu - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt",
        "name": "STEPBible TAHOT — Translators Amalgamated Hebrew OT (Genesis–Deuteronomy), interlinear",
        "lang": "he", "topic": "Interlinears & Reverse Interlinears", "split": "TAHOT",
    },
    "TAHOT_Jos-Est": {
        "file": "TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt",
        "name": "STEPBible TAHOT — Translators Amalgamated Hebrew OT (Joshua–Esther), interlinear",
        "lang": "he", "topic": "Interlinears & Reverse Interlinears", "split": "TAHOT",
    },
    "TAHOT_Job-Sng": {
        "file": "TAHOT Job-Sng - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt",
        "name": "STEPBible TAHOT — Translators Amalgamated Hebrew OT (Job–Song of Songs), interlinear",
        "lang": "he", "topic": "Interlinears & Reverse Interlinears", "split": "TAHOT",
    },
    "TAHOT_Isa-Mal": {
        "file": "TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt",
        "name": "STEPBible TAHOT — Translators Amalgamated Hebrew OT (Isaiah–Malachi), interlinear",
        "lang": "he", "topic": "Interlinears & Reverse Interlinears", "split": "TAHOT",
    },
}
LICENSE = "Creative Commons: BY 4.0"

# Verse-level extras derived from the same tagged files. The interlinear rows
# carry the gloss and the morphology tag inline; these pull each dimension out
# into its own dataset so it can be joined, filtered or counted on its own.
EXTRAS = {
    "MORPHGRK": {"name": "STEPBible TAGNT — Greek morphology, verse by verse",
                 "topic": "Morphology & Parsing Data", "lang": "grc", "split": "TAGNT"},
    "MORPHHEB": {"name": "STEPBible TAHOT — Hebrew morphology, verse by verse",
                 "topic": "Morphology & Parsing Data", "lang": "he", "split": "TAHOT"},
    "STRONGSGRK": {"name": "STEPBible TAGNT — disambiguated Strong's tags, verse by verse",
                   "topic": "Lexical Datasets (Domain/Semantic)", "lang": "grc", "split": "TAGNT"},
    "STRONGSHEB": {"name": "STEPBible TAHOT — disambiguated Strong's tags, verse by verse",
                   "topic": "Lexical Datasets (Domain/Semantic)", "lang": "he", "split": "TAHOT"},
}
SPLIT_FILES = {"TAGNT": ["TAGNT_Mat-Jhn", "TAGNT_Act-Rev"],
               "TAHOT": ["TAHOT_Gen-Deu", "TAHOT_Jos-Est", "TAHOT_Job-Sng", "TAHOT_Isa-Mal"]}

# word line: Book.C. V #nn =L \t word \t translit \t gloss \t dStrong \t grammar ...
# TAGNT puts ref, word and transliteration in column 0; TAHOT gives them as three
# separate columns. Both are matched here and split out below.
WORD = re.compile(r"^([1-3]?[A-Z][a-z]{1,2})\.(\d+)\.(\d+)#(\d+)(=\S+)?\t")


def fetch(spec):
    os.makedirs(DL, exist_ok=True)
    p = os.path.join(DL, spec["file"])
    if os.path.exists(p) and os.path.getsize(p) > 100000:
        return p
    url = BASE + urllib.parse.quote(spec["file"])
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, \
            open(p, "wb") as fh:
        while True:
            c = r.read(1 << 20)
            if not c:
                break
            fh.write(c)
    return p


def verses(path, spec):
    """Group word lines into verses, preserving word order."""
    cur, words = None, []
    order = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        next(fh, None)
        for line in fh:
            m = WORD.match(line)
            if not m:
                continue
            book, ch, vs = m.group(1), m.group(2), m.group(3)
            key = (book, int(ch), int(vs))
            cols = line.rstrip("\n").split("\t")
            if spec["split"] == "TAHOT":
                # 0=ref 1=word 2=transliteration 3=gloss 4=dStrong 5=grammar
                word = cols[1].strip()
                translit = cols[2].strip() if len(cols) > 2 else ""
                gloss = cols[3].strip() if len(cols) > 3 else ""
                gram = cols[5].strip() if len(cols) > 5 else ""
                strong = cols[4].strip() if len(cols) > 4 else ""
            else:
                # TAGNT columns: 0="Mat.1.1#01=NKO" 1="Βίβλος (Biblos)"
                # 2="[The] book" 3="G0976=N-NSF" 4="βίβλος=book"
                word = cols[1].strip() if len(cols) > 1 else ""
                translit = ""
                if " (" in word:
                    word, translit = word.split(" (", 1)
                    translit = translit.rstrip(")")
                gloss = cols[2].strip() if len(cols) > 2 else ""
                dstr = cols[3].strip() if len(cols) > 3 else ""
                gram = dstr.split("=", 1)[1] if "=" in dstr else ""
                strong = dstr.split("=", 1)[0] if "=" in dstr else dstr
            if not word:
                continue
            if key != cur:
                if cur and words:
                    order.append((cur, words))
                cur, words = key, []
            words.append((word, translit, gloss, gram, strong))
    if cur and words:
        order.append((cur, words))
    return order


def render(words):
    """One line per word: original \u2014 transliteration \u2014 gloss [morphology]."""
    out = []
    for word, translit, gloss, gram, strong in words:
        w = word.replace("\\/", "/").replace("\\", "")
        bits = [w]
        if translit:
            bits.append("(" + translit.replace("/", "") + ")")
        if gloss:
            bits.append(gloss.replace("/", " "))
        if gram:
            bits.append("[" + gram + "]")
        out.append(" ".join(bits))
    return "  ".join(out)


BOOK_IDS = {}


def book_id(b):
    return {"Gen": "GEN", "Exo": "EXO", "Lev": "LEV", "Num": "NUM", "Deu": "DEU",
            "Jos": "JOS", "Jdg": "JDG", "Rut": "RUT", "1Sa": "1SA", "2Sa": "2SA",
            "1Ki": "1KI", "2Ki": "2KI", "1Ch": "1CH", "2Ch": "2CH", "Ezr": "EZR",
            "Neh": "NEH", "Est": "EST", "Job": "JOB", "Psa": "PSA", "Pro": "PRO",
            "Ecc": "ECC", "Sng": "SNG", "Isa": "ISA", "Jer": "JER", "Lam": "LAM",
            "Ezk": "EZK", "Dan": "DAN", "Hos": "HOS", "Jol": "JOL", "Amo": "AMO",
            "Oba": "OBA", "Jon": "JON", "Mic": "MIC", "Nam": "NAM", "Hab": "HAB",
            "Zep": "ZEP", "Hag": "HAG", "Zec": "ZEC", "Mal": "MAL",
            "Mat": "MAT", "Mrk": "MRK", "Luk": "LUK", "Jhn": "JHN", "Act": "ACT",
            "Rom": "ROM", "1Co": "1CO", "2Co": "2CO", "Gal": "GAL", "Eph": "EPH",
            "Php": "PHP", "Col": "COL", "1Th": "1TH", "2Th": "2TH", "1Ti": "1TI",
            "2Ti": "2TI", "Tit": "TIT", "Phm": "PHM", "Heb": "HEB", "Jas": "JAS",
            "1Pe": "1PE", "2Pe": "2PE", "1Jn": "1JN", "2Jn": "2JN", "3Jn": "3JN",
            "Jud": "JUD", "Rev": "REV"}.get(b, b.upper())


def build(mod, dry=False):
    spec = SOURCES[mod]
    path = fetch(spec)
    vs = verses(path, spec)
    n = len(vs)
    if dry:
        words = sum(len(w) for _, w in vs)
        print(f"  {mod:14s} {n:6d} verses {words:8d} words {sum(len(render(w)) for _, w in vs)/1e6:6.2f} Mchars")
        return None
    keys = [f"{b} {c}:{v}" for (b, c, v), _ in vs]
    texts = [render(w) for _, w in vs]
    bids = [book_id(b) for (b, c, v), _ in vs]
    chap = [c for (b, c, v), _ in vs]
    vers = [v for (b, c, v), _ in vs]
    table = pa.table({
        "module_id": pa.array([mod] * n, pa.string()),
        "module_name": pa.array([spec["name"]] * n, pa.string()),
        "category": pa.array(["Interlinear"] * n, pa.string()),
        "entry_key": pa.array(keys, pa.string()),
        "entry_order": pa.array(list(range(n)), pa.int32()),
        "book_id": pa.array(bids, pa.string()),
        "chapter": pa.array(chap, pa.int16()),
        "verse": pa.array(vers, pa.int16()),
        "entry_text": pa.array(texts, pa.string()),
        "char_count": pa.array([len(t) for t in texts], pa.int32()),
    }, schema=SCHEMA)
    os.makedirs(os.path.join(OUT, "partitioned"), exist_ok=True)
    pq.write_table(table, os.path.join(OUT, "partitioned", mod + ".parquet"),
                   compression="zstd", compression_level=19, use_dictionary=False,
                   row_group_size=200000, data_page_size=4 << 20)
    man = {
        "status": "ok", "module_id": mod, "module_name": spec["name"],
        "category": "Interlinear", "topic": spec["topic"],
        "sword_driver": "external:stepbible", "language": spec["lang"],
        "license": LICENSE, "license_basis": "stated", "copyright": "",
        "source_name": "STEPBible (Tyndale House Cambridge)",
        "source_url": "https://github.com/STEPBible/STEPBible-Data",
        "download_url": BASE + urllib.parse.quote(spec["file"]),
        "module_version": "STEPBible-Data master", "sword_version_date": "",
        "text_source": spec["file"], "markup_source_type": "TSV word-tagged",
        "about": "Word-by-word tagged original with transliteration, gloss and "
                 "morphology; one row per verse, words in reading order.",
        "entry_count": n, "empty_entries_skipped": 0, "duplicate_entries_dropped": 0,
        "repeated_keys_disambiguated": 0, "char_count": sum(len(t) for t in texts),
        "scripture_linked_entries": n, "retrieved": "2026-10-28",
    }
    sidecar = os.path.join(OUT, "manifests")
    os.makedirs(sidecar, exist_ok=True)
    json.dump(man, open(os.path.join(sidecar, mod + ".json"), "w"), indent=1)
    print(f"  {mod:14s} {n:6d} verses {man['char_count']/1e6:6.2f} Mchars "
          f"{os.path.getsize(os.path.join(OUT,'partitioned',mod+'.parquet'))/1e6:5.1f} MB",
          flush=True)
    return man


def build_extra(mod, dry=False):
    """One row per verse carrying a single dimension (morphology or Strong's)."""
    spec = EXTRAS[mod]
    per_key, per_bid, per_ch, per_vs = {}, {}, {}, {}
    order = []
    for src in SPLIT_FILES[spec["split"]]:
        path = fetch(SOURCES[src])
        for (b, c, v), words in verses(path, SOURCES[src]):
            key = f"{b} {c}:{v}"
            if spec["split"] == "TAHOT":
                vals = [w[3] if mod.startswith("MORPH") else w[4] for w in words]
            else:
                vals = [w[3] if mod.startswith("MORPH") else w[4] for w in words]
            vals = [x for x in (vals or []) if x]
            if not vals:
                continue
            if key not in per_key:
                order.append(key)
                per_key[key] = " ".join(vals)
                per_bid[key] = book_id(b)
                per_ch[key] = c
                per_vs[key] = v
    # morph tags repeat word-for-word; compress runs so the row is readable
    keys = order
    texts = []
    for k in keys:
        parts = per_key[k].split()
        out, prev, run = [], None, 0
        for p in parts:
            if p == prev:
                run += 1
                continue
            if prev is not None:
                out.append(prev if run == 1 else f"{prev} x{run}")
            prev, run = p, 1
        if prev is not None:
            out.append(prev if run == 1 else f"{prev} x{run}")
        texts.append(" ".join(out))
    n = len(keys)
    if dry:
        print(f"  {mod:12s} {n:6d} verses {sum(len(t) for t in texts)/1e6:6.2f} Mchars")
        return None
    table = pa.table({
        "module_id": pa.array([mod] * n, pa.string()),
        "module_name": pa.array([spec["name"]] * n, pa.string()),
        "category": pa.array(["Reference"] * n, pa.string()),
        "entry_key": pa.array(keys, pa.string()),
        "entry_order": pa.array(list(range(n)), pa.int32()),
        "book_id": pa.array([per_bid[k] for k in keys], pa.string()),
        "chapter": pa.array([per_ch[k] for k in keys], pa.int16()),
        "verse": pa.array([per_vs[k] for k in keys], pa.int16()),
        "entry_text": pa.array(texts, pa.string()),
        "char_count": pa.array([len(t) for t in texts], pa.int32()),
    }, schema=SCHEMA)
    os.makedirs(os.path.join(OUT, "partitioned"), exist_ok=True)
    pq.write_table(table, os.path.join(OUT, "partitioned", mod + ".parquet"),
                   compression="zstd", compression_level=19, use_dictionary=False,
                   row_group_size=200000, data_page_size=4 << 20)
    man = {
        "status": "ok", "module_id": mod, "module_name": spec["name"],
        "category": "Reference", "topic": spec["topic"],
        "sword_driver": "external:stepbible", "language": spec["lang"],
        "license": LICENSE, "license_basis": "stated", "copyright": "",
        "source_name": "STEPBible (Tyndale House Cambridge)",
        "source_url": "https://github.com/STEPBible/STEPBible-Data",
        "download_url": "https://github.com/STEPBible/STEPBible-Data",
        "module_version": "STEPBible-Data master", "sword_version_date": "",
        "text_source": "TAGNT / TAHOT", "markup_source_type": "TSV word-tagged",
        "about": "One row per verse: the morphology (or Strong's) codes of every word "
                 "in reading order, with repeated codes compressed.",
        "entry_count": n, "empty_entries_skipped": 0, "duplicate_entries_dropped": 0,
        "repeated_keys_disambiguated": 0, "char_count": sum(len(t) for t in texts),
        "scripture_linked_entries": n, "retrieved": "2026-10-28",
    }
    sidecar = os.path.join(OUT, "manifests")
    os.makedirs(sidecar, exist_ok=True)
    json.dump(man, open(os.path.join(sidecar, mod + ".json"), "w"), indent=1)
    print(f"  {mod:12s} {n:6d} verses {man['char_count']/1e6:6.2f} Mchars", flush=True)
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--survey", action="store_true")
    a = ap.parse_args()
    if a.only:
        names = [m.strip() for m in a.only.split(",") if m.strip()]
    else:
        names = list(SOURCES) + list(EXTRAS)
    for m in names:
        if m in EXTRAS:
            build_extra(m, dry=a.survey)
        else:
            build(m, dry=a.survey)


if __name__ == "__main__":
    main()
