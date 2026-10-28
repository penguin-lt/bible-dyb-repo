"""Combine the per-module partitions into one reference.parquet + manifests.

Streaming: one partition is held in memory at a time, so this stays inside a
2 GB box even though the concatenated text is ~390 M characters.

    reference.parquet          combined table, all modules
    modules.parquet / .csv     manifest, one row per ingested module
    modules_excluded.csv       modules we looked at and did not ingest, with reasons
    stats.json                 headline counts
"""
import csv
import glob
import json
import os

import pyarrow as pa
import pyarrow.parquet as pq

OUT = "/tmp/out"
COMBINED = os.path.join(OUT, "reference.parquet")
MANIFEST_COLS = [
    "module_id", "module_name", "category", "sword_driver", "language", "license",
    "copyright", "source_name", "source_url", "download_url", "module_version",
    "sword_version_date", "text_source", "markup_source_type", "about",
    "entry_count", "empty_entries_skipped", "duplicate_entries_dropped",
    "repeated_keys_disambiguated", "char_count", "scripture_linked_entries",
    "retrieved",
]


def main():
    manifest = {r["module_id"]: r for r in json.load(open(os.path.join(OUT, "modules.json")))
                if r.get("status") == "ok"}
    parts = sorted(glob.glob(os.path.join(OUT, "partitioned", "*.parquet")))
    parts = [p for p in parts if os.path.basename(p)[:-8] in manifest]
    if os.path.exists(COMBINED):
        os.remove(COMBINED)

    writer = None
    rows = chars = 0
    for i, p in enumerate(sorted(parts, key=lambda x: os.path.basename(x).lower()), 1):
        t = pq.read_table(p)
        if writer is None:
            writer = pq.ParquetWriter(COMBINED, t.schema, compression="zstd",
                                      compression_level=19, use_dictionary=False)
        writer.write_table(t, row_group_size=200000)
        rows += t.num_rows
        chars += int(t.column("char_count").to_pylist().__len__() and
                     sum(t.column("char_count").to_pylist()))
        print(f"[{i}/{len(parts)}] {os.path.basename(p)[:-8]:24s} {t.num_rows:7d} rows "
              f"{os.path.getsize(COMBINED)/1e6:7.1f} MB", flush=True)
        del t
    writer.close()

    mrows = []
    for mid, r in manifest.items():
        mrows.append({k: r.get(k, "") for k in MANIFEST_COLS})
    mrows.sort(key=lambda r: r["module_id"].lower())
    pq.write_table(pa.Table.from_pylist(mrows), os.path.join(OUT, "modules.parquet"),
                   compression="zstd", compression_level=19)
    with open(os.path.join(OUT, "modules.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(mrows)

    plan = json.load(open("/tmp/plan.json"))
    excl = [{"module_id": s["module"], "reason": s["reason"],
             "module_name": s["desc"], "language": s["lang"]} for s in plan["skipped"]]
    excl.sort(key=lambda r: r["module_id"].lower())
    with open(os.path.join(OUT, "modules_excluded.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["module_id", "module_name", "language", "reason"],
                           quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(excl)

    cat = {}
    for r in mrows:
        c = cat.setdefault(r["category"], {"modules": 0, "entries": 0, "chars": 0})
        c["modules"] += 1
        c["entries"] += int(r["entry_count"])
        c["chars"] += int(r["char_count"])
    stats = {
        "modules": len(mrows),
        "entries": rows,
        "chars": sum(int(r["char_count"]) for r in mrows),
        "by_category": cat,
        "languages": sorted({r["language"] for r in mrows}),
        "combined_bytes": os.path.getsize(COMBINED),
        "partitioned_bytes": sum(os.path.getsize(p) for p in parts),
        "excluded_modules": len(excl),
    }
    json.dump(stats, open(os.path.join(OUT, "stats.json"), "w"), indent=1)
    print(json.dumps(stats, indent=1)[:1200])


if __name__ == "__main__":
    main()
