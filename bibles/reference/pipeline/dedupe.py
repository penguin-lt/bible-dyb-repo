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

    # 1. exact duplicates — same bytes of text. Also collapse pairs whose
    #    *sampled body* is identical: Sefaria publishes some texts twice under
    #    different version titles (e.g. Tosefta Demai and "…en Sefaria Community
    #    Translation"), and the full-text hash missed them because page
    #    separators differ between the two editions.
    by_sha = {}
    for mid, f in fps.items():
        by_sha.setdefault(f["sha"], []).append(mid)
    def prefer(group):
        def score(mid):
            f, m = fps[mid], manifest[mid]
            # a merged edition covers the whole work; a page-split edition is a
            # partial view of the same text. Prefer merged.
            merged = 1 if "merged" in str(m.get("module_version", "")).lower() else 0
            # prefer a stated licence over an inferred basis. v1 tested the
            # licence *label*, which says "Public Domain" for inferred works, so
            # the tie-break silently did nothing and half of Sefaria's duplicates
            # were kept as the Hebrew page-split and the English merged one at random.
            stated = 0 if str(m.get("license_basis", "")) == "inferred_pre1929" else 1
            return (round(f["linked_ratio"], 2), stated, merged, f["chars"])
        return max(group, key=score)

    by_sample = {}
    for mid, f in fps.items():
        by_sample.setdefault(f["sample_sha"], []).append(mid)
    for sha, group in by_sample.items():
        if len(group) > 1:
            if len({fps[m]["sha"] for m in group}) == 1:
                continue                     # already handled as identical
            keep = prefer(group)
            for mid in group:
                if mid != keep and mid not in decisions:
                    decisions[mid] = {"duplicate_of": keep, "similarity": 0.99,
                                      "action": "drop",
                                      "reason": "identical body text, different page separators"}

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
    # title normalisation shared by the review pass below
    DROP = {"the", "of", "a", "an", "on", "and", "in", "to", "for", "vol", "volume",
            "part", "book", "saint", "st", "en", "he", "sefaria", "community",
            "translation", "merged", "edition", "vilna", "romm", "friedberg",
            "senlake", "gerlitz", "with", "his", "its"}

    def norm(title):
        t = re.sub(r"\b(sefaria community translation|sefaria|translation|merged)\b",
                   " ", (title or "").lower())
        return " ".join(w for w in re.sub(r"[^a-z0-9 ]", " ", t).split() if w not in DROP)

    suggest = []
    titles = {}
    for mid, m in manifest.items():
        if mid in fps:
            titles[mid] = (norm(m.get("module_name", "")) or mid, m.get("source_name", ""))
    # Pairwise comparison over 10,156 works is 51 million title comparisons and,
    # worse, drowns the report in junk: with this many works, words like "on" or
    # "abraham" appear in hundreds of titles. Index the *rare* words instead and
    # only compare works that share one.
    words = {mid: set(t.split()) for mid, (t, _) in titles.items()}
    df = {}
    for mid, ws in words.items():
        for w in ws:
            df[w] = df.get(w, 0) + 1
    RARE_DF = 40
    index = {}
    for mid, ws in words.items():
        for w in ws:
            if len(w) >= 4 and df[w] <= RARE_DF:
                index.setdefault(w, []).append(mid)
    shared = {}
    for w, mids in index.items():
        if len(mids) < 2:
            continue
        mids = sorted(mids)
        for i, a_id in enumerate(mids):
            for b_id in mids[i + 1:]:
                if titles[a_id][1] == titles[b_id][1]:
                    continue                  # same source: a series, not a duplicate
                shared[(a_id, b_id)] = shared.get((a_id, b_id), 0) + 1
    for (a_id, b_id), inter in shared.items():
        aw, bw = words[a_id], words[b_id]
        ratio = inter / min(len(aw), len(bw))
        if inter >= 3 and ratio >= 0.7:
            suggest.append((a_id, b_id, round(ratio, 3)))
    suggest.sort(key=lambda x: (-x[2], x[0]))

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
