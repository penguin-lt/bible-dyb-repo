#!/usr/bin/env python3
"""Split bibles.parquet into one Parquet file per translation.

`bibles_partitioned/` is a convenience layout, not a separate source of truth:
it holds exactly the same rows as `bibles.parquet`, one file per
`translation_id`, so a query engine can prune to a single small file. Because it
is derived, it is published as a release asset rather than committed, and either
layout regenerates in seconds.

    python3 tools/make_partitions.py                    # -> bibles_partitioned/
    python3 tools/make_partitions.py --zip              # also bibles_partitioned.zip
    python3 tools/make_partitions.py --partitioned      # Hive-style instead
"""
import argparse
import os
import zipfile

import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT = os.path.join(ROOT, "bibles", "text", "bibles.parquet")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bibles", default=DEFAULT)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(DEFAULT),
                                                  "bibles_partitioned"))
    ap.add_argument("--zip", action="store_true",
                    help="also write <out>.zip for release upload")
    ap.add_argument("--partitioned", action="store_true",
                    help="Hive layout: translation_id=<ID>/part-0.parquet")
    ap.add_argument("--level", type=int, default=12)
    a = ap.parse_args()

    t = pq.read_table(a.bibles)
    ids = sorted(set(t.column("translation_id").to_pylist()))
    os.makedirs(a.out, exist_ok=True)
    for tid in ids:
        sub = t.filter(pc.equal(t["translation_id"], tid))
        if a.partitioned:
            d = os.path.join(a.out, f"translation_id={tid}")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "part-0.parquet")
        else:
            path = os.path.join(a.out, f"{tid}.parquet")
        pq.write_table(sub, path, compression="zstd", compression_level=a.level)
    total = sum(os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(a.out) for f in fs)
    print(f"{len(ids)} partitions, {total / 1e6:.1f} MB -> {a.out}")

    if a.zip:
        zp = a.out.rstrip("/") + ".zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
            for r, _, fs in os.walk(a.out):
                for f in sorted(fs):
                    full = os.path.join(r, f)
                    z.write(full, os.path.relpath(full, os.path.dirname(a.out)))
        print(f"{zp}  {os.path.getsize(zp) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
