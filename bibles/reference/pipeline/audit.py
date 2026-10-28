"""Audit the built reference database: invariants, content quality, random sampling.

Run against whatever is in $REF_OUT. Exits non-zero if any check fails.

    python3 audit.py                      # full audit, 400 random rows
    python3 audit.py --rows 2000          # deeper sample
    python3 audit.py --only content       # one section
"""
import argparse
import collections
import hashlib
import json
import os
import random
import re
import sys

import pyarrow.parquet as pq

OUT = os.environ.get("REF_OUT", "/home/user/scratch/out")
PART = os.path.join(OUT, "partitioned")
SIDE = os.path.join(OUT, "manifests")

FAIL = []


def fail(check, detail):
    FAIL.append((check, detail))
    print(f"FAIL {check}  {detail}")


def ok(check, detail=""):
    print(f"PASS {check}  {detail}".rstrip())


def manifests():
    out = {}
    for f in os.listdir(SIDE):
        if f.endswith(".json"):
            m = json.load(open(os.path.join(SIDE, f)))
            if m.get("status") == "ok":
                out[m["module_id"]] = m
    return out


# ---------------------------------------------------------------- structure
def check_structure(man):
    disk = {f[:-8] for f in os.listdir(PART) if f.endswith(".parquet")}
    if disk == set(man):
        ok("manifest and partition sets agree", f"[{len(disk)}]")
    else:
        fail("manifest and partition sets agree",
             f"only-on-disk={sorted(disk - set(man))[:3]} only-in-manifest={sorted(set(man) - disk)[:3]}")
    empty = [f for f in os.listdir(PART) if os.path.getsize(os.path.join(PART, f)) < 200]
    if empty:
        fail("no near-empty partitions", f"{len(empty)} e.g. {empty[:3]}")
    else:
        ok("no near-empty partitions")


# ---------------------------------------------------------------- rows
BAD_MARKUP = re.compile(r"<(/?)(p|div|span|br|i|b|em|strong|sup|note|ref|hi|scripRef|br)\b[^>]{0,80}>")
TEMPLATE = re.compile(r"\{\{[^}]{0,80}\}\}")   # [[..]] is asserted data, not markup
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ENTITIES = re.compile(r"&(amp|lt|gt|quot|nbsp|mdash|ndash|hellip|#\d{2,4});")
HEBREW = re.compile(r"[\u0590-\u05ff]")
GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
LATIN = re.compile(r"[A-Za-z]")


def check_content(man, rows_wanted, seed):
    rnd = random.Random(seed)
    ids = sorted(man)
    sample = rnd.sample(ids, min(rows_wanted, len(ids)))
    problems = collections.Counter()
    examples = collections.defaultdict(list)

    def note(kind, mid, key, snippet=""):
        problems[kind] += 1
        if len(examples[kind]) < 4:
            examples[kind].append(f"{mid}:{key}: {snippet[:110]}")

    rows_seen = 0
    for mid in sample:
        t = pq.read_table(os.path.join(PART, mid + ".parquet"))
        d = t.to_pydict()
        n = t.num_rows
        rows_seen += n
        keys = d["entry_key"]
        texts = d["entry_text"]
        cc = d["char_count"]
        # per-row invariants
        for i in range(n):
            txt = texts[i] or ""
            if not txt.strip():
                note("empty text", mid, keys[i])
                continue
            if cc[i] != len(txt):
                note("char_count wrong", mid, keys[i], f"{cc[i]} != {len(txt)}")
            if BAD_MARKUP.search(txt):
                note("markup", mid, keys[i], txt[:110])
            if TEMPLATE.search(txt):
                note("template residue", mid, keys[i], txt[:110])
            if CONTROL.search(txt):
                note("control chars", mid, keys[i], repr(txt[:60]))
            if ENTITIES.search(txt):
                note("unresolved entity", mid, keys[i], txt[:110])
            if "\ufffd" in txt:
                note("U+FFFD", mid, keys[i], txt[:80])
            if txt.strip().lower().startswith("image of page"):
                note("page-scan placeholder", mid, keys[i], txt[:80])
        # key uniqueness and ordering
        if len(set(keys)) != n:
            dup = [k for k, c in collections.Counter(keys).items() if c > 1][:3]
            note("duplicate keys", mid, str(dup))
        if d["entry_order"] != list(range(n)):
            note("entry_order not 0..n", mid, "")
        # identical consecutive rows = parse failure signal
        reps = sum(1 for i in range(1, n) if texts[i] == texts[i - 1] and len(texts[i]) > 40)
        if n > 20 and reps > n * 0.5:
            note("mostly repeated rows", mid, f"{reps}/{n}")
        # language sanity, only where the manifest is explicit
        lang = (man[mid].get("language") or "")[:2]
        body = " ".join(texts[:200])
        if lang == "he" and len(body) > 2000 and not HEBREW.search(body):
            note("labelled Hebrew but no Hebrew", mid, body[:60])
        if lang in ("grc", "el") and len(body) > 2000 and not GREEK.search(body):
            note("labelled Greek but no Greek", mid, body[:60])
        # Language labelling: only flag an *unsourced* claim. Sefaria and the
        # other external adapters record the text's own actualLanguage, which is
        # authoritative even when the version title carries an English name.
        if mid.startswith("sefaria") or mid.startswith("f1k"):
            pass
        elif lang == "en" and len(body) > 2000 and HEBREW.search(body) and not LATIN.search(body):
            note("labelled English but Hebrew only", mid, body[:60])

    print(f"\n-- content sample: {len(sample)} partitions, {rows_seen:,} rows")
    if not problems:
        ok("row-level content checks", "no problems in sample")
    for kind, c in problems.most_common():
        fail(kind, f"{c} hit(s)")
        for e in examples[kind]:
            print(f"      {e}")


