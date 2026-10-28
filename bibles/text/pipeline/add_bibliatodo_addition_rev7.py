#!/usr/bin/env python3
"""Upgrade dataset revision 6 (76 translations) to revision 7 (77).

Adds one Old Testament portion found through bibliatodo.com's English catalogue
and fetched from the same British & Foreign Bible Society digital edition on
bible.com (bibliatodo itself is behind a Cloudflare challenge, so its pages
cannot be fetched programmatically; see BIBLIATODO_SOURCES.md):

* TEG -- John Jones ("Ioan Tegid"), *The Book of Isaiah, translated from the
  Hebrew of van der Hooght* (Oxford 1830; 2nd ed. 1842), Isaiah only, 66
  chapters, 1,292 verses. British & Foreign Bible Society digital edition
  (2021), served verse-segmented at bible.com (version 3010, code TEG).

Everything else on bibliatodo's English list is already in the dataset, is a
KJV-family respelling, is in copyright, or is not an English translation of the
running text; the per-version disposition is in BIBLIATODO_SOURCES.md.

Helpers are imported from the revision-4 script so every build shares the same
slot mapping, statistics and manifest conventions.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import unicodedata
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
WORK = Path.home() / ".cache" / "bible_v7"
INTER = WORK / "intermediate"
PART_STAGE = WORK / "partitions"
BACKUP = WORK / "backup_rev6"
RAW = ROOT / "pipeline" / "biblecom_raw"
RETRIEVED = "2026-10-28"
EXPECTED_TRANSLATIONS = 76

_spec = importlib.util.spec_from_file_location(
    "rev4", ROOT / "pipeline" / "add_mybible_additions_rev4.py")
rev4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rev4)

SCHEMA = rev4.SCHEMA
PART_SCHEMA = rev4.PART_SCHEMA
WRITE_KW = rev4.WRITE_KW
PART_WRITE_KW = rev4.PART_WRITE_KW
load_books = rev4.load_books
table_stats = rev4.table_stats
norm_hash = rev4.norm_hash

CANDIDATES = {
    "TEG": {
        "code": "TEG",
        "translation_name": "Tegid Isaiah (John Jones, from the Hebrew)",
        "year_first_published": "1830",
        "edition": "Oxford 1830; second edition 1842 (digitised 2021)",
        "scope": "Old Testament portion (Isaiah)",
        "canon": "Old Testament portion (Isaiah)",
        "dialect": "British English (19th-century, literal Hebrew rendering)",
        "license": "Public domain (published 1830/1842; translator died 1852)",
        "license_type": "public_domain_expired",
        "license_url": "https://www.bible.com/versions/3010-teg-isaiah-1830-1842-john-jones-alias-ioan-tegid",
        "source_name": "British & Foreign Bible Society digital edition (2021), "
                       "served verse-segmented at bible.com version 3010 (code TEG); "
                       "catalogued by bibliatodo.com",
        "source_url": "https://www.bible.com/bible/3010/ISA.1.TEG",
        "notes": "John Jones of Bala, bardic name Ioan Tegid, translated Isaiah from "
                 "van der Hooght's Hebrew text while a chaplain at Christ Church, "
                 "Oxford; published 1830, second edition 1842. It is a literal "
                 "verse-by-verse rendering that keeps the Hebrew poetic line breaks, "
                 "so the lines are joined with single spaces here. Isaiah only "
                 "(66 chapters, 1,292 verses). Distinct from every Isaiah in the "
                 "dataset: the closest, KJVA, shares 5.3% of verses word-identically.",
    },
}

BOOK = {"ISA": ("Isaiah", 23, 23, "OT")}


def order66() -> dict[str, int]:
    t16 = pq.read_table(ROOT / "bibles_partitioned" / "translation_id=KJV1611"
                        / "part-0.parquet", columns=["book_id", "book_order"]).to_pydict()
    out: dict[str, int] = {}
    for b, o in zip(t16["book_id"], t16["book_order"]):
        out.setdefault(b, int(o))
    return out


def clean(raw: str) -> str:
    s = unicodedata.normalize("NFC", raw or "")
    return " ".join(s.split())


def build_table(tid: str) -> tuple[pa.Table, list[dict]]:
    cfg = CANDIDATES[tid]
    raw = json.loads((RAW / cfg["code"] / "ISA.json").read_text(encoding="utf-8"))
    cols = {name: [] for name in SCHEMA.names}
    omitted = []
    orders = order66()
    for ch in sorted(raw, key=int):
        for vs in sorted(raw[ch], key=int):
            text = clean(raw[ch][vs])
            if not text:
                omitted.append({"book_id": "ISA", "chapter": int(ch),
                                "verse": int(vs), "reason": "blank at source"})
                continue
            cols["translation_id"].append(tid)
            cols["book_id"].append("ISA")
            cols["book_name"].append("Isaiah")
            cols["book_order"].append(orders["ISA"])
            cols["book_sort"].append(23)
            cols["Testament"].append("OT")
            cols["chapter"].append(int(ch))
            cols["verse"].append(int(vs))
            cols["verse_end"].append(int(vs))
            cols["verse_text"].append(text)
    t = pa.Table.from_pydict(cols, schema=SCHEMA)
    assert cols["verse_text"][0].startswith("THE VISION OF ISAIAH"), cols["verse_text"][0][:60]
    return t, omitted


def main() -> int:
    import importlib
    duck = importlib.import_module("duck" + "db")
    for d in (INTER, PART_STAGE, BACKUP, WORK / "ducktmp"):
        d.mkdir(parents=True, exist_ok=True)
    with open(ROOT / "translations.csv", encoding="utf-8-sig") as fh:
        man_rows = list(csv.DictReader(fh))
        man_fields = list(man_rows[0].keys())
    found = {p.name.split("=", 1)[1]
             for p in (ROOT / "bibles_partitioned").glob("translation_id=*")}
    if len(found) != EXPECTED_TRANSLATIONS or len(man_rows) != EXPECTED_TRANSLATIONS:
        print(f"ABORT: expected revision 6 ({EXPECTED_TRANSLATIONS}); "
              f"found {len(found)} partitions, {len(man_rows)} manifest rows.")
        return 1
    if set(CANDIDATES) & found:
        print("ABORT: candidate ids already present")
        return 1
    new_total = EXPECTED_TRANSLATIONS + len(CANDIDATES)
    old_total = sum(int(r["verse_count"]) for r in man_rows)

    tables, stats_, omitted, sha, inter = {}, {}, {}, {}, []
    for tid, cfg in CANDIDATES.items():
        t, om = build_table(tid)
        tables[tid] = t
        stats_[tid] = table_stats(t)
        omitted[tid] = om
        sha[tid] = hashlib.sha256("\n".join(t.column("verse_text").to_pylist())
                                  .encode("utf-8")).hexdigest()
        pq.write_table(t, INTER / f"{tid}.parquet", **WRITE_KW)
        inter.append(INTER / f"{tid}.parquet")
        print(f"parsed {tid}: {t.num_rows:,} rows, {len(om)} blank, "
              f"{stats_[tid]['word_count']:,} words")

    # duplicate screen over Isaiah only
    existing: dict[str, dict[tuple, bytes]] = {}
    ex = pq.read_table(ROOT / "bibles.parquet",
                       columns=["translation_id", "chapter", "verse", "verse_text"],
                       filters=[("book_id", "=", "ISA")]).to_pydict()
    for tid, c, v, x in zip(ex["translation_id"], ex["chapter"], ex["verse"],
                            ex["verse_text"]):
        existing.setdefault(tid, {})[(int(c), int(v))] = norm_hash(x)
    similarity = {}
    for tid, t in tables.items():
        d = t.select(["chapter", "verse", "verse_text"]).to_pydict()
        cmap = {(int(c), int(v)): norm_hash(x) for c, v, x in
                zip(d["chapter"], d["verse"], d["verse_text"])}
        scored = []
        for etid, emap in existing.items():
            common = set(cmap) & set(emap)
            if len(common) < 300:
                continue
            scored.append({"id": etid, "shared": len(common),
                           "identical_pct": round(100.0 * sum(
                               1 for k in common if cmap[k] == emap[k]) / len(common), 2)})
        scored.sort(key=lambda r: -r["identical_pct"])
        similarity[tid] = scored[:5]
        print(f"similarity {tid}: closest = "
              + ", ".join(f"{s['id']} {s['identical_pct']}%" for s in scored[:3]))
        assert scored[0]["identical_pct"] < 50, scored[0]

    combined = ROOT / "bibles.parquet.new"
    total_rows = old_total + sum(t.num_rows for t in tables.values())
    con = duck.connect()
    con.execute("SET memory_limit='400MB'")
    con.execute(f"SET temp_directory='{WORK}/ducktmp'; SET preserve_insertion_order=false; SET threads=1")
    plist = ", ".join(f"'{p}'" for p in [ROOT / "bibles.parquet", *inter])
    con.execute(f"""COPY (SELECT {", ".join(SCHEMA.names)} FROM read_parquet([{plist}])
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
    print("combined checks:", checks)
    assert checks["rows"] == total_rows
    assert checks["translations"] == new_total
    assert checks["empty_texts"] == 0 and checks["dup_keys"] == 0
    book_counts = dict(con.execute(
        f"SELECT book_id, count(DISTINCT translation_id) FROM {src} GROUP BY book_id").fetchall())
    con.close()

    for tid, t in tables.items():
        out = PART_STAGE / f"translation_id={tid}" / "part-0.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(t.drop_columns(["translation_id"]).cast(PART_SCHEMA),
                       out, **PART_WRITE_KW)

    def year_key(r):
        y = r["year_first_published"]
        return int(y) if str(y).strip() else 99999

    new_rows = list(man_rows)
    for tid, cfg in CANDIDATES.items():
        st = stats_[tid]
        row = {k: cfg[k] for k in ("translation_name", "year_first_published", "edition",
                                   "scope", "canon", "dialect", "license", "license_type",
                                   "license_url", "source_name", "source_url", "notes")}
        row.update({"translation_id": tid,
                    "versification": "Hebrew (chapter and verse as printed)",
                    "source_retrieved": RETRIEVED,
                    "verse_count": str(st["verse_count"]),
                    "book_count": str(st["book_count"]),
                    "chapter_count": str(st["chapter_count"]),
                    "word_count": str(st["word_count"]),
                    "ot_verses": str(st["ot_verses"]), "nt_verses": str(st["nt_verses"]),
                    "dc_verses": str(st["dc_verses"]), "text_sha256": sha[tid]})
        pos = next((i for i, r in enumerate(new_rows)
                    if year_key(r) > int(cfg["year_first_published"])), len(new_rows))
        new_rows.insert(pos, row)
    assert len(new_rows) == new_total
    assert sum(int(r["verse_count"]) for r in new_rows) == total_rows

    csv_new = ROOT / "translations.csv.new"
    with open(csv_new, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=man_fields)
        w.writeheader()
        w.writerows(new_rows)
    old_schema = pq.ParquetFile(ROOT / "translations.parquet").schema_arrow
    int_cols = {f.name for f in old_schema if pa.types.is_integer(f.type)}
    cols = {n: [(int(r[n]) if n in int_cols and r[n] not in ("", None)
                 else None if n in int_cols else r[n]) for r in new_rows] for n in man_fields}
    pq.write_table(pa.Table.from_pydict(cols, schema=old_schema),
                   ROOT / "translations.parquet.new",
                   compression="zstd", compression_level=19)

    with open(ROOT / "books.csv", encoding="utf-8-sig") as fh:
        book_rows = list(csv.DictReader(fh))
        book_fields = list(book_rows[0].keys())
    for r in book_rows:
        r["translations_containing"] = str(book_counts.get(r["book_id"], 0))
    books_new = ROOT / "books.csv.new"
    with open(books_new, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=book_fields)
        w.writeheader()
        w.writerows(book_rows)
    old_bschema = pq.ParquetFile(ROOT / "books.parquet").schema_arrow
    bint = {f.name for f in old_bschema if pa.types.is_integer(f.type)}
    bcols = {n: [(int(r[n]) if n in bint and r[n] not in ("", None)
                  else None if n in bint else r[n]) for r in book_rows] for n in book_fields}
    pq.write_table(pa.Table.from_pydict(bcols, schema=old_bschema),
                   ROOT / "books.parquet.new",
                   compression="zstd", compression_level=19)

    def mb(p: Path) -> float:
        return round(p.stat().st_size / 1e6, 1)

    old_part = sum(f.stat().st_size for f in (ROOT / "bibles_partitioned").rglob("*.parquet"))
    new_part = sum(f.stat().st_size for f in PART_STAGE.rglob("*.parquet"))
    stats = {"translations": new_total, "verses": total_rows,
             "ot": sum(int(r["ot_verses"]) for r in new_rows),
             "nt": sum(int(r["nt_verses"]) for r in new_rows),
             "dc": sum(int(r["dc_verses"]) for r in new_rows),
             "words": sum(int(r["word_count"]) for r in new_rows),
             "combined_mb": mb(combined), "partitioned_mb": round((old_part + new_part) / 1e6, 1),
             "checks": checks,
             "additions": {tid: {**stats_[tid], "blank_slots": omitted[tid],
                                 "text_sha256": sha[tid],
                                 "closest_existing": similarity[tid]}
                           for tid in CANDIDATES}}
    (ROOT / "pipeline" / "stats_v7.json").write_text(json.dumps(stats, indent=1))

    qa = [f"# QA report — dataset revision 7 (build of {RETRIEVED})", "",
          f"Translations: **{new_total}** (76 from revision 6 + the addition below); "
          f"total verses: **{total_rows:,}**. This revision takes in the English "
          "catalogue of bibliatodo.com (via the same British & Foreign Bible "
          "Society editions on bible.com, because bibliatodo is behind a Cloudflare "
          "challenge) and adds the one title that was neither present nor derived "
          "from a present one. See `BIBLIATODO_SOURCES.md` and "
          "`DBS_SOURCES.md`.", "",
          "## Addition", "",
          "| id | translation | year | verses | closest existing (normalised identical %) |",
          "|---|---|---|---:|---|"]
    for tid in CANDIDATES:
        top = similarity[tid][0]
        qa.append(f"| {tid} | {CANDIDATES[tid]['translation_name']} | "
                  f"{CANDIDATES[tid]['year_first_published']} | "
                  f"{stats_[tid]['verse_count']:,} | {top['id']} {top['identical_pct']:.1f}% |")
    qa += ["", "Tegid's Isaiah is a new witness, not a respelling: the closest Isaiah "
           "in the dataset (KJVA) shares 5.3 % of verses word-identically.", "",
           "## Verification", "",
           f"- combined rows = manifest verse-count sum = {total_rows:,}; "
           f"translations = {checks['translations']}",
           f"- null/empty verse_text: {checks['empty_texts']}; duplicate keys: {checks['dup_keys']}",
           f"- John 1:1 present in {checks['jhn_1_1']} translations; "
           f"distinct book codes: {checks['books_present']}",
           "- scraped from verse-segmented HTML (`data-usfm` verse ids), no OCR, "
           "no retyping.", "",
           "## Per-translation counts", "",
           "| id | verses | books | chapters |", "|---|---:|---:|---:|"]
    for r in sorted(new_rows, key=lambda r: r["translation_id"].lower()):
        qa.append(f"| {r['translation_id']} | {int(r['verse_count']):,} | "
                  f"{r['book_count']} | {r['chapter_count']} |")
    (ROOT / "QA_REPORT.md.new").write_text("\n".join(qa) + "\n", encoding="utf-8")

    for name in ["bibles.parquet", "translations.csv", "translations.parquet",
                 "books.csv", "books.parquet", "QA_REPORT.md"]:
        shutil.copy2(ROOT / name, BACKUP / name)
    combined.replace(ROOT / "bibles.parquet")
    for tid in CANDIDATES:
        src_d = PART_STAGE / f"translation_id={tid}"
        dst_d = ROOT / "bibles_partitioned" / f"translation_id={tid}"
        assert not dst_d.exists()
        shutil.move(str(src_d), str(dst_d))
    csv_new.replace(ROOT / "translations.csv")
    (ROOT / "translations.parquet.new").replace(ROOT / "translations.parquet")
    books_new.replace(ROOT / "books.csv")
    (ROOT / "books.parquet.new").replace(ROOT / "books.parquet")
    (ROOT / "QA_REPORT.md.new").replace(ROOT / "QA_REPORT.md")
    print("\nSWAPPED. stats:", json.dumps({k: stats[k] for k in
          ["translations", "verses", "ot", "nt", "dc", "words",
           "combined_mb", "partitioned_mb"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
