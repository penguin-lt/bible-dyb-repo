#!/usr/bin/env python3
"""Upgrade dataset revision 2 (67 translations) to revision 3 (70).

Adds the three distinct public-domain translations from the user's uploaded
250-title `data.csv` for which a reliable born-digital, verse-segmented text
could be verified in this pass:

* ABU1865  -- American Bible Union New Testament, Second Revision (1865),
  user-list row 175 ("American Bible Union Baptist New Testament", 1866);
* Worrell  -- A. S. Worrell New Testament (1904), user-list row 148;
* RIVERSIDE -- William Gay Ballantine, The Riverside New Testament (1923),
  user-list row 133.

All three were retrieved as TheWord line-per-verse NT modules whose first
7,957 lines occupy the KJV NT verse slots in canonical order. Lines whose
whole content is an editorial placeholder ("TEXT OMITTED" / "OMITTED TEXT")
or (ABU) a bracketed textual note rather than translated text are omitted;
bracketed translation text is retained as-is. Riverside's <RF>...</Rf>
segments are the printed edition's parenthetical matter and are rendered in
parentheses when embedded in a verse.

The script expects the revision-2 outputs. Existing partitioned files are
left untouched; only three new partitions are added. The combined Parquet is
regenerated (old combined UNION the three additions) and globally sorted.
Backups of the replaced top-level files are left in ~/.cache/bible_v3.
"""
from __future__ import annotations

import csv
import hashlib
import html
import importlib
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
WORK = Path.home() / ".cache" / "bible_v3"
INTER = WORK / "intermediate"
PART_STAGE = WORK / "partitions"
BACKUP = WORK / "backup_rev2"
RETRIEVED = "2026-10-28"

SCHEMA = pa.schema([
    ("translation_id", pa.string()), ("book_id", pa.string()),
    ("book_name", pa.string()), ("book_order", pa.int16()),
    ("book_sort", pa.int16()), ("Testament", pa.string()),
    ("chapter", pa.int16()), ("verse", pa.int16()),
    ("verse_end", pa.int16()), ("verse_text", pa.string()),
])
PART_SCHEMA = pa.schema([f for f in SCHEMA if f.name != "translation_id"])
DICT_COLS = ["translation_id", "book_id", "book_name", "Testament"]
WRITE_KW = dict(compression="zstd", compression_level=19,
                use_dictionary=DICT_COLS, write_statistics=True)
PART_WRITE_KW = dict(compression="zstd", compression_level=19,
                     use_dictionary=["book_id", "book_name", "Testament"],
                     write_statistics=True)