# ---------------------------------------------------------------- duplicates
def check_duplicates(man, cap=3000):
    """Same text in two modules is legitimate (two editions); identical *sample*
    hashes across many partitions hints at a copy or a parser error."""
    rnd = random.Random(11)
    ids = sorted(man)
    seen = collections.defaultdict(list)
    for mid in rnd.sample(ids, min(cap, len(ids))):
        t = pq.read_table(os.path.join(PART, mid + ".parquet"))
        col = t.column("entry_text").to_pylist()
        if len(col) < 5:
            continue
        probe = "\n".join(sorted(rnd.sample(col, min(5, len(col)))))[:4000]
        h = hashlib.sha256(probe.encode("utf-8", "ignore")).hexdigest()[:16]
        seen[h].append(mid)
    clashes = {h: v for h, v in seen.items() if len(v) > 1}
    if clashes:
        fail("no identical text across sampled partitions",
             f"{len(clashes)} group(s): {list(clashes.values())[:3]}")
    else:
        ok("no identical text across sampled partitions", f"[{min(cap, len(ids))} sampled]")


# ---------------------------------------------------------------- manifest
def check_manifest(man):
    bad = []
    for mid, m in man.items():
        for k in ("module_id", "module_name", "topic", "license", "language",
                  "entry_count", "char_count", "source_name", "source_url"):
            if not str(m.get(k, "")).strip():
                bad.append(f"{mid}: empty {k}")
        if m.get("license") not in ("Public Domain", "CC0", "CC BY", "CC BY-SA", "GPL"):
            bad.append(f"{mid}: licence {m.get('license')!r}")
        if int(m.get("entry_count", 0)) <= 0:
            bad.append(f"{mid}: entry_count {m.get('entry_count')}")
    if bad:
        fail("manifest fields complete and licences canonical", f"{len(bad)}: {bad[:4]}")
    else:
        ok("manifest fields complete and licences canonical", f"[{len(man)} works]")


# ---------------------------------------------------------------- taxonomy
def check_taxonomy(man):
    """A work whose *name* announces its kind must be filed under that kind.

    Only the name is checked, not the prose description: a commentary that says
    "should be read interlinearly" is not an interlinear, and TBESG is a lexicon
    that happens to explain morphology codes.
    """
    want = {
        "interlinear": "Interlinears & Reverse Interlinears",
        "morphology codes": "Morphology & Parsing Data",
        "cross-reference": "Cross-Reference Systems",
    }
    lexical = ("tb", "strong", "bdb", "lsj", "ohlex", "lexicon", "dictionary")
    bad = []
    for mid, m in man.items():
        name = (m.get("module_name", "") + " " + mid).lower()
        for k, area in want.items():
            if k in name and m.get("topic") != area:
                if k == "morphology codes" and any(x in name for x in lexical):
                    continue          # a lexicon documenting morphology is a lexicon
                bad.append(f"{mid}: name says '{k}' but topic={m.get('topic')}")
    if bad:
        fail("taxonomy follows the work's own description", f"{len(bad)}: {bad[:6]}")
    else:
        ok("taxonomy follows the work's own description")


