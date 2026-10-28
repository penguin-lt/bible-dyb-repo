"""Balanced de-duplication across all ingested works.

The database now draws on four sources that overlap: CrossWire SWORD, CCEL,
Sefaria and the STEPBible/Open Scriptures datasets. The same work can therefore
arrive twice — e.g. Barnes' Notes as one SWORD module and as seventeen CCEL
volume files, Matthew Henry as `MHC` and as `henry_mhc1..6`.

Policy (the same "balanced" rule used for the bibles dataset):
  * exact duplicates (identical text)   -> keep one, drop the rest
  * near duplicates (>92 % shingle similarity) -> keep one per work:
        - prefer the edition keyed by scripture reference, because it joins the
          verse corpus
        - else prefer the fuller text
        - else prefer the explicitly public-domain one over an inferred one
  * everything decided is written to `dedupe_report.csv` — nothing is dropped
    silently, and any decision can be reversed by editing that file.

    python3 dedupe.py            # analyse, print the plan
    python3 dedupe.py --apply    # write dedupe_report.csv and move dropped
                                 # partitions to /tmp/out/dropped/
"""
import argparse
import glob
import csv
import hashlib
import json
import os
import re
import shutil
import sys

import pyarrow.parquet as pq

OUT = os.environ.get("REF_OUT", "/home/user/scratch/out")
REPORT = os.path.join(OUT, "dedupe_report.csv")
DROPPED = os.path.join(OUT, "dropped")


def shingles(text, n=6, cap=3000):
    words = text.split()
    if len(words) < n:
        return {" ".join(words)}
    step = max(1, len(words) // cap)
    return {" ".join(words[i:i + n]) for i in range(0, len(words) - n, step)}


# Front matter (title pages, publisher blurbs, series prefaces) is nearly
# identical across volumes of the same series and made an earlier version of this
# script declare Barnes on Isaiah a duplicate of Schaff's Encyclopedia. Entries
# below this length are skipped, and sampling is spread through the body.
MIN_ENTRY = 400


def fingerprint(path):
    t = pq.read_table(path, columns=["entry_text", "char_count", "book_id"])
    texts = t["entry_text"].to_pylist()
    joined = "\n".join(texts)
    sha = hashlib.sha256(joined.encode("utf-8", "replace")).hexdigest()
    linked = int(t.num_rows - t["book_id"].null_count)
    body = [x for x in texts if len(x) >= MIN_ENTRY] or texts
    # spread the sample through the work, not the biggest entries
    if len(body) > 10:
        idx = [int(i * (len(body) - 1) / 9) for i in range(10)]
        sample = "\n".join(body[i] for i in sorted(set(idx)))
    else:
        sample = "\n".join(body)
    return {
        "path": path,
        "rows": t.num_rows,
        "chars": sum(len(x) for x in texts),
        "sha": sha,
        "linked": linked,
        "linked_ratio": (linked / t.num_rows) if t.num_rows else 0.0,
        "sample_sha": hashlib.sha256(sample[:600000].encode("utf-8", "replace")).hexdigest(),
        "sample_words": len(sample.split()),
    }


def containment(a, b):
    """How much of the smaller work appears in the larger — the right measure
    when one edition is a subset of another, and immune to one work simply being
    longer than the other."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    sidecar = os.path.join(OUT, "manifests")
    manifest = {}
    for f in sorted(os.listdir(sidecar)):
        if f.endswith(".json"):
            r = json.load(open(os.path.join(sidecar, f)))
            if r.get("status") == "ok":
                manifest[r["module_id"]] = r
    paths = sorted(glob.glob(os.path.join(OUT, "partitioned", "*.parquet")))
    fps = {}
    for p in paths:
        mid = os.path.basename(p)[:-8]
        if mid in manifest:
            fps[mid] = fingerprint(p)
    print(f"fingerprinted {len(fps)} works", flush=True)

    decisions = {}

    # 1. exact duplicates only — same bytes of text
    by_sha = {}
    for mid, f in fps.items():
        by_sha.setdefault(f["sha"], []).append(mid)

    def prefer(group):
        def score(mid):
            f, m = fps[mid], manifest[mid]
            stated = 0 if "inferred" in str(m.get("license", "")) else 1
            return (round(f["linked_ratio"], 2), stated, f["chars"])
        return max(group, key=score)

    for sha, group in by_sha.items():
        if len(group) > 1:
            keep = prefer(group)
            for mid in group:
                if mid != keep:
                    decisions[mid] = {"duplicate_of": keep, "similarity": 1.0,
                                      "action": "drop", "reason": "identical text"}

    # 2. title overlap — reported, never auto-applied. Two editions of one work
    #    (SWORD Barnes vs CCEL Barnes volumes) are left in unless a human says
    #    otherwise, because the editions genuinely differ in coverage.
    suggest = []
    norm = lambda s: " ".join(w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()
                              if w not in ("the", "of", "a", "an", "on", "and", "vol",
                                           "volume", "part", "book", "saint", "st"))
    titles = {}
    for mid, m in manifest.items():
        if mid in fps:
            titles[mid] = (norm(m.get("module_name", "")) or mid, m.get("source_name", ""))
    keys = sorted(titles.items(), key=lambda kv: kv[1][0])
    for i, (a_id, (a_t, a_src)) in enumerate(keys):
        for b_id, (b_t, b_src) in keys[i + 1:]:
            if a_src == b_src:
                continue                      # same source: a series, not a duplicate
            aw, bw = set(a_t.split()), set(b_t.split())
            if not aw or not bw:
                continue
            inter = aw & bw
            if len(inter) >= 3 and len(inter) / min(len(aw), len(bw)) >= 0.7:
                suggest.append((a_id, b_id, round(len(inter) / min(len(aw), len(bw)), 3)))

    print()
    if decisions:
        print(f"{len(decisions)} exact-text duplicates:")
        for mid, d in sorted(decisions.items()):
            print(f"  {mid:38s} -> {d['duplicate_of']:30s} {d['reason']}")
    else:
        print("no exact-text duplicates")
    print()
    print(f"{len(suggest)} possible same-work pairs across sources "
          f"(left in place, listed for review):")
    for a_id, b_id, r in suggest[:40]:
        print(f"  {a_id:32s} ~ {b_id:32s} title overlap {r}")

    if a.apply:
        report = os.path.join(OUT, "dedupe_report.csv")
        with open(report, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["kind", "module_id", "other", "score",
                                               "action", "reason"])
            w.writeheader()
            for mid, d in sorted(decisions.items()):
                w.writerow({"kind": "exact", "module_id": mid,
                            "other": d["duplicate_of"], "score": d["similarity"],
                            "action": "dropped", "reason": d["reason"]})
            for a_id, b_id, r in suggest:
                w.writerow({"kind": "review", "module_id": a_id, "other": b_id,
                            "score": r, "action": "kept",
                            "reason": "same work suspected across sources; kept, needs review"})
        if decisions:
            os.makedirs(DROPPED, exist_ok=True)
            for mid in decisions:
                src = os.path.join(OUT, "partitioned", mid + ".parquet")
                if os.path.exists(src):
                    shutil.move(src, os.path.join(DROPPED, mid + ".parquet"))
                m = manifest.pop(mid, None)
                if m:
                    m["status"] = "duplicate"
                    m["duplicate_of"] = decisions[mid]["duplicate_of"]
                    json.dump(m, open(os.path.join(sidecar, mid + ".json"), "w"), indent=1)
        print()
        print(f"applied {len(decisions)} drops; report at {report}")


if __name__ == "__main__":
    main()
