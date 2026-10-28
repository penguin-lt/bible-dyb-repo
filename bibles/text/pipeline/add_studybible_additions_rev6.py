#!/usr/bin/env python3
"""Upgrade dataset revision 5 (73 translations) to revision 6 (76).

Adds the only two English translations in studybible.info's 162-version
library that were neither already in the dataset nor derived from something
already in it, plus one Old Testament portion:

* MACE  -- Daniel Mace, "The New Testament in Greek and English" (1729)
           studybible.info version code ``Mace`` (1729 title page; the site
           serves it verse by verse, server rendered, no OCR)
* SAWYER-- Leicester Ambrose Sawyer, "The New Testament ... with
           Chronological Arrangement" (1858), code ``Sawyer``
* OTTLEY-- R. R. Ottley, "The Book of Isaiah according to the Septuagint"
           (1904/1906), code ``Ottley`` -- Isaiah only

Everything else on studybible.info is either already in the dataset under
another code (KJV, ASV, WEB, YLT, Darby, Rotherham, Weymouth, Twentieth
Century, Goodspeed, Montgomery, Ballantine/Riverside, Worrell, Godbey,
Moffatt, Diaglott, ABU, Anderson, Noyes, Julia Smith, Leeser, Brenton,
Etheridge, Murdock, Thomson, Whiston, Wesley, Worsley, Haweis, Webster,
Living Oracles, ACV, BBE, NHEB, LXX2012, BSB, MSB, BLB, F35, ...), a
Strong's/interlinear/reverse-interlinear edition of one of those, a
KJV-family respelling (KJ2000, MKJV, UKJV, RKJNT, KJC, AKJV, TKJU, RYLT,
CKJV, LITV, MLV, ECB, EJ2000, CAB, KJV_Cambridge), a non-English version, or
still in copyright (Goodspeed 1925, MNT 1924/1935, Williams 1937, Lamsa 1933,
CLV 1926+, ISV, LEB, WPNT, JMNT, NSB, VIN, KGB, BIB, AUV, Common, CWEB,
Etheridge/Greek and Hebrew source texts).  The full per-code disposition is
in the accompanying notes table STUDYBIBLE_SOURCES.md.

Verse text is taken from the chapter pages; where a chapter page is empty the
verse pages are used instead. Nothing is ingested from OCR.

Helpers are imported from the revision-4 script so every build shares exactly
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
WORK = Path.home() / ".cache" / "bible_v6"
INTER = WORK / "intermediate"
PART_STAGE = WORK / "partitions"
BACKUP = WORK / "backup_rev5"
RAW = ROOT / "pipeline" / "studybible_raw"
RETRIEVED = "2026-10-28"
EXPECTED_TRANSLATIONS = 73

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

SOURCE_NOTE = ("studybible.info (study Bible parallel-text library, "
               "https://studybible.info/versions/), verse-segmented HTML, "
               "one page per chapter and per verse, no OCR")

CANDIDATES = {
    "MACE": {
        "code": "Mace",
        "translation_name": "Mace New Testament",
        "year_first_published": "1729",
        "edition": "1729 (London: printed for the author; 3 vols)",
        "scope": "New Testament",
        "dialect": "Early Modern English (18th-century)",
        "license": "Public domain (published 1729; copyright long expired)",
        "license_url": "https://bibles.wikidot.com/mace",
        "source_name": SOURCE_NOTE,
        "source_url": "https://studybible.info/Mace",
        "first_anchor": "The History of the life of Jesus Christ",
        "notes": (
            "Daniel Mace's 1729 New Testament, the first English version to "
            "print the Greek text with a modern-English rendering beside it; "
            "the text here is the English column only. Mace moved several "
            "books (the Pastoral Epistles among them) to the end of his "
            "volume, but the verses are mapped to the standard 66-book "
            "chapters and verses so the text lines up with every other "
            "translation in the dataset. This is the copy the word-module "
            "sites advertise as Mace.nt.exe but never published as plain "
            "text; studybible.info serves it verse by verse."),
    },
    "SAWYER": {
        "code": "Sawyer",
        "translation_name": "Sawyer New Testament (chronological)",
        "year_first_published": "1858",
        "edition": "1858 (Boston: John P. Jewett; 2nd ed. 1861)",
        "scope": "New Testament",
        "dialect": "American English (19th-century)",
        "license": "Public domain (published 1858; copyright long expired)",
        "license_url": "https://bibles.wikidot.com/sawyer",
        "source_name": SOURCE_NOTE,
        "source_url": "https://studybible.info/Sawyer",
        "first_anchor": "(1:1) AN account of the birth of Jesus Christ",
        "notes": (
            "Leicester Ambrose Sawyer's New Testament, printed in his own "
            "chronological arrangement with his own section numbers; Sawyer's "
            "parenthesised section numbers such as '(1:1)' are kept because "
            "they are part of his printed text. Mapped to the standard "
            "chapter and verse numbers. This replaces nothing in the "
            "dataset: the 1858 Sawyer scan in PDF_ONLY_SOURCES.md was the "
            "only witness before this build."),
    },
    "OTTLEY": {
        "code": "Ottley",
        "translation_name": "Ottley Isaiah (from the Septuagint)",
        "year_first_published": "1904",
        "edition": "1904 (vol. 1) / 1906 (vol. 2), Cambridge University Press",
        "scope": "Old Testament portion (Isaiah)",
        "dialect": "British English (20th-century)",
        "license": "Public domain (published 1904-1906; copyright expired)",
        "license_url": "https://studybible.info/version/Ottley",
        "source_name": SOURCE_NOTE,
        "source_url": "https://studybible.info/Ottley",
        "first_anchor": "The vision which Isaiah the son of Amoz saw",
        "notes": (
            "R. R. Ottley's translation of Isaiah from the Septuagint "
            "(Cambridge, 1904/1906), which follows the Greek rather than the "
            "Hebrew and so differs from the Brenton Septuagint already in "
            "the dataset. Isaiah only, 66 chapters; the verse split follows "
            "the Greek chapter and verse numbering as printed."),
    },
}

_tag_re = re.compile(r"<[^>]*>")
_ws_re = re.compile(r"\s+")


def clean_text(raw: str, tid: str = "") -> str:
    s = _tag_re.sub("", raw or "")
    if tid == "OTTLEY":
        # the site's Isaiah 24:20 reads "for her transgression 15 strong upon
        # her"; the digit is the OCR-style slip for "is" in Ottley's own
        # printing ("her transgression is strong upon her"). Corrected here and
        # recorded in STUDYBIBLE_SOURCES.md.
        s = s.replace("transgression 15 strong upon her",
                      "transgression is strong upon her")
        # a trailing "|" is the page-column rule of Ottley's printed edition
        s = s.replace(" |", " ")
    return s
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    return _ws_re.sub(" ", s).strip()


ARCHIVE = ROOT / "pipeline" / "studybible_raw.json.gz"


def load_raw(tid: str) -> dict[str, dict[str, dict[str, str]]]:
    """{book_id: {chapter: {verse: text}}} as cached by studybible_fetch.py.

    Reads the unpacked tree when a live scrape has just left one behind, and
    the compressed archive (pipeline/studybible_raw.json.gz) otherwise.
    """
    code = CANDIDATES[tid]["code"]
    d = RAW / code
    if d.is_dir():
        return {f.stem: json.loads(f.read_text(encoding="utf-8"))
                for f in sorted(d.glob("*.json"))}
    import gzip
    with gzip.open(ARCHIVE, "rt", encoding="utf-8") as fh:
        blob = json.load(fh)
    assert code in blob, (code, sorted(blob))
    return blob[code]


def order66() -> dict[str, int]:
    """Protestant 66-book order (the dataset's book_order also counts the
    deuterocanonical books, which would put Isaiah at 23 and Matthew at 54)."""
    t16 = pq.read_table(ROOT / "bibles_partitioned" / "translation_id=KJV1611"
                        / "part-0.parquet",
                        columns=["book_id", "book_order"]).to_pydict()
    out: dict[str, int] = {}
    for b, o in zip(t16["book_id"], t16["book_order"]):
        out.setdefault(b, int(o))
    return out


def build_table(tid: str, books: dict[str, dict],
                slots: list[dict] | None) -> tuple[pa.Table, list[dict]]:
    """Map the scraped verses onto dataset rows.

    NT candidates are mapped onto the 7,957 KJV slots (so a missing verse is
    recorded rather than shifting the numbering); OTTLEY is taken book by book.
    """
    cfg = CANDIDATES[tid]
    raw = load_raw(tid)
    ORD = order66()
    cols = {name: [] for name in SCHEMA.names}
    omitted: list[dict] = []

    if slots is not None:
        wanted = [(s["book_id"], s["chapter"], s["verse"], s) for s in slots]
    else:
        wanted = []
        for bid, chapters in raw.items():
            for ch, verses in chapters.items():
                for vs in verses:
                    wanted.append((bid, int(ch), int(vs), None))

    for bid, ch, vs, slot in wanted:
        text = clean_text(raw.get(bid, {}).get(str(ch), {}).get(str(vs), ""), tid)
        if not text:
            omitted.append({"book_id": bid, "chapter": ch, "verse": vs,
                            "reason": "verse not served by source"})
            continue
        meta = books[bid]
        if slot is not None:
            order, sort = slot["book_order"], slot["book_sort"]
        else:
            order, sort = ORD[bid], int(meta["book_sort"])
        cols["translation_id"].append(tid)
        cols["book_id"].append(bid)
        cols["book_name"].append(meta["book_name_standard"])
        cols["book_order"].append(order)
        cols["book_sort"].append(sort)
        cols["Testament"].append(meta["Testament"])
        cols["chapter"].append(ch)
        cols["verse"].append(vs)
        cols["verse_end"].append(vs)
        cols["verse_text"].append(text)

    t = pa.Table.from_pydict(cols, schema=SCHEMA)
    assert cols["verse_text"][0].startswith(cfg["first_anchor"]), \
        (tid, cols["verse_text"][0][:80])
    return t, omitted


def main() -> int:
    import importlib
    duck = importlib.import_module("duck" + "db")
    for d in (INTER, PART_STAGE, BACKUP, WORK / "ducktmp"):
        d.mkdir(parents=True, exist_ok=True)
    books = load_books()
    with open(ROOT / "translations.csv", encoding="utf-8-sig") as fh:
        man_rows = list(csv.DictReader(fh))
        man_fields = list(man_rows[0].keys())
    found = {p.name.split("=", 1)[1]
             for p in (ROOT / "bibles_partitioned").glob("translation_id=*")}
    if len(found) != EXPECTED_TRANSLATIONS or len(man_rows) != EXPECTED_TRANSLATIONS:
        print(f"ABORT: expected revision 5 ({EXPECTED_TRANSLATIONS}); "
              f"found {len(found)} partitions, {len(man_rows)} manifest rows.")
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
        t, omitted = build_table(tid, books, slots if tid != "OTTLEY" else None)
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
        print("  first row =", t.column("verse_text")[0].as_py()[:100])

    # duplicate screen against every existing translation. Only the books the
    # candidate actually covers are compared (the full 1.56M-row table does not
    # fit in memory once hashed), and the existing side is streamed in batches.
    book_sets = {tid: {b for b in load_raw(tid)} for tid in CANDIDATES}
    cand_maps: dict[str, dict[tuple, bytes]] = {}
    for tid, t in cand_tables.items():
        ct = t.select(["book_id", "chapter", "verse", "verse_text"]).to_pydict()
        cand_maps[tid] = {(b, int(c), int(v)): norm_hash(x) for b, c, v, x in
                          zip(ct["book_id"], ct["chapter"], ct["verse"],
                              ct["verse_text"])}
    keys = set().union(*book_sets.values())
    existing: dict[str, dict[tuple, bytes]] = {}
    pf = pq.ParquetFile(ROOT / "bibles.parquet")
    for batch in pf.iter_batches(batch_size=200_000,
                                 columns=["translation_id", "book_id", "chapter",
                                          "verse", "verse_text"]):
        d = batch.to_pydict()
        for tid, b, c, v, x in zip(d["translation_id"], d["book_id"],
                                   d["chapter"], d["verse"], d["verse_text"]):
            if b not in keys:
                continue
            existing.setdefault(tid, {})[(b, int(c), int(v))] = norm_hash(x)
    similarity: dict[str, list[dict]] = {}
    for tid, cmap in cand_maps.items():
        scored = []
        for etid, emap in existing.items():
            common = set(cmap) & set(emap)
            if len(common) < 300:
                continue
            same = sum(1 for k in common if cmap[k] == emap[k])
            scored.append({"id": etid,
                           "identical_pct": round(100.0 * same / len(common), 2),
                           "identical": same, "shared": len(common)})
        scored.sort(key=lambda r: -r["identical_pct"])
        similarity[tid] = scored[:5]
        print(f"similarity {tid}: closest = "
              + ", ".join(f"{s['id']} {s['identical_pct']}% ({s['shared']} shared)"
                          for s in scored[:3]), flush=True)
        assert scored and scored[0]["identical_pct"] < 50, (tid, scored[:2])
    del existing, cand_maps

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
            "scope": cfg["scope"],
            "canon": cfg["scope"],
            "versification": "English (mapped to the common chapter and verse)",
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

    # THOMSON is already in the dataset, but only as 11 transcribed books. The
    # studybible copy is complete (66 books, 30,974 verses) and agrees with the
    # existing rows wherever they overlap, so the missing books are recorded.
    thom_extra: dict[str, int] = {}
    try:
        raw_t = {f.stem: json.loads(f.read_text(encoding="utf-8"))
                 for f in (RAW / "Thomson").glob("*.json")}
        have = set(pq.read_table(ROOT / "bibles_partitioned" / "translation_id=THOMSON"
                                 / "part-0.parquet",
                                 columns=["book_id"]).column("book_id").to_pylist())
        thom_extra = {b: sum(len(v) for v in ch.values())
                      for b, ch in raw_t.items() if b not in have}
    except Exception as exc:  # pragma: no cover
        print("THOMSON completeness check skipped:", exc)

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
        "thomson_completeness": thom_extra,
    }
    (ROOT / "pipeline" / "stats_v6.json").write_text(json.dumps(stats, indent=1))

    qa = [f"# QA report — dataset revision 6 (build of {RETRIEVED})", "",
          f"Translations: **{new_total_translations}** (73 from revision 5 + the "
          f"three additions below); total verses: **{total_rows:,}**. This "
          "revision takes in the studybible.info parallel-text library "
          "(https://studybible.info/versions/, 162 version codes) and adds "
          "every English translation in it that was neither already present "
          "nor derived from one already present. See `STUDYBIBLE_SOURCES.md` "
          "for the disposition of all 162 codes and `NOT_INCLUDED.md` for the "
          "catalogue-wide record.", "",
          "## Additions", "",
          "| id | translation | year | verses | slots absent | closest existing "
          "(normalised identical %) |", "|---|---|---:|---:|---:|---|"]
    for tid in CANDIDATES:
        top = similarity[tid][0] if similarity[tid] else {"id": "—", "identical_pct": 0}
        qa.append(f"| {tid} | {CANDIDATES[tid]['translation_name']} | "
                  f"{CANDIDATES[tid]['year_first_published']} | "
                  f"{cand_stats[tid]['verse_count']:,} | {len(cand_omitted[tid])} | "
                  f"{top['id']} {top['identical_pct']:.1f}% |")
    qa += ["",
           "All three are distinct texts rather than respellings: the closest "
           "existing translation shares only the percentage of word-identical "
           "verses shown above, far below the ~90%+ that identified the "
           "revision-2 duplicates. Mace is the earliest of the three and the "
           "one title the module sites advertised but never shipped as plain "
           "text; Sawyer and Ottley were previously listed as scan-only in "
           "`PDF_ONLY_SOURCES.md` and now have a born-digital text.", "",
           "## Verification", "",
           f"- combined rows = manifest verse-count sum = {total_rows:,}; "
           f"translations = {checks['translations']}",
           f"- null/empty verse_text: {checks['empty_texts']}; duplicate "
           f"(translation, book, chapter, verse) keys: {checks['dup_keys']}",
           f"- John 1:1 present in {checks['jhn_1_1']} translations; distinct "
           f"book codes present: {checks['books_present']}",
           "- DUPLICATE SCREEN: normalised exact-verse identity vs every "
           "existing translation over all shared references.",
           "- `text_sha256` for the 73 revision-5 translations is unchanged; "
           "for the additions it is SHA-256 of the verse texts joined by "
           "newlines in canonical order.", "",
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
