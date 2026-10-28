"""Streaming harvest: CrossWire SWORD module -> plain-text entries -> Parquet.

For each module in /tmp/plan.json:
    download  rawzip/<Name>.zip
    unpack    into /tmp/w/<Name>   (a throwaway SWORD_PATH)
    dump      mod2imp <Name>       (whole module as "$$$KEY" + markup blocks)
    normalise markup -> plain reading text (normalize.clean)
    write     reference_partitioned/<Module>.parquet  and append to reference.parquet
    delete    the zip, the unpacked module and the dump

Needs: libsword-utils (mod2imp), unzip, curl, pyarrow, zstandard.
Run:   python3 harvest.py [--limit N] [--only NAME[,NAME]]
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from normalize import clean, split_entry_blocks  # noqa: E402

RAWZIP = "https://www.crosswire.org/ftpmirror/pub/sword/packages/rawzip/"
WORK = "/tmp/w"
OUT = "/tmp/out"

SCHEMA = pa.schema([
    ("module_id", pa.string()),
    ("module_name", pa.string()),
    ("category", pa.string()),
    ("entry_key", pa.string()),
    ("entry_order", pa.int32()),
    ("book_id", pa.string()),
    ("chapter", pa.int16()),
    ("verse", pa.int16()),
    ("entry_text", pa.string()),
    ("char_count", pa.int32()),
])

BOOKS = {
    "genesis": "GEN", "exodus": "EXO", "leviticus": "LEV", "numbers": "NUM",
    "deuteronomy": "DEU", "joshua": "JOS", "judges": "JDG", "ruth": "RUT",
    "1 samuel": "1SA", "2 samuel": "2SA", "1 kings": "1KI", "2 kings": "2KI",
    "1 chronicles": "1CH", "2 chronicles": "2CH", "ezra": "EZR", "nehemiah": "NEH",
    "esther": "EST", "job": "JOB", "psalms": "PSA", "psalm": "PSA", "ps": "PSA",
    "proverbs": "PRO", "ecclesiastes": "ECC", "song of solomon": "SNG",
    "song of songs": "SNG", "canticles": "SNG", "isaiah": "ISA", "jeremiah": "JER",
    "lamentations": "LAM", "ezekiel": "EZK", "daniel": "DAN", "hosea": "HOS",
    "joel": "JOL", "amos": "AMO", "obadiah": "OBA", "jonah": "JON", "micah": "MIC",
    "nahum": "NAM", "habakkuk": "HAB", "zephaniah": "ZEP", "haggai": "HAG",
    "zechariah": "ZEC", "malachi": "MAL", "matthew": "MAT", "mark": "MRK",
    "luke": "LUK", "john": "JHN", "acts": "ACT", "romans": "ROM",
    "1 corinthians": "1CO", "2 corinthians": "2CO", "galatians": "GAL",
    "ephesians": "EPH", "philippians": "PHP", "colossians": "COL",
    "1 thessalonians": "1TH", "2 thessalonians": "2TH", "1 timothy": "1TI",
    "2 timothy": "2TI", "titus": "TIT", "philemon": "PHM", "hebrews": "HEB",
    "james": "JAS", "1 peter": "1PE", "2 peter": "2PE", "1 john": "1JN",
    "2 john": "2JN", "3 john": "3JN", "jude": "JUD", "revelation": "REV",
    "1 esdras": "1ES", "2 esdras": "2ES", "tobit": "TOB", "judith": "JDT",
    "wisdom": "WIS", "sirach": "SIR", "baruch": "BAR", "1 maccabees": "1MA",
    "2 maccabees": "2MA",
}
KEYREF = re.compile(r"^(.*?)\s+(\d+):(\d+)(?:[-–]\d+(?::\d+)?)?$")

TOPPISH = ("topical", "topics", "chain", "daily light", "names", "alphabet",
           "concordance", "definitions and symbols")


def parse_key(key):
    m = KEYREF.match(key.strip())
    if not m:
        return None, None, None
    b = BOOKS.get(m.group(1).strip().lower())
    if not b:
        return None, None, None
    return b, int(m.group(2)), int(m.group(3))


def read_conf(path):
    meta, cur = {}, None
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.rstrip("\r\n")
        m = re.match(r"^([A-Za-z][A-Za-z0-9_]*)\s*=(.*)$", line)
        if line.lstrip().startswith("History_"):
            cur = None
            continue
        if m:
            k, v = m.group(1), m.group(2)
            meta[k] = (meta[k] + " " + v).strip() if k in meta else v.strip()
            cur = k
        elif cur and line.strip() and not line.lstrip().startswith("#"):
            meta[cur] = (meta[cur] + " " + line.strip()).strip()
    out = {}
    for k, v in meta.items():
        out[k] = re.sub(r"\s+", " ", v.replace("\\par", " ")).strip()
    return out


HEAD_PUNCT = (" \t\r\n.,:;\u2013\u2014-\u00b7()[]" + chr(39) + chr(34)
              + "\u2018\u2019\u201c\u201d\u00b4\u02bc\u0060")


def strip_headword(text, key):
    """TEI/OSIS entries often repeat the headword as a <title>; drop that repeat."""
    k = key.strip()
    if not k:
        return text
    t = text.lstrip()
    if t[:len(k)].lower() != k.lower():
        return text
    rest = t[len(k):]
    if not rest or rest[0] not in HEAD_PUNCT:
        return text
    rest = rest.lstrip(HEAD_PUNCT).lstrip()
    return rest if rest else text


def decode_module(raw, enc):
    """SWORD modules carry their own encoding (UTF-8, ISO-8859-1, ...)."""
    e = (enc or "utf-8").strip().lower().replace("-", "")
    prefer = {"utf8": "utf-8", "iso88591": "cp1252", "windows1252": "cp1252",
              "iso885915": "iso8859-15"}.get(e)
    for cand in (prefer, "utf-8", "cp1252", "latin-1"):
        if not cand:
            continue
        try:
            return raw.decode(cand)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def category_of(moddrv, desc):
    d = (desc or "").lower()
    if moddrv in ("zLD", "RawLD", "RawLD4"):
        if any(w in d for w in TOPPISH):
            return "Topical"
        return "Dictionary" if ("dictionary" in d or "cyclopedia" in d
                                or "encyclopedia" in d) else "Lexicon"
    if moddrv in ("zCom", "zCom4", "RawCom"):
        return "Commentary"
    return "Reference"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def harvest_one(sel):
    name = sel["name"]
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    zp = os.path.join(WORK, name + ".zip")
    if not (os.path.exists(zp) and os.path.getsize(zp) > 1000):
        r = run(["curl", "-sS", "-m", "900", "-o", zp, RAWZIP + sel["zip"]])
        if r.returncode or not os.path.exists(zp):
            return None, "download failed"
    r = run(["unzip", "-q", "-o", zp, "-d", d])
    if r.returncode:
        return None, "unzip failed"
    confs = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(d, "mods.d"))
             for f in fs if f.endswith(".conf")]
    if not confs:
        return None, "no .conf in archive"
    meta = read_conf(confs[0])
    sec = re.search(r"(?m)^\s*\[([^\]]+)\]\s*$", open(confs[0], encoding="utf-8", errors="replace").read())
    modname = sec.group(1).strip() if sec else os.path.basename(confs[0])[:-5]
    r = subprocess.run(["mod2imp", modname], capture_output=True,
                       env={**os.environ, "SWORD_PATH": d})
    raw = r.stdout
    if r.returncode or len(raw) < 200:
        return None, "mod2imp failed: " + r.stderr.decode("utf-8", "replace").strip()[:120]
    out_text = decode_module(raw, meta.get("Encoding", "UTF-8"))

    entries = split_entry_blocks(out_text)
    keys, texts, orders, bids, chs, vss = [], [], [], [], [], []
    empty = dup_same = dup_diff = 0
    seen = {}
    for i, (k, body) in enumerate(entries):
        t = strip_headword(clean(body), k)
        if not t:
            empty += 1
            continue
        base = k
        if k in seen:                 # same key twice: drop an exact repeat,
            if seen[k] == t:          # otherwise keep both under a qualified key
                dup_same += 1
                continue
            n = 2
            while k in seen:
                k = f"{base} ({n})"
                n += 1
        if k != base:
            dup_diff += 1
        seen[k] = t
        b, c, v = parse_key(base)
        keys.append(k)
        texts.append(t)
        orders.append(i)
        bids.append(b)
        chs.append(c)
        vss.append(v)
    if not keys:
        return None, "no text after normalisation"

    desc = sel["desc"] or meta.get("Description", name)
    cat = category_of(sel["moddrv"], desc)
    n = len(keys)
    table = pa.table({
        "module_id": pa.array([name] * n, pa.string()),
        "module_name": pa.array([desc] * n, pa.string()),
        "category": pa.array([cat] * n, pa.string()),
        "entry_key": pa.array(keys, pa.string()),
        "entry_order": pa.array(orders, pa.int32()),
        "book_id": pa.array(bids, pa.string()),
        "chapter": pa.array(chs, pa.int16()),
        "verse": pa.array(vss, pa.int16()),
        "entry_text": pa.array(texts, pa.string()),
        "char_count": pa.array([len(t) for t in texts], pa.int32()),
    }, schema=SCHEMA)

    os.makedirs(os.path.join(OUT, "partitioned"), exist_ok=True)
    pq.write_table(table, os.path.join(OUT, "partitioned", name + ".parquet"),
                   compression="zstd", compression_level=19,
                   use_dictionary=False, row_group_size=200000,
                   data_page_size=4 << 20)
    manifest = {
        "module_id": name,
        "module_name": desc,
        "category": cat,
        "sword_driver": sel["moddrv"],
        "language": sel["lang"],
        "license": sel["dist"],
        "copyright": meta.get("Copyright", "")[:900],
        "source_name": "CrossWire SWORD module " + name,
        "source_url": "https://www.crosswire.org/sword/modules/ModInfo.jsp?modName=" + name,
        "download_url": RAWZIP + sel["zip"],
        "module_version": meta.get("Version", ""),
        "sword_version_date": meta.get("SwordVersionDate", ""),
        "text_source": meta.get("TextSource", ""),
        "markup_source_type": meta.get("SourceType", ""),
        "about": meta.get("About", "")[:900],
        "entry_count": n,
        "empty_entries_skipped": empty,
        "duplicate_entries_dropped": dup_same,
        "repeated_keys_disambiguated": dup_diff,
        "char_count": sum(len(t) for t in texts),
        "scripture_linked_entries": sum(1 for b in bids if b),
        "retrieved": "2026-10-28",
    }
    # 2026-10-28 fetch; keep the first date if a rerun happens
    del zp
    return table, manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    plan = json.load(open("/tmp/plan.json"))
    sel = plan["selected"]
    if args.only:
        want = {x.strip().lower() for x in args.only.split(",")}
        sel = [s for s in sel if s["name"].lower() in want]
    if args.limit:
        sel = sel[: args.limit]
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)

    man_path = os.path.join(OUT, "modules.json")
    manifest = {}
    if os.path.exists(man_path):
        manifest = {r["module_id"]: r for r in json.load(open(man_path))}

    for i, s in enumerate(sorted(sel, key=lambda x: x["name"].lower()), 1):
        part = os.path.join(OUT, "partitioned", s["name"] + ".parquet")
        if os.path.exists(part) and s["name"] in manifest:
            print(f"[{i}/{len(sel)}] skip (done) {s['name']}", flush=True)
            continue
        t0 = time.time()
        table, info = harvest_one(s)
        shutil.rmtree(os.path.join(WORK, s["name"]), ignore_errors=True)
        for junk in (s["name"] + ".zip",):
            p = os.path.join(WORK, junk)
            if os.path.exists(p):
                os.remove(p)
        if table is None:
            print(f"[{i}/{len(sel)}] FAIL {s['name']}: {info}", flush=True)
            manifest.setdefault(s["name"], {"module_id": s["name"], "status": "failed",
                                            "error": info, "module_name": s["desc"]})
            continue
        manifest[s["name"]] = {"status": "ok", **info}
        json.dump(list(manifest.values()), open(man_path, "w"), indent=1)
        print(f"[{i}/{len(sel)}] {s['name']:24s} {info['category']:11s} "
              f"{info['entry_count']:7d} entries {info['char_count']/1e6:6.2f} Mchars "
              f"{time.time()-t0:5.1f}s", flush=True)
        del table
    print("harvest complete:", sum(1 for m in manifest.values() if m.get("status") == "ok"),
          "modules")


if __name__ == "__main__":
    main()
