"""Repair pass over the harvested partitions, run before combine.

Three jobs, all streaming (one partition in memory at a time):

1. **Licence canonicalisation and enforcement.** Sources word their licences in
   dozens of ways ("Public domain in the U.S.; author DOD 1859", "CC-BY-NC",
   "Released into the Public Domain"). This maps every string to a small
   canonical set and, critically, *removes* any work whose licence is
   non-commercial or no-derivatives. Sefaria's `CC-BY-NC` texts slipped past an
   earlier substring test — "cc-by" matches "cc-by-nc" — the same bug that once
   let SWORD's CC BY-NC-ND modules in.

2. **Empty text removal.** Rows whose text is blank after trimming are dropped
   and counted.

3. **Duplicate key qualification.** Sefaria and CCEL key sections
   "chapter 1", "chapter 1", ... so a work can repeat a key. Later repeats get
   "  (2)", "  (3)" suffixes, mirroring what the SWORD harvester does.

    python3 repair.py [--apply]
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

OUT = os.environ.get("REF_OUT", "/home/user/scratch/out")
REJECTED = os.path.join(OUT, "not_ingested")

# canonical order matters: the first pattern that matches wins
RULES = [
    ("reject", r"by-nc|by-nc-sa|by-nc-nd|by-nd|\bnc\b|non-?commercial|no-?derivat"),
    ("CC0", r"\bcc0\b|cc-0|creative commons zero"),
    ("CC BY-SA", r"by-sa|share-?alike"),
    # Sefaria writes the bare string "CC BY"; match that spelling explicitly as
    # well as the long form. The lookaheads are what keep -nc/-nd out, since
    # "cc by" is a prefix of "cc by-nc".
    ("CC BY", r"creative commons[\s:]*\bby\b(?!-nc|-nd)|creative commons attribution|"
              r"\bcc[\s-]?by\b(?!-nc|-nd)|^cc by$"),
    ("GPL", r"\bgpl\b|general public licen[cs]e"),
    ("Public Domain", r"public domain|public-domain|released into the public|"
                      r"may be copied and distributed freely"),
]


def canonical(license_str, basis):
    s = (license_str or "").lower()
    if not s.strip():
        return ("reject", "no licence statement") if basis != "stated" else ("Public Domain", None)
    for label, pat in RULES:
        if re.search(pat, s):
            if label == "reject":
                return "reject", (license_str or "")[:90]
            return label, None
    return "reject", "unrecognised licence: " + (license_str or "")[:80]


def repair_partition(path):
    t = pq.read_table(path)
    n0 = t.num_rows
    # drop empty text
    mask = pc.invert(pc.equal(pc.utf8_trim_whitespace(t["entry_text"]), ""))
    t = t.filter(mask)
    empties = n0 - t.num_rows
    keys = t["entry_key"].to_pylist()
    seen = set()
    fixed, dups = [], 0
    for k in keys:
        if k in seen:
            base, n = k, 2
            while k in seen:
                k = f"{base}  ({n})"
                n += 1
            dups += 1
        seen.add(k)
        fixed.append(k)
    if dups:
        i = t.schema.get_field_index("entry_key")
        t = t.set_column(i, "entry_key", pa.array(fixed, pa.string()))
    return t, empties, dups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--recheck", action="store_true",
                    help="re-evaluate works previously rejected, using their stored "
                         "original licence wording (for policy corrections)")
    a = ap.parse_args()

    sidecar = os.path.join(OUT, "manifests")
    manifest, parked = {}, {}
    for f in sorted(os.listdir(sidecar)):
        if f.endswith(".json"):
            r = json.load(open(os.path.join(sidecar, f)))
            manifest[r["module_id"]] = r
            if r.get("status") == "ok":
                parked[r["module_id"]] = None
            elif a.recheck:
                parked[r["module_id"]] = r

    rejected, relabelled, repaired = [], 0, 0
    tot_empty = tot_dups = 0
    if a.recheck and not a.apply:
        pass
    for mid, m in sorted(manifest.items()):
        if m.get("status") != "ok" and not a.recheck:
            continue
        # a previously rejected work is judged on the wording it arrived with
        if m.get("status") != "ok":
            # Never guess: only a preserved original wording can overturn a
            # rejection. Without one, canonical(None) would read as Public Domain.
            if not (m.get("license_raw") or "").strip():
                continue
            lic_for_judgement = m["license_raw"]
        else:
            lic_for_judgement = m.get("license")
        canon, why = canonical(lic_for_judgement, m.get("license_basis", "") or "stated")
        if m.get("status") != "ok" and canon != "reject":
            # policy was wrong first time round: put the work back
            if a.apply:
                src = os.path.join(REJECTED, mid + ".parquet")
                if not os.path.exists(src):
                    # already live (e.g. an earlier partial run restored it);
                    # still correct the manifest so status agrees with disk
                    m["status"] = "ok"
                    m["license"] = canon
                    m.pop("reason", None)
                    relabelled += 1
                    json.dump(m, open(os.path.join(sidecar, mid + ".json"), "w"), indent=1)
                    continue
                m["status"] = "ok"
                m["license"] = canon
                m.pop("reason", None)
                relabelled += 1
                json.dump(m, open(os.path.join(sidecar, mid + ".json"), "w"), indent=1)
            else:
                relabelled += 1
            continue
        if canon == "reject":
            rejected.append((mid, m.get("license"), why))
            if a.apply:
                src = os.path.join(OUT, "partitioned", mid + ".parquet")
                if os.path.exists(src):
                    os.makedirs(REJECTED, exist_ok=True)
                    shutil.move(src, os.path.join(REJECTED, mid + ".parquet"))
                m["status"] = "not_ingested"
                m["reason"] = "licence not redistributable: " + str(m.get("license"))[:120]
                json.dump(m, open(os.path.join(sidecar, mid + ".json"), "w"), indent=1)
            continue
        if m.get("license") != canon:
            relabelled += 1
            if a.apply:
                m["license_raw"] = m.get("license", "")
                m["license"] = canon
                json.dump(m, open(os.path.join(sidecar, mid + ".json"), "w"), indent=1)
        path = os.path.join(OUT, "partitioned", mid + ".parquet")
        if not os.path.exists(path):
            continue
        t, empties, dups = repair_partition(path)
        tot_empty += empties
        tot_dups += dups
        if empties or dups:
            repaired += 1
            if a.apply:
                pq.write_table(t, path, compression="zstd", compression_level=19,
                               use_dictionary=False, row_group_size=200000,
                               data_page_size=4 << 20)
                m["empty_entries_skipped"] = int(m.get("empty_entries_skipped", 0)) + empties
                m["repeated_keys_disambiguated"] = int(m.get("repeated_keys_disambiguated", 0)) + dups
                m["entry_count"] = t.num_rows
                m["char_count"] = int(pc.sum(t["char_count"]).as_py())
                json.dump(m, open(os.path.join(sidecar, mid + ".json"), "w"), indent=1)

    print(f"works inspected        {len(manifest)}")
    print(f"works rejected on licence  {len(rejected)}")
    for mid, lic, why in rejected[:25]:
        print(f"  {mid[:44]:46s} {(lic or '')[:40]:42s} {why}")
    if len(rejected) > 25:
        print(f"  ... and {len(rejected)-25} more")
    print(f"licences relabelled    {relabelled}")
    print(f"partitions repaired    {repaired}  (empty rows {tot_empty}, requalified keys {tot_dups})")
    if a.apply:
        print("applied")


if __name__ == "__main__":
    main()
