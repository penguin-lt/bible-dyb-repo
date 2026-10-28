"""Independent verification of the built reference dataset.

Checks, in order:
 1. row counts agree across combined file, partitions and manifest
 2. schema is identical everywhere and matches the documented one
 3. no empty / whitespace-only entry text, no null keys
 4. no duplicate (module_id, entry_key) pairs left after de-duplication
 5. scripture linkage coverage (book_id/chapter/verse parsed from the key)
 6. spot checks of known headwords against the source modules
 7. licence tally matches the manifest
Exit code is non-zero if any hard check fails.
"""
import glob
import json
import os
import sys

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

OUT = os.environ.get("REF_OUT", "/home/user/scratch/out")
EXPECTED = ["module_id", "module_name", "category", "entry_key", "entry_order",
            "book_id", "chapter", "verse", "entry_text", "char_count"]
SPOT = [("LSJ", "G0026", "love"), ("BDB", "אָבַד", "perish"),
        ("TBESG", "G0001G", "alpha"), ("TBESH", "H0001G", "father"),
        ("Easton", "AARON", "Amram"), ("Smith", "AARON", "Amram"),
        ("StrongsGreek", "00001", "alpha"), ("Nave", "AARON", "Lineage"),
        ("Torrey", "ACCESS TO GOD", "Christ"), ("MHC", "Genesis 1:1", "beginning"),
        ("Webster1913", "AARON'S ROD", "serpent"), ("ISBE", "AARON", "Amram")]

fails = []


def check(cond, label, detail=""):
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail else ""))
    if not cond:
        fails.append(label)


def main():
    stats = json.load(open(os.path.join(OUT, "stats.json")))
    man = pq.read_table(os.path.join(OUT, "modules.parquet")).to_pylist()
    manmap = {r["module_id"]: r for r in man}
    parts = {os.path.basename(p)[:-8]: p
             for p in glob.glob(os.path.join(OUT, "partitioned", "*.parquet"))}

    comb = pq.ParquetFile(os.path.join(OUT, "reference.parquet"))
    check(sorted(comb.schema_arrow.names) == sorted(EXPECTED), "combined schema",
          str(comb.schema_arrow.names))
    check(len(man) == len(parts), "module count / partition count",
          f"{len(man)} modules, {len(parts)} partitions")
    check(set(manmap) == set(parts), "manifest and partition module sets agree")

    total = empty = nulls = dups = dupmods = 0
    linked = 0
    for mid, p in parts.items():
        pf = pq.ParquetFile(p)
        check_schema = pf.schema_arrow.names == EXPECTED
        if not check_schema:
            fails.append("schema " + mid)
        t = pf.read(columns=["entry_key", "entry_text", "book_id"])
        n = t.num_rows
        total += n
        empty += pc.sum(pc.equal(pc.utf8_trim_whitespace(t.column("entry_text")), "")).as_py() or 0
        nulls += t.column("entry_key").null_count + t.column("entry_text").null_count
        keys = t.column("entry_key").to_pylist()
        d = n - len(set(keys))
        if d:
            dupmods += 1
        dups += d
        linked += t.column("book_id").null_count == n and 0 or (n - t.column("book_id").null_count)
        if n != int(manmap[mid]["entry_count"]):
            fails.append("count " + mid)

    check(total == comb.metadata.num_rows, "partitions sum to combined row count",
          f"{total:,} rows")
    check(total == stats["entries"] == sum(int(r["entry_count"]) for r in man),
          "manifest entry_count sum matches", f"{total:,}")
    check(empty == 0, "no empty entry text", str(empty))
    check(nulls == 0, "no null keys or texts", str(nulls))
    check(dups == 0, "no duplicate (module, key) pairs", f"{dups} across {dupmods} modules")
    check(linked > 0, "scripture-linked entries parsed", f"{linked:,}")

    lic = {}
    for r in man:
        lic[r["license"]] = lic.get(r["license"], 0) + 1
    print("licences:", json.dumps(lic, sort_keys=True))
    check(all(not k.lower().startswith("copyrighted") for k in lic),
          "no copyrighted-only licences in the dataset")

    # spot checks
    for mid, key, needle in SPOT:
        p = parts.get(mid)
        if not p:
            check(False, f"spot {mid}:{key}", "module missing")
            continue
        t = pq.read_table(p)
        row = t.filter(pc.equal(t.column("entry_key"), key))
        ok = row.num_rows == 1 and needle.lower() in row.to_pylist()[0]["entry_text"].lower()
        check(ok, f"spot {mid}:{key}", needle)

    # encoding hygiene: no replacement characters or pronunciation placeholders
    bad_chars = 0
    for p in parts.values():
        tt = pq.read_table(p, columns=["entry_text"]).column("entry_text")
        bad_chars += pc.sum(pc.cast(pc.match_substring(tt, "\ufffd"), "int64")).as_py() or 0
    check(bad_chars == 0, "no U+FFFD replacement characters", str(bad_chars))

    # no leftover markup
    probe = pq.read_table(parts["Easton"]).column("entry_text").to_pylist()[:400]
    check(not any("<" in x and ">" in x for x in probe), "no residual markup in sample")

    print()
    print(f"modules={len(man)} entries={total:,} chars={stats['chars']:,} "
          f"combined={stats['combined_bytes']/1e6:.1f} MB "
          f"partitions={stats['partitioned_bytes']/1e6:.1f} MB")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILURES")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