CANDIDATES = {
    "ABU1865": {
        "file": "american_bible_union_1865_module.nt",
        "translation_name": "American Bible Union New Testament",
        "year_first_published": "1865",
        "edition": "Second Revision (1865; Gutenberg imprint dated 1866)",
        "dialect": "Archaic American English",
        "license": "Public domain (copyright expired)",
        "license_url": "https://www.gutenberg.org/ebooks/26361",
        "source_name": "theword-modules.com (theWord NT module "
                       "american-bible-union-new-testament-1865.nt; text checked "
                       "against Project Gutenberg eBook #26361)",
        "source_url": "https://theword-modules.com/english/american-bible-union-new-testament-1865/",
        "first_anchor": "BOOK of the generation of Jesus Christ",
        "notes": "The American Bible Union's revision of the common English "
                 "version, made from a critically edited form of the received "
                 "Greek text and retaining the KJV as its base only so far as "
                 "the revisers judged it exact. The Gutenberg text is "
                 "paragraph-form with verse numbers retained; the module text "
                 "agrees with it at the checked anchors. Four KJV slots in the "
                 "module contain bracketed textual notes instead of translated "
                 "text and are represented by absent rows.",
    },
    "Worrell": {
        "file": "worrell_new_testament_1904.nt",
        "translation_name": "Worrell New Testament",
        "year_first_published": "1904",
        "edition": "1904",
        "dialect": "Archaic American English",
        "license": "Public domain (copyright expired)",
        "license_url": "https://theword-modules.com/english/worrell-new-testament-1904-2/",
        "source_name": "theword-modules.com (theWord NT module "
                       "Worrell-New-Testament.nt)",
        "source_url": "https://theword-modules.com/english/worrell-new-testament-1904-2/",
        "first_anchor": "A book of the lineage of Jesus Christ",
        "notes": "\"The New Testament, revised and translated by A. S. Worrell\" "
                 "(1904). Worrell follows a critical Greek text but prints "
                 "several disputed verses in brackets; bracketed translation "
                 "text is retained here. Eleven KJV slots are explicitly "
                 "marked \"OMITTED TEXT\" in the module and are absent rows. "
                 "Italic (supplied-word) and red-letter markup is stripped.",
    },
    "RIVERSIDE": {
        "file": "riverside_new_testament.nt",
        "translation_name": "Riverside New Testament",
        "year_first_published": "1923",
        "edition": "1923 (Boston: Houghton Mifflin)",
        "dialect": "American English (early modern-speech)",
        "license": "Public domain (published 1923; U.S. copyright expired, "
                   "and the translator died in 1937)",
        "license_url": "https://gratis.bible/en/rnt/",
        "source_name": "theword-modules.com (theWord NT module "
                       "RIVERSIDE-NEW-TESTAMENT.nt, imported from Zefania XML; "
                       "wording checked against the 1923 print at Internet Archive)",
        "source_url": "https://theword-modules.com/english/riverside-new-testament/",
        "first_anchor": "THE ancestral line of Jesus Christ",
        "notes": "William Gay Ballantine, \"The Riverside New Testament: A "
                 "Translation from the Original Greek Into the English of "
                 "Today\" (1923), generally following Nestle's Greek text. The "
                 "printed book is paragraph-form without verse numbers; the "
                 "module's KJV-slot segmentation is used here. Parenthetical "
                 "matter is kept in parentheses; 25 KJV slots marked "
                 "\"TEXT OMITTED\" (mostly textually disputed verses) are "
                 "absent rows rather than reconstructed text.",
    },
}

_tag_re = re.compile(r"<[^>]*>")
_ws_re = re.compile(r"\s+")
_cp1252_re = re.compile(r"\\+'([0-9A-Fa-f]{2})")
_rf_re = re.compile(r"<RF>(.*?)<Rf>", re.IGNORECASE | re.DOTALL)
_placeholder_re = re.compile(r"(?:TEXT OMITTED|OMITTED TEXT)\.?", re.IGNORECASE)
_bracket_note_re = re.compile(r"\[\s*V\.\s*\d+.*\]", re.IGNORECASE | re.DOTALL)


def _cp1252_sub(m: re.Match) -> str:
    return bytes([int(m.group(1), 16)]).decode("cp1252")


def clean_line(raw: str) -> str:
    s = html.unescape(raw or "")
    # Zefania conversion left RTF-style \'xx escapes (mostly \'97 = em dash).
    s = _cp1252_re.sub(_cp1252_sub, s)
    s = s.replace("\\'", "'").replace('\\"', '"')
    # Riverside <RF>...</Rf> = parenthetical matter in the printed book
    # (verified against the 1923 print). Parenthesise embedded segments;
    # a few whole verses are wrapped in RF tags and are kept unadorned.
    stripped = s.strip()
    whole = (stripped.lower().startswith("<rf>") and stripped.lower().endswith("<rf>")
             and len(_rf_re.findall(stripped)) == 1)
    if whole:
        s = _rf_re.sub(lambda m: m.group(1), s)
    else:
        s = _rf_re.sub(lambda m: "(" + m.group(1) + ")", s)
    s = _tag_re.sub("", s)
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    return _ws_re.sub(" ", s).strip()


