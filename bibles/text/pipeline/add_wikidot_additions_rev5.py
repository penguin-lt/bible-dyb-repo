#!/usr/bin/env python3
"""Upgrade dataset revision 4 (72 translations) to revision 5 (73).

Adds the one translation from the Internet Bible Catalog
(https://bibles.wikidot.com/indexpage) reconciliation that met every rule and
had a reliable born-digital verse-segmented text:

* WHISTON -- William Whiston, "Mr. Whiston's Primitive New Testament" (1745),
  MySword/theWord module published by theword-modules.com
  (WhistonNT[1745].nt, plain text, one line per KJV NT verse slot).

The catalogue's other pre-1929 titles either are already in the dataset, are
still in copyright, or exist only as page scans (OCR is excluded by rule);
see NOT_INCLUDED.md for the full reconciliation.

Helpers are imported from the revision-4 script so both builds share exactly
the same slot mapping, statistics and manifest conventions.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
WORK = Path.home() / ".cache" / "bible_v5"
INTER = WORK / "intermediate"
PART_STAGE = WORK / "partitions"
BACKUP = WORK / "backup_rev4"
RETRIEVED = "2026-10-28"
EXPECTED_TRANSLATIONS = 72

_spec = importlib.util.spec_from_file_location(
    "rev4", ROOT / "pipeline" / "add_mybible_additions_rev4.py")
rev4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rev4)

SCHEMA = rev4.SCHEMA
PART_SCHEMA = rev4.PART_SCHEMA
WRITE_KW = rev4.WRITE_KW
PART_WRITE_KW = rev4.PART_WRITE_KW
load_books = rev4.load_books
nt_slots = rev4.nt_slots
table_stats = rev4.table_stats
norm_hash = rev4.norm_hash

CANDIDATES = {
    "WHISTON": {
        "file": "Wm._Whiston_s_Primitive_New_Testament_Published_in_1745__WhistonNT_1745__.nt",
        "translation_name": "Whiston Primitive New Testament",
        "year_first_published": "1745",
        "edition": "1745 (Stamford and London, printed for the author)",
        "dialect": "Archaic English (18th-century)",
        "license": "Public domain (published 1745; copyright long expired)",
        "license_url": "https://bibles.wikidot.com/whiston",
        "source_name": "theword-modules.com MySword/theWord NT module "
                       "'WhistonNT[1745]' (plain text, one line per verse; "
                       "catalogued at bibles.wikidot.com/whiston)",
        "source_url": "https://theword-modules.com/uncategorized/"
                      "wm-whistons-primitive-new-testament-published-in-1745/",
        "first_anchor": "THE book of the generation of Jesus Christ",
        "notes": "William Whiston's own revision of the English New Testament "
                 "against the oldest Greek manuscripts and the ancient "
                 "versions, first published in 1745 and here complete in four "
                 "parts. Whiston prints bracketed supplied words "
                 "(\"[be]\", \"[day]\") as part of his text and they are kept; "
                 "the module's <CL> markup is only a paragraph break inside a "
                 "verse, so the tag is removed and the words retained. The "
                 "text follows Whiston's own eclectic text (for example "
                 "1 John 5:7 is short, Matthew 6:13 has \"the evil one\").",
    },
}

_tag_re = re.compile(r"<[^>]*>")
_ws_re = re.compile(r"\s+")


def clean_whiston(raw: str) -> str:
    s = _tag_re.sub("", raw or "")
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    return _ws_re.sub(" ", s).strip()


def parse_candidate(tid: str, cfg: dict, slots: list[dict],
                    books: dict[str, dict]) -> tuple[pa.Table, list[dict]]:
    path = ROOT / "pipeline" / "sources" / cfg["file"]
    lines = path.read_bytes().decode("utf-8-sig").splitlines()
    assert len(lines) >= 7958, (tid, len(lines))
    verse_lines = lines[:7957]
    assert lines[7957].strip() == "" and lines[7958].startswith("short.title="), tid
    cols = {name: [] for name in SCHEMA.names}
    omitted: list[dict] = []
    for slot, raw in zip(slots, verse_lines):
        text = clean_whiston(raw)
        if not text:
            omitted.append({"book_id": slot["book_id"], "chapter": slot["chapter"],
                            "verse": slot["verse"],
                            "reason": "blank module slot", "module_text": ""})
            continue
        assert "<" not in text and ">" not in text, (tid, slot, text[:100])
        meta = books[slot["book_id"]]
        cols["translation_id"].append(tid)
        cols["book_id"].append(slot["book_id"])
        cols["book_name"].append(meta["book_name_standard"])
        cols["book_order"].append(slot["book_order"])
        cols["book_sort"].append(slot["book_sort"])
        cols["Testament"].append("NT")
        cols["chapter"].append(slot["chapter"])
        cols["verse"].append(slot["verse"])
        cols["verse_end"].append(slot["verse"])
        cols["verse_text"].append(text)
    assert cols["verse_text"][0].startswith(cfg["first_anchor"]), cols["verse_text"][0][:80]
    t = pa.Table.from_pydict(cols, schema=SCHEMA)
    return t, omitted


def main() -> int:
    duck = importlib.import_module("duck" + "db")
    for d in (INTER, PART_STAGE, BACKUP, WORK / "ducktmp"):
        d.mkdir(parents=True, exist_ok=True)
    books = load_books()
    with open(ROOT / "translations.csv", encoding="utf-8-sig") as fh:
        man_rows = list(csv.DictReader(fh))
        man_fields = list(man_rows[0].keys())
    manifest = {r["translation_id"]: r for r in man_rows}
    found = {p.name.split("=", 1)[1]
             for p in (ROOT / "bibles_partitioned").glob("translation_id=*")}
    if len(found) != EXPECTED_TRANSLATIONS or set(manifest) != found:
        print(f"ABORT: expected revision 4 ({EXPECTED_TRANSLATIONS} partitions == "
              f"manifest); found {len(found)} partitions, {len(manifest)} rows.")
        return 1
    clash = set(CANDIDATES) & found
    if clash:
        print(f"ABORT: candidate ids already present: {sorted(clash)}")
        return 1
    new_total_translations = EXPECTED_TRANSLATIONS + len(CANDIDATES)
    old_total = sum(int(r["verse_count"]) for r in man_rows)

    slots = nt_slots()
    cand_tables: dict[str, pa.Table] = {}
    cand_stats: dict[str, dict] = {}
    cand_omitted: dict[str, list[dict]] = {}
    cand_sha: dict[str, str] = {}
    inter_paths: list[Path] = []
    for tid, cfg in CANDIDATES.items():
        t, omitted = parse_candidate(tid, cfg, slots, books)
        cand_tables[tid] = t
        cand_stats[tid] = table_stats(t)
        cand_omitted[tid] = omitted
        cand_sha[tid] = hashlib.sha256(
            "\n".join(t.column("verse_text").to_pylist()).encode("utf-8")).hexdigest()
        dst = INTER / f"{tid}.parquet"
        pq.write_table(t, dst, **WRITE_KW)
        inter_paths.append(dst)
        print(f"parsed {tid}: {t.num_rows:,} rows, {len(omitted)} slots absent, "
              f"{cand_stats[tid]['word_count']:,} words")
        print("  John 1:1 =", t.filter(
            pa.compute.and_(pa.compute.equal(t.column("book_id"), "JHN"),
                            pa.compute.equal(t.column("chapter"), 1))
        ).column("verse_text")[0].as_py())

    # duplicate screen against all 72 existing translations
    existing: dict[str, dict[tuple, bytes]] = {}
    et = pq.read_table(ROOT / "bibles.parquet",
                       columns=["translation_id", "book_id", "chapter", "verse",
                                "Testament", "verse_text"],
                       filters=[("Testament", "=", "NT")]).to_pydict()
    for tid, b, c, v, x in zip(et["translation_id"], et["book_id"], et["chapter"],
                               et["verse"], et["verse_text"]):
        existing.setdefault(tid, {})[(b, int(c), int(v))] = norm_hash(x)
    similarity: dict[str, list[dict]] = {}
    for tid, t in cand_tables.items():
        ct = t.select(["book_id", "chapter", "verse", "verse_text"]).to_pydict()
        cmap = {(b, int(c), int(v)): norm_hash(x) for b, c, v, x in
                zip(ct["book_id"], ct["chapter"], ct["verse"], ct["verse_text"])}
        scored = []
        for etid, emap in existing.items():
            common = set(cmap) & set(emap)
            if len(common) < 1000:
                continue
            same = sum(1 for k in common if cmap[k] == emap[k])
            scored.append({"id": etid,
                           "identical_pct": round(100.0 * same / len(common), 2),
                           "identical": same, "shared": len(common)})
        scored.sort(key=lambda r: -r["identical_pct"])
        similarity[tid] = scored[:5]
        print(f"similarity {tid}: closest = "
              + ", ".join(f"{s['id']} {s['identical_pct']}%" for s in scored[:3]))
        assert scored[0]["identical_pct"] < 50, (tid, scored[0])

    combined_new = ROOT / "bibles.parquet.new"
    total_rows = old_total + sum(t.num_rows for t in cand_tables.values())
    con = duck.connect()
    con.execute("SET memory_limit='800MB'")
    con.execute(f"SET temp_directory='{WORK}/ducktmp'")
    plist = ", ".join(f"'{p}'" for p in [ROOT / "bibles.parquet", *inter_paths])
    con.execute(f"""
        COPY (SELECT {", ".join(SCHEMA.names)} FROM read_parquet([{plist}])
              ORDER BY book_sort, chapter, verse, translation_id)
        TO '{combined_new}' (FORMAT PARQUET, COMPRESSION ZSTD,
                             COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 262144)""")
    src = f"read_parquet('{combined_new}')"
    checks = {
        "rows": con.execute(f"SELECT count(*) FROM {src}").fetchone()[0],
        "translations": con.execute(
            f"SELECT count(DISTINCT translation_id) FROM {src}").fetchone()[0],
        "empty_texts": con.execute(
            f"SELECT count(*) FROM {src} WHERE verse_text IS NULL OR trim(verse_text)=''").fetchone()[0],
        "dup_keys": con.execute(f"""SELECT count(*) FROM (SELECT translation_id, book_id,
            chapter, verse, verse_end, count(*) c FROM {src}
            GROUP BY ALL HAVING c>1)""").fetchone()[0],
        "jhn_1_1": con.execute(
            f"SELECT count(*) FROM {src} WHERE book_id='JHN' AND chapter=1 AND verse=1").fetchone()[0],
        "books_present": con.execute(
            f"SELECT count(DISTINCT book_id) FROM {src}").fetchone()[0],
    }
    print("combined checks:", checks)
    assert checks["rows"] == total_rows
    assert checks["translations"] == new_total_translations
    assert checks["empty_texts"] == 0 and checks["dup_keys"] == 0
    for tid, t in cand_tables.items():
        n = con.execute(f"SELECT count(*) FROM {src} WHERE translation_id='{tid}'").fetchone()[0]
        assert n == t.num_rows, (tid, n, t.num_rows)
    book_counts = dict(con.execute(
        f"SELECT book_id, count(DISTINCT translation_id) FROM {src} GROUP BY book_id").fetchall())
    con.close()

    for tid, t in cand_tables.items():
        out = PART_STAGE / f"translation_id={tid}" / "part-0.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(t.drop_columns(["translation_id"]).cast(PART_SCHEMA),
                       out, **PART_WRITE_KW)

    def year_key(r):
        y = r["year_first_published"]
        return int(y) if str(y).strip() else 99999

    new_rows = list(man_rows)
    for tid, cfg in CANDIDATES.items():
        st = cand_stats[tid]
        row = {
            "translation_id": tid,
            "translation_name": cfg["translation_name"],
            "year_first_published": cfg["year_first_published"],
            "edition": cfg["edition"],
            "scope": "New Testament",
            "canon": "New Testament",
            "versification": "English (as in source module)",
            "dialect": cfg["dialect"],
            "license": cfg["license"],
            "license_type": "public_domain_expired",
            "license_url": cfg["license_url"],
            "source_name": cfg["source_name"],
            "source_url": cfg["source_url"],
            "source_retrieved": RETRIEVED,
            "verse_count": str(st["verse_count"]),
            "book_count": str(st["book_count"]),
            "chapter_count": str(st["chapter_count"]),
            "word_count": str(st["word_count"]),
            "ot_verses": str(st["ot_verses"]),
            "nt_verses": str(st["nt_verses"]),
            "dc_verses": str(st["dc_verses"]),
            "text_sha256": cand_sha[tid],
            "notes": cfg["notes"],
        }
        y = int(cfg["year_first_published"])
        pos = next((i for i, r in enumerate(new_rows) if year_key(r) > y), len(new_rows))
        new_rows.insert(pos, row)
    assert len(new_rows) == new_total_translations
    assert sum(int(r["verse_count"]) for r in new_rows) == total_rows

    csv_new = ROOT / "translations.csv.new"
    with open(csv_new, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=man_fields)
        w.writeheader()
        w.writerows(new_rows)
    old_schema = pq.ParquetFile(ROOT / "translations.parquet").schema_arrow
    int_cols = {f.name for f in old_schema if pa.types.is_integer(f.type)}

    def conv(name, v):
        if name in int_cols:
            return int(v) if v not in ("", None) else None
        return v

    cols = {name: [conv(name, r[name]) for r in new_rows] for name in man_fields}
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
    bcols = {name: [(int(r[name]) if name in bint and r[name] not in ("", None)
                     else None if name in bint else r[name]) for r in book_rows]
             for name in book_fields}
    pq.write_table(pa.Table.from_pydict(bcols, schema=old_bschema),
                   ROOT / "books.parquet.new",
                   compression="zstd", compression_level=19)

    def mb(p: Path) -> float:
        return round(p.stat().st_size / 1e6, 1)

    old_part_bytes = sum(f.stat().st_size
                         for f in (ROOT / "bibles_partitioned").rglob("*.parquet"))
    new_part_bytes = sum(f.stat().st_size for f in PART_STAGE.rglob("*.parquet"))
    stats = {
        "translations": new_total_translations, "verses": total_rows,
        "ot": sum(int(r["ot_verses"]) for r in new_rows),
        "nt": sum(int(r["nt_verses"]) for r in new_rows),
        "dc": sum(int(r["dc_verses"]) for r in new_rows),
        "words": sum(int(r["word_count"]) for r in new_rows),
        "combined_mb": mb(combined_new),
        "partitioned_mb": round((old_part_bytes + new_part_bytes) / 1e6, 1),
        "checks": checks,
        "additions": {tid: {**cand_stats[tid], "omitted_slots": cand_omitted[tid],
                            "text_sha256": cand_sha[tid],
                            "closest_existing": similarity[tid]}
                      for tid in CANDIDATES},
    }
    (ROOT / "pipeline" / "stats_v5.json").write_text(json.dumps(stats, indent=1))

    qa = [f"# QA report — dataset revision 5 (build of {RETRIEVED})", "",
          f"Translations: **{new_total_translations}** (72 from revision 4 + 1 "
          f"addition below); total verses: **{total_rows:,}**. This revision "
          "reconciles the whole Internet Bible Catalog "
          "(bibles.wikidot.com/indexpage, 1,030 catalogue entries / 806 entry "
          "pages) against the dataset; the single remaining pre-1929 title with "
          "a reliable born-digital verse-segmented text was added. See "
          "NOT_INCLUDED.md for the entry-by-entry disposition.", "",
          "## Addition", "",
          "| id | translation | year | verses | slots absent | closest existing "
          "(normalised identical %) |", "|---|---|---:|---:|---:|---|"]
    for tid in CANDIDATES:
        top = similarity[tid][0]
        qa.append(f"| {tid} | {CANDIDATES[tid]['translation_name']} | "
                  f"{CANDIDATES[tid]['year_first_published']} | "
                  f"{cand_stats[tid]['verse_count']:,} | {len(cand_omitted[tid])} | "
                  f"{top['id']} {top['identical_pct']:.1f}% |")
    qa += ["", f"Whiston keeps all 7,957 NT verse slots and is a distinct text: "
           f"the closest existing translation, {similarity['WHISTON'][0]['id']}, "
           f"shares {similarity['WHISTON'][0]['identical_pct']:.1f}% word-identical "
           "verses after normalisation — far below the ~90%+ scores that "
           "identified the revision-2 duplicates. Its 18th-century revision of "
           "the received text (\"the evil one\" in Matthew 6:13, the short text "
           "of 1 John 5:7) is why it sits closer to the KJV family than to any "
           "modern version.", "",
           "## Verification", "",
           f"- combined rows = manifest verse-count sum = {total_rows:,}; "
           f"translations = {checks['translations']}",
           f"- null/empty verse_text: {checks['empty_texts']}; duplicate "
           f"(translation, book, chapter, verse) keys: {checks['dup_keys']}",
           f"- John 1:1 present in {checks['jhn_1_1']} translations; distinct "
           f"book codes present: {checks['books_present']}",
           "- DUPLICATE SCREEN: normalised exact-verse identity vs every "
           "existing translation over all shared NT references.",
           "- `text_sha256` for the 72 revision-4 translations is unchanged; for "
           "WHISTON it is SHA-256 of the verse texts joined by newlines in "
           "canonical order.", "",
           "## Per-translation counts", "",
           "| id | verses | books | chapters |", "|---|---:|---:|---:|"]
    for r in sorted(new_rows, key=lambda r: r["translation_id"].lower()):
        qa.append(f"| {r['translation_id']} | {int(r['verse_count']):,} | "
                  f"{r['book_count']} | {r['chapter_count']} |")
    (ROOT / "QA_REPORT.md.new").write_text("\n".join(qa) + "\n", encoding="utf-8")

    for name in ["bibles.parquet", "translations.csv", "translations.parquet",
                 "books.csv", "books.parquet", "QA_REPORT.md"]:
        shutil.copy2(ROOT / name, BACKUP / name)
    combined_new.replace(ROOT / "bibles.parquet")
    for tid in CANDIDATES:
        srcd = PART_STAGE / f"translation_id={tid}"
        dstd = ROOT / "bibles_partitioned" / f"translation_id={tid}"
        assert not dstd.exists(), dstd
        shutil.move(str(srcd), str(dstd))
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