# ---------------------------------------------------------------- joins
def check_languages(man):
    """Script must agree with the declared language, in both directions."""
    HE = re.compile(r"[\u0590-\u05ff]")
    GR = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
    LA = re.compile(r"[A-Za-z]")
    # Lexicons, morphology tables and code datasets declare the language they
    # *describe* (a Hebrew lexicon glossed in English, a tag list), so a script
    # share test does not apply to them. Prose works are held to it.
    SKIP_TOPICS = ("Lexical Datasets (Domain/Semantic)", "Morphology & Parsing Data",
                   "Cross-Reference Systems")
    bad = []
    for mid, m in sorted(man.items()):
        if m.get("topic") in SKIP_TOPICS or (m.get("language") or "") == "und":
            continue
        p = os.path.join(PART, mid + ".parquet")
        if not os.path.exists(p):
            continue
        col = pq.read_table(p, columns=["entry_text"]).column("entry_text").to_pylist()
        head = " ".join(x for x in col[:60] if x)[:60000]
        if len(head) < 2000:
            continue
        n = len(head)
        lang = (m.get("language") or "")[:2]
        la = len(LA.findall(head)) / n
        he = len(HE.findall(head)) / n
        gr = len(GR.findall(head)) / n
        if lang == "en" and la < 0.15:
            bad.append(f"{mid}: labelled en, Latin share {la:.2f}")
        if lang == "he" and he < 0.10:
            bad.append(f"{mid}: labelled he, Hebrew share {he:.2f}")
        if lang == "gr" and gr < 0.10:
            bad.append(f"{mid}: labelled grc, Greek share {gr:.2f}")
    if bad:
        fail("declared language matches the script", f"{len(bad)}: {bad[:5]}")
    else:
        ok("declared language matches the script", f"[{len(man)} works]")


def check_join(man):
    """Interlinear and morphology rows must line up with the verse corpus."""
    bibles = os.path.join(os.path.dirname(OUT), "..", "work", "repo", "bibles", "text", "data")
    cands = [bibles + "/bibles.parquet", bibles + "/verses.parquet"]
    path = next((c for c in cands if os.path.exists(c)), None)
    if not path:
        print("SKIP verse join (verse corpus not found)")
        return
    verses = pq.read_table(path, columns=["book_id", "chapter", "verse"]).to_pydict()
    have = set(zip(verses["book_id"], verses["chapter"], verses["verse"]))
    for mid in ("TAGNT_Mat-Jhn", "TAHOT_Job-Sng", "MORPHGRK"):
        p = os.path.join(PART, mid + ".parquet")
        if not os.path.exists(p):
            continue
        d = pq.read_table(p, columns=["book_id", "chapter", "verse"]).to_pydict()
        rows = {(b, c, v) for b, c, v in zip(d["book_id"], d["chapter"], d["verse"]) if b}
        hit = len(rows & have)
        share = hit / max(1, len(rows))
        if share < 0.95:
            fail(f"{mid} joins the verse corpus", f"{hit}/{len(rows)} = {share:.1%}")
        else:
            ok(f"{mid} joins the verse corpus", f"{hit}/{len(rows)} = {share:.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20261028)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    man = manifests()
    print(f"{len(man)} works with status=ok in {SIDE}\n")
    want = {x.strip() for x in a.only.split(",") if x.strip()}

    def go(name, fn, *args):
        if not want or name in want:
            fn(*args)

    go("structure", check_structure, man)
    go("manifest", check_manifest, man)
    go("taxonomy", check_taxonomy, man)
    go("content", check_content, man, a.rows, a.seed)
    go("languages", check_languages, man)
    go("duplicates", check_duplicates, man)
    go("join", check_join, man)

    print()
    if FAIL:
        print(f"RESULT: {len(FAIL)} FAILURES")
        for c, d in FAIL:
            print(f"  - {c}: {d[:140]}")
        sys.exit(1)
    print("RESULT: ALL AUDIT CHECKS PASSED")


if __name__ == "__main__":
    main()