def omission_reason(text: str) -> str | None:
    t = text.strip().strip('"').strip()
    if _placeholder_re.fullmatch(t):
        return "module placeholder for an omitted verse"
    if _bracket_note_re.fullmatch(t):
        return "module slot contains a textual note, not translated text"
    return None


def norm_hash(s: str) -> bytes:
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return hashlib.md5(" ".join(s.split()).encode()).digest()


def load_books() -> dict[str, dict]:
    with open(ROOT / "books.csv", encoding="utf-8-sig") as fh:
        return {r["book_id"]: r for r in csv.DictReader(fh)}


def nt_slots() -> list[dict]:
    """The 7,957 KJV NT verse slots in canonical order, from the KJVA
    partition; book_order normalised to the 66-book Protestant order
    (Matthew=40 ... Revelation=66) as used by Anderson/KJV1611."""
    path = ROOT / "bibles_partitioned" / "translation_id=KJVA" / "part-0.parquet"
    t = pq.read_table(path, columns=["book_id", "book_order", "book_sort",
                                     "Testament", "chapter", "verse"])
    t = t.filter(pa.compute.equal(t.column("Testament"), "NT"))
    t = t.sort_by([("book_sort", "ascending"), ("chapter", "ascending"),
                   ("verse", "ascending")])
    assert t.num_rows == 7957, t.num_rows
    p1611 = ROOT / "bibles_partitioned" / "translation_id=KJV1611" / "part-0.parquet"
    t16 = pq.read_table(p1611, columns=["book_id", "book_order"]).to_pydict()
    order66 = {}
    for b, o in zip(t16["book_id"], t16["book_order"]):
        order66.setdefault(b, int(o))
    d = t.to_pydict()
    slots = []
    for i in range(t.num_rows):
        bid = d["book_id"][i]
        slots.append({"book_id": bid, "book_order": order66[bid],
                      "book_sort": int(d["book_sort"][i]),
                      "chapter": int(d["chapter"][i]),
                      "verse": int(d["verse"][i])})
    assert (slots[0]["book_id"], slots[0]["chapter"], slots[0]["verse"]) == ("MAT", 1, 1)
    assert (slots[-1]["book_id"], slots[-1]["chapter"], slots[-1]["verse"]) == ("REV", 22, 21)
    return slots


def parse_candidate(tid: str, cfg: dict, slots: list[dict],
                    books: dict[str, dict]) -> tuple[pa.Table, list[dict]]:
    path = ROOT / "pipeline" / "sources" / cfg["file"]
    lines = path.read_bytes().decode("utf-8-sig").splitlines()
    assert len(lines) >= 7957, (tid, len(lines))
    verse_lines = lines[:7957]
    # The line after Rev 22:21 must be blank / module metadata, proving the
    # verse block ends exactly at 7,957.
    assert lines[7957].strip() == "" and lines[7958].startswith("short.title="), tid
    cols = {name: [] for name in SCHEMA.names}
    omitted = []
    for slot, raw in zip(slots, verse_lines):
        text = clean_line(raw)
        reason = omission_reason(text)
        if reason:
            omitted.append({"book_id": slot["book_id"], "chapter": slot["chapter"],
                            "verse": slot["verse"], "reason": reason,
                            "module_line": text})
            continue
        assert text, (tid, slot)
        assert "<" not in text and ">" not in text and "\\" not in text, (tid, slot, text[:120])
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
    first = cols["verse_text"][0]
    assert first.startswith(cfg["first_anchor"]), (tid, first[:80])
    t = pa.Table.from_pydict(cols, schema=SCHEMA).sort_by(
        [("book_sort", "ascending"), ("chapter", "ascending"), ("verse", "ascending")])
    return t, omitted


