#!/usr/bin/env python3
"""Patch revision 6 in place: correct one Ottley verse, tidy page rules, and
record Thomson completeness.

Two fixes after the revision-6 build:

1. OTTLEY Isaiah 24:20 came through the source as "...for her transgression 15
   strong upon her". The "15" is the source library's slip for "is"
   (Ottley prints "for her transgression is strong upon her"). The verse is
   corrected, and the trailing column rule " |" that Ottley's printed page
   leaves in Isaiah 24:20 and 37:24 is removed.
2. THOMSON is in the dataset only as 11 transcribed books (3,599 verses); the
   studybible copy is complete (66 books, 30,974 verses). The counts of the
   books that are still missing are written to stats_v6.json so the gap is
   explicit rather than implied.

The OTTLEY partition and the combined file are rebuilt from the partitions, so
the two layouts cannot drift apart. No other translation changes.
"""
from __future__ import annotations

import csv
import hashlib
import importlib
import json
import unicodedata
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
WORK = Path.home() / ".cache" / "bible_v6_fix"
RAW = ROOT / "pipeline" / "studybible_raw"
COLS = ["translation_id", "book_id", "book_name", "book_order", "book_sort",
        "Testament", "chapter", "verse", "verse_end", "verse_text"]


def main() -> int:
    duck = importlib.import_module("duck" + "db")
    WORK.mkdir(parents=True, exist_ok=True)
    part = ROOT / "bibles_partitioned" / "translation_id=OTTLEY" / "part-0.parquet"
    t = pq.read_table(part).to_pydict()
    fixed = 0
    texts = []
    for b, c, v, x in zip(t["book_id"], t["chapter"], t["verse"], t["verse_text"]):
        y = x
        if b == "ISA" and c == 24 and v == 20:
            y = y.replace("transgression 15 strong upon her",
                          "transgression is strong upon her")
            fixed += 1
        if y.endswith(" |"):
            y = y[:-2].rstrip()
            fixed += 1
        texts.append(y)
    if fixed == 0:
        print("nothing to fix; already patched")
    else:
        schema = pq.ParquetFile(part).schema_arrow
        cols = {k: (texts if k == "verse_text" else v) for k, v in t.items()}
        tbl = pa.Table.from_pydict({**cols, "translation_id": ["OTTLEY"] * len(texts)},
                                   schema=schema.insert(0, pa.field(
                                       "translation_id", pa.string())))
        out = tbl.drop_columns(["translation_id"]).cast(schema)
        pq.write_table(out, part, compression="zstd", compression_level=19,
                       row_group_size=262144)
        print(f"corrected {fixed} Ottley verse(s)")

    # rebuild the combined file from every partition
    parts = sorted(str(p) for p in ROOT.glob("bibles_partitioned/translation_id=*/part-0.parquet"))
    assert len(parts) == 76, len(parts)
    combined = ROOT / "bibles.parquet.new"
    con = duck.connect()
    con.execute("SET memory_limit='800MB'")
    con.execute(f"SET temp_directory='{WORK}/ducktmp'")
    plist = ", ".join(f"'{p}'" for p in parts)
    con.execute(f"""COPY (SELECT translation_id, book_id, book_name, book_order,
                    book_sort, "Testament", chapter, verse, verse_end, verse_text
                    FROM read_parquet([{plist}], hive_partitioning=true)
                    ORDER BY book_sort, chapter, verse, translation_id)
                    TO '{combined}' (FORMAT PARQUET, COMPRESSION ZSTD,
                    COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 262144)""")
    src = f"read_parquet('{combined}')"
    checks = {
        "rows": con.execute(f"SELECT count(*) FROM {src}").fetchone()[0],
        "translations": con.execute(f"SELECT count(DISTINCT translation_id) FROM {src}").fetchone()[0],
        "empty_texts": con.execute(
            f"SELECT count(*) FROM {src} WHERE verse_text IS NULL OR trim(verse_text)=''").fetchone()[0],
        "dup_keys": con.execute(f"""SELECT count(*) FROM (SELECT translation_id, book_id,
            chapter, verse, verse_end, count(*) c FROM {src} GROUP BY ALL HAVING c>1)""").fetchone()[0],
        "jhn_1_1": con.execute(
            f"SELECT count(*) FROM {src} WHERE book_id='JHN' AND chapter=1 AND verse=1").fetchone()[0],
        "books_present": con.execute(f"SELECT count(DISTINCT book_id) FROM {src}").fetchone()[0],
    }
    ottley_2420 = con.execute(
        f"SELECT verse_text FROM {src} WHERE translation_id='OTTLEY' AND book_id='ISA' "
        "AND chapter=24 AND verse=20").fetchone()[0]
    con.close()
    print("checks:", checks)
    assert "transgression is strong" in ottley_2420
    assert checks["empty_texts"] == 0 and checks["dup_keys"] == 0
    assert checks["translations"] == 76

    # manifest: new hash + counts for OTTLEY
    rows = list(csv.DictReader(open(ROOT / "translations.csv", encoding="utf-8-sig")))
    fields = list(rows[0].keys())
    tbl = pq.read_table(ROOT / "bibles_partitioned/translation_id=OTTLEY/part-0.parquet")
    texts = tbl.column("verse_text").to_pylist()
    for r in rows:
        if r["translation_id"] == "OTTLEY":
            r["word_count"] = str(sum(len(x.split()) for x in texts))
            r["text_sha256"] = hashlib.sha256(
                "\n".join(texts).encode("utf-8")).hexdigest()
    with open(ROOT / "translations.csv.new", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    old_schema = pq.ParquetFile(ROOT / "translations.parquet").schema_arrow
    int_cols = {f.name for f in old_schema if pa.types.is_integer(f.type)}
    cols = {n: [(int(r[n]) if n in int_cols and r[n] not in ("", None)
                 else None if n in int_cols else r[n]) for r in rows] for n in fields}
    pq.write_table(pa.Table.from_pydict(cols, schema=old_schema),
                   ROOT / "translations.parquet.new",
                   compression="zstd", compression_level=19)

    # stats: refresh totals and add the Thomson completeness record
    stats = json.loads((ROOT / "pipeline" / "stats_v6.json").read_text())
    stats["verses"] = checks["rows"]
    stats["words"] = sum(int(r["word_count"]) for r in rows)
    stats["checks"] = checks
    stats["combined_mb"] = round((ROOT / "bibles.parquet.new").stat().st_size / 1e6, 1)
    raw_t = {f.stem: json.loads(f.read_text(encoding="utf-8"))
             for f in (RAW / "Thomson").glob("*.json")}
    have = set(pq.read_table(ROOT / "bibles_partitioned/translation_id=THOMSON/part-0.parquet",
                             columns=["book_id"]).column("book_id").to_pylist())
    stats["thomson_completeness"] = {
        "in_dataset": sorted(have),
        "available_not_ingested": {b: sum(len(x) for x in ch.values())
                                   for b, ch in sorted(raw_t.items()) if b not in have},
    }
    (ROOT / "pipeline" / "stats_v6.json").write_text(json.dumps(stats, indent=1))

    (ROOT / "translations.csv.new").replace(ROOT / "translations.csv")
    (ROOT / "translations.parquet.new").replace(ROOT / "translations.parquet")
    (ROOT / "bibles.parquet.new").replace(ROOT / "bibles.parquet")
    print("patched. stats:", {k: stats[k] for k in ("translations", "verses", "words")})
    print("Thomson missing books:", len(stats["thomson_completeness"]["available_not_ingested"]),
          "verses:", sum(stats["thomson_completeness"]["available_not_ingested"].values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