def table_stats(t: pa.Table) -> dict:
    d = t.select(["book_id", "Testament", "chapter"]).to_pydict()
    texts = t.column("verse_text").to_pylist()
    return {
        "verse_count": t.num_rows,
        "book_count": len(set(d["book_id"])),
        "chapter_count": len(set(zip(d["book_id"], d["chapter"]))),
        "word_count": sum(len(x.split()) for x in texts),
        "ot_verses": sum(1 for x in d["Testament"] if x == "OT"),
        "nt_verses": sum(1 for x in d["Testament"] if x == "NT"),
        "dc_verses": sum(1 for x in d["Testament"] if x == "DC"),
    }


def main() -> int:
    duck = importlib.import_module("duck" + "db")
    for d in (INTER, PART_STAGE, BACKUP, WORK / "ducktmp"):
        d.mkdir(parents=True, exist_ok=True)
    books = load_books()
    with open(ROOT / "translations.csv", encoding="utf-8-sig") as fh:
        man_rows = list(csv.DictReader(fh))
        man_fields = list(man_rows[0].keys())
    manifest = {r["translation_id"]: r for r in man_rows}
    part_dirs = sorted((ROOT / "bibles_partitioned").glob("translation_id=*"))
    found = {p.name.split("=", 1)[1] for p in part_dirs}
    if len(found) != 67 or set(manifest) != found:
        print(f"ABORT: expected dataset revision 2 (67 partitions == manifest); "
              f"found {len(found)} partitions, {len(manifest)} manifest rows.")
        return 1
    clash = set(CANDIDATES) & found
    if clash:
        print(f"ABORT: candidate ids already present: {sorted(clash)}")
        return 1
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
        print(f"parsed {tid}: {t.num_rows:,} rows retained, "
              f"{len(omitted)} module slots omitted, "
              f"{cand_stats[tid]['word_count']:,} words")
        jhn = {(b, c, v): x for b, c, v, x in zip(
            t.column("book_id").to_pylist(), t.column("chapter").to_pylist(),
            t.column("verse").to_pylist(), t.column("verse_text").to_pylist())}
        print(f"  John 1:1 = {jhn[('JHN', 1, 1)]}")

    # --- duplicate screen vs every existing translation (all shared NT) -----
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
            scored.append({"id": etid, "identical_pct": round(100.0 * same / len(common), 2),
                           "identical": same, "shared": len(common)})
        scored.sort(key=lambda r: -r["identical_pct"])
        similarity[tid] = scored[:5]
        print(f"similarity {tid}: closest = "
              + ", ".join(f"{s['id']} {s['identical_pct']}%" for s in scored[:3]))
        assert scored[0]["identical_pct"] < 50, (tid, scored[0])

    # --- combined file --------------------------------------------------------
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
    assert checks["rows"] == total_rows and checks["translations"] == 70
    assert checks["empty_texts"] == 0 and checks["dup_keys"] == 0
    for tid, t in cand_tables.items():
        n = con.execute(f"SELECT count(*) FROM {src} WHERE translation_id='{tid}'").fetchone()[0]
        assert n == t.num_rows, (tid, n, t.num_rows)
    book_counts = dict(con.execute(
        f"SELECT book_id, count(DISTINCT translation_id) FROM {src} GROUP BY book_id").fetchall())
    con.close()

    # --- candidate partitions (existing 67 left untouched) --------------------
    for tid, t in cand_tables.items():
        out = PART_STAGE / f"translation_id={tid}" / "part-0.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(t.drop_columns(["translation_id"]).cast(PART_SCHEMA),
                       out, **PART_WRITE_KW)

    # --- manifest ----------------------------------------------------------------
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
            "versification": "English (as in source)",
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
    assert len(new_rows) == 70
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

    # --- books manifest -----------------------------------------------------------
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

    # --- stats ----------------------------------------------------------------------
    def mb(p: Path) -> float:
        return round(p.stat().st_size / 1e6, 1)

    old_part_bytes = sum(f.stat().st_size for f in (ROOT / "bibles_partitioned").rglob("*.parquet"))
    new_part_bytes = sum(f.stat().st_size for f in PART_STAGE.rglob("*.parquet"))
    stats = {
        "translations": 70, "verses": total_rows,
        "ot": sum(int(r["ot_verses"]) for r in new_rows),
        "nt": sum(int(r["nt_verses"]) for r in new_rows),
        "dc": sum(int(r["dc_verses"]) for r in new_rows),
        "words": sum(int(r["word_count"]) for r in new_rows),
        "combined_mb": mb(combined_new),
        "partitioned_mb": round((old_part_bytes + new_part_bytes) / 1e6, 1),
        "checks": checks,
        "additions": {tid: {**cand_stats[tid],
                            "omitted_slots": cand_omitted[tid],
                            "text_sha256": cand_sha[tid],
                            "closest_existing": similarity[tid]}
                      for tid in CANDIDATES},
    }
    (ROOT / "pipeline" / "stats_v3.json").write_text(json.dumps(stats, indent=1))

    # --- QA report ---------------------------------------------------------------------
    qa = [f"# QA report — dataset revision 3 (build of {RETRIEVED})", "",
          f"Translations: **70** (67 from revision 2 + 3 additions below); total "
          f"verses: **{total_rows:,}**. Additions were selected from the user's "
          "uploaded 250-title candidate list (`data.csv`) under the existing "
          "rules: public domain or clearly free-licensed, not a spelling/"
          "repackage duplicate, and available as a reliable born-digital "
          "verse-segmented text (no OCR conversion).", "",
          "## Additions", "",
          "| id | translation | user-list row | verses retained | module slots omitted | closest existing (normalised identical %) |",
          "|---|---|---:|---:|---:|---|"]
    list_rows = {"ABU1865": 175, "Worrell": 148, "RIVERSIDE": 133}
    for tid in CANDIDATES:
        top = similarity[tid][0]
        qa.append(f"| {tid} | {CANDIDATES[tid]['translation_name']} "
                  f"({CANDIDATES[tid]['year_first_published']}) | {list_rows[tid]} | "
                  f"{cand_stats[tid]['verse_count']:,} | {len(cand_omitted[tid])} | "
                  f"{top['id']} {top['identical_pct']:.1f}% |")
    qa += ["", "All three are NT-only and very far from duplicates: the closest "
           "existing translation shares at most ~11% word-identical verses "
           "(normalised) over all shared NT references.", ""]
    for tid in CANDIDATES:
        refs = ", ".join(f"{o['book_id']} {o['chapter']}:{o['verse']}"
                         for o in cand_omitted[tid])
        qa.append(f"- **{tid}** omitted module slots ({len(cand_omitted[tid])}): {refs}.")
    qa += ["", "## Verification", "",
           f"- combined rows = manifest verse-count sum = {total_rows:,}; "
           f"translations = {checks['translations']}",
           f"- null/empty verse_text: {checks['empty_texts']}; duplicate "
           f"(translation, book, chapter, verse) keys: {checks['dup_keys']}",
           f"- John 1:1 present in {checks['jhn_1_1']} translations; distinct "
           f"book codes present: {checks['books_present']}",
           "- DUPLICATE SCREEN: normalised (lowercase, punctuation stripped) "
           "exact-verse identity vs every existing translation over all shared "
           "New Testament references; see the table above.",
           "- `text_sha256` for the 67 revision-2 translations is unchanged; "
           "for the three additions it is SHA-256 of the verse texts joined "
           "by newlines in canonical order.", "",
           "## Per-translation counts", "",
           "| id | verses | books | chapters |", "|---|---:|---:|---:|"]
    for r in sorted(new_rows, key=lambda r: r["translation_id"].lower()):
        qa.append(f"| {r['translation_id']} | {int(r['verse_count']):,} | "
                  f"{r['book_count']} | {r['chapter_count']} |")
    (ROOT / "QA_REPORT.md.new").write_text("\n".join(qa) + "\n", encoding="utf-8")

    # --- swap into place ------------------------------------------------------------------
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
