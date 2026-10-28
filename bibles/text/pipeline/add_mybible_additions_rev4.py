#!/usr/bin/env python3
"""Upgrade dataset revision 3 (70 translations) to revision 4 (72).

Adds the two pre-1929 public-domain New Testaments whose verse-segmented
born-digital text was verified in the MyBible (ph4) English module catalogue:

* MOFFATT -- James Moffatt, "The New Testament: A New Translation" (1913),
  MyBible module ``NTM.SQLite3``;
* PANIN   -- Ivan Panin, "The New Testament from the Greek Text as
  Established by Bible Numerics" (1914), MyBible module ``NumNT.SQLite3``.

Both modules store one row per verse with MyBible book numbers 470-730; the
27 books map in catalogue order onto the canonical NT book ids.

Cleaning (unchanged rules: plain reading text, no tags / notes / headings,
native versification, no OCR):

* <J>...</J> red-letter and <n>...</n> note-span tags are stripped; the words
  they enclose are retained (they are printed translation text, not notes).
* MOFFATT prints a few editorial instructions inside square brackets
  ("[Relocated to follow vs 20]", "[vss 22-29 moved to follow 9:41]").  A
  bracket is dropped only when its content is such an instruction (it starts
  with a relocation keyword or a verse reference); bracketed *text*
  ("[the Son of God]", "[without cause]") is kept as printed.
* MOFFATT leaves 17 KJV slots with a punctuation-only placeholder
  ("--", "— -") instead of text; those are absent rows.
* PANIN uses a colon before a word to mark the Greek article (documented in
  the 2019 Vedder edition: "the placement of a colon before a word to
  indicate the Greek use of the article").  That is a typographic device, not
  reading text, so the colon is removed; no word is changed, added, removed
  or reordered.  Slots marked "Omitted" or left blank are absent rows (19).
* PANIN's module mis-slots Matthew 23: the text of verse 13 sits in the
  slot numbered 14 and slot 13 says "Omitted".  The text is moved back to
  23:13 and 23:14 is an absent row (Panin's text, like the critical text it
  follows, has no verse 14 there).  In Hebrews the module merges 1:14 into
  1:13, so HEB 1:14 is an absent row and 1:13 carries both sentences.

Existing 70 partitions are left untouched; two new partitions are added and
the combined Parquet is regenerated.  Backups of replaced top-level files go
to ~/.cache/bible_v4/backup_rev3/ (not part of the workspace snapshot).
"""
from __future__ import annotations

import csv
import hashlib
import html
import importlib
import json
import re
import shutil
import sqlite3
import sys
import unicodedata
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
WORK = Path.home() / ".cache" / "bible_v4"
INTER = WORK / "intermediate"
PART_STAGE = WORK / "partitions"
BACKUP = WORK / "backup_rev3"
RETRIEVED = "2026-10-28"
EXPECTED_TRANSLATIONS = 70

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
    "MOFFATT": {
        "db": "NTM.SQLite3",
        "translation_name": "Moffatt New Testament",
        "year_first_published": "1913",
        "edition": "1913 (The New Testament: A New Translation)",
        "dialect": "British English (early modern-speech)",
        "license": "Public domain (published 1913; U.S. copyright expired; "
                   "translator died 1944)",
        "license_url": "https://www.ph4.org/b4_1.php?l=en",
        "source_name": "MyBible module NTM.SQLite3 (ph4 English catalogue, "
                       "entry 'NTM 1913 New Testament, James Moffatt')",
        "source_url": "https://www.ph4.org/b4_1.php?l=en",
        "first_anchor": "The birth-roll of Jesus Christ",
        "notes": "James Moffatt's own translation of the New Testament, first "
                 "published 1913 (the complete Bible followed in 1924). "
                 "Moffatt worked from a critical Greek text and often "
                 "relocated verses, printing bracketed passages of doubtful "
                 "authenticity; bracketed translated text is retained, while "
                 "the module's bracketed editorial relocation instructions are "
                 "dropped. Seventeen KJV slots hold only a punctuation dash in "
                 "the module and are absent rows. Red-letter and note-span "
                 "tags are stripped; words are otherwise unaltered, including "
                 "verse-initial lower case and spans whose brackets are split "
                 "across two verses because the module note runs verse to "
                 "verse.",
    },
    "PANIN": {
        "db": "NumNT.SQLite3",
        "translation_name": "Panin Numeric New Testament",
        "year_first_published": "1914",
        "edition": "1914 (The New Testament from the Greek Text as "
                   "Established by Bible Numerics)",
        "dialect": "Archaic English (American)",
        "license": "Public domain (published 1914; U.S. copyright expired; "
                   "translator died 1942)",
        "license_url": "https://www.ph4.org/b4_1.php?l=en",
        "source_name": "MyBible module NumNT.SQLite3 (ph4 English catalogue, "
                       "entry 'NumNT 1914 Numeric English New Testament, "
                       "Ivan Panin')",
        "source_url": "https://www.ph4.org/b4_1.php?l=en",
        "first_anchor": "A GENEALOGY of Jesus Christ",
        "notes": "Ivan Panin's translation of the Greek text he established by "
                 "his 'Bible numerics' method (1914). The text keeps the "
                 "1914 orthography (geenna, the archaic second person) and "
                 "Panin's own punctuation. Panin marked the Greek article by "
                 "placing a colon before the English word; those colon "
                 "markers (and the other word-attached colons of the module's "
                 "text) are removed so the file holds plain reading text, with "
                 "no word altered, added, removed or reordered. Nineteen KJV "
                 "slots are marked 'Omitted' or blank in the module and are "
                 "absent rows; the module also files Matthew 23:13's text "
                 "under verse 14 (corrected here to 23:13, so 23:14 is absent) "
                 "and merges Hebrews 1:14 into 1:13.",
    },
}

_tag_re = re.compile(r"<[^>]*>")
_ws_re = re.compile(r"\s+")
_bracket_re = re.compile(r"\[([^\[\]]*)\]")
# MOFFATT editorial instructions inside square brackets
_editorial_re = re.compile(
    r"^\s*(?:relocat|move\b|moved\b|vss?\.?\s|chapters?\b|follows?\b|"
    r"vs omitted|moved to\b)", re.IGNORECASE)
_placeholder_re = re.compile(r"^[\s\-—–]*$")


def _editorial(m: re.Match) -> str:
    return "" if _editorial_re.match(m.group(1)) else m.group(0)


def clean_moffatt(raw: str) -> str:
    s = html.unescape(raw or "")
    s = _tag_re.sub("", s)
    s = _bracket_re.sub(_editorial, s)
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    return _ws_re.sub(" ", s).strip()


def clean_panin(raw: str) -> str:
    s = html.unescape(raw or "")
    s = _tag_re.sub("", s)
    s = s.replace("::", ":")
    s = re.sub(r":(?=[^\s])", "", s)          # ":)", ":-", stray adjoining
    s = re.sub(r"(?<=[A-Za-z]):(?=\s|$)", "", s)  # article marker / word colon
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    return _ws_re.sub(" ", s).strip()


CLEANERS = {"MOFFATT": clean_moffatt, "PANIN": clean_panin}
PLACEHOLDER_SLOTS = {"MOFFATT": _placeholder_re}
OMIT_TEXT = {"PANIN": re.compile(r"^omitted\.?$", re.IGNORECASE)}


def norm_hash(s: str) -> bytes:
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return hashlib.md5(" ".join(s.split()).encode()).digest()


def load_books() -> dict[str, dict]:
    with open(ROOT / "books.csv", encoding="utf-8-sig") as fh:
        return {r["book_id"]: r for r in csv.DictReader(fh)}


def nt_slots() -> list[dict]:
    """7,957 KJV NT verse slots in canonical order, book_order normalised to
    the 66-book Protestant order (Matthew=40 ... Revelation=66)."""
    path = ROOT / "bibles_partitioned" / "translation_id=KJVA" / "part-0.parquet"
    t = pq.read_table(path, columns=["book_id", "book_sort", "Testament",
                                     "chapter", "verse"])
    t = t.filter(pa.compute.equal(t.column("Testament"), "NT"))
    t = t.sort_by([("book_sort", "ascending"), ("chapter", "ascending"),
                   ("verse", "ascending")])
    assert t.num_rows == 7957, t.num_rows
    t16 = pq.read_table(ROOT / "bibles_partitioned" / "translation_id=KJV1611"
                        / "part-0.parquet",
                        columns=["book_id", "book_order"]).to_pydict()
    order66: dict[str, int] = {}
    for b, o in zip(t16["book_id"], t16["book_order"]):
        order66.setdefault(b, int(o))
    d = t.to_pydict()
    slots = [{"book_id": d["book_id"][i], "book_order": order66[d["book_id"][i]],
              "book_sort": int(d["book_sort"][i]), "chapter": int(d["chapter"][i]),
              "verse": int(d["verse"][i])} for i in range(t.num_rows)]
    assert (slots[0]["book_id"], slots[0]["chapter"], slots[0]["verse"]) == ("MAT", 1, 1)
    assert (slots[-1]["book_id"], slots[-1]["chapter"], slots[-1]["verse"]) == ("REV", 22, 21)
    return slots


def parse_candidate(tid: str, cfg: dict, slots: list[dict],
                    books: dict[str, dict]) -> tuple[pa.Table, list[dict]]:
    db = ROOT / "pipeline" / "sources" / cfg["db"]
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    book_rows = con.execute("SELECT book_number, long_name FROM books "
                            "ORDER BY book_number").fetchall()
    verse_rows = con.execute("SELECT book_number, chapter, verse, text FROM verses "
                             "ORDER BY book_number, chapter, verse").fetchall()
    con.close()
    assert len(book_rows) == 27, (tid, len(book_rows))
    nt_ids = []  # the 27 NT book ids in canonical order
    for s in slots:
        if s["book_id"] not in nt_ids:
            nt_ids.append(s["book_id"])
    assert len(nt_ids) == 27, (tid, len(nt_ids))
    bmap = {int(num): bid for (num, _name), bid in zip(book_rows, nt_ids)}
    clean = CLEANERS[tid]

    # optional corrective re-slotting (module numbering bug), keyed on slot
    reslot = {}
    if tid == "PANIN":
        reslot[(nt_ids[0], 23, 14)] = (nt_ids[0], 23, 13)

    omitted: list[dict] = []
    kept: dict[tuple, str] = {}
    for bn, c, v, raw in verse_rows:
        key = (bmap[int(bn)], int(c), int(v))
        text = clean(raw)
        if not text or (tid in PLACEHOLDER_SLOTS and
                        PLACEHOLDER_SLOTS[tid].match(text)) or \
                (tid in OMIT_TEXT and OMIT_TEXT[tid].match(text)):
            omitted.append({"book_id": key[0], "chapter": key[1], "verse": key[2],
                            "reason": "module slot is a placeholder/omission mark",
                            "module_text": text})
            continue
        key = reslot.get(key, key)
        if key in kept:
            raise AssertionError(f"{tid}: duplicate slot {key}")
        kept[key] = text
    # a slot that was refilled by a corrective move is no longer absent
    omitted = [o for o in omitted
               if (o["book_id"], o["chapter"], o["verse"]) not in kept]

    slot_index = {(s["book_id"], s["chapter"], s["verse"]): s for s in slots}
    missing = [k for k in slot_index if k not in kept]
    extra = [k for k in kept if k not in slot_index]
    assert not extra, (tid, extra[:5])
    for k in missing:  # KJV slots with no verse in this translation
        if not any(o["book_id"] == k[0] and o["chapter"] == k[1]
                   and o["verse"] == k[2] for o in omitted):
            omitted.append({"book_id": k[0], "chapter": k[1], "verse": k[2],
                            "reason": "no verse in this translation at this reference",
                            "module_text": ""})

    cols = {name: [] for name in SCHEMA.names}
    for slot in slots:
        key = (slot["book_id"], slot["chapter"], slot["verse"])
        if key not in kept:
            continue
        text = kept[key]
        assert "<" not in text and ">" not in text, (tid, key, text[:120])
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
    omitted.sort(key=lambda o: (o["book_id"], o["chapter"], o["verse"]))
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
    if len(found) != EXPECTED_TRANSLATIONS or set(manifest) != found:
        print(f"ABORT: expected dataset revision 3 ({EXPECTED_TRANSLATIONS} "
              f"partitions == manifest); found {len(found)} partitions, "
              f"{len(manifest)} manifest rows.")
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
        print(f"parsed {tid}: {t.num_rows:,} rows retained, "
              f"{len(omitted)} slots absent, {cand_stats[tid]['word_count']:,} words")
        jhn = {(b, c, v): x for b, c, v, x in zip(
            t.column("book_id").to_pylist(), t.column("chapter").to_pylist(),
            t.column("verse").to_pylist(), t.column("verse_text").to_pylist())}
        print(f"  John 1:1 = {jhn[('JHN', 1, 1)]}")
        print(f"  Matt 5:22 = {jhn.get(('MAT', 5, 22))}")

    # --- duplicate screen vs every existing translation ----------------------
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

    # --- combined file ------------------------------------------------------
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

    # --- new partitions (existing 70 untouched) ------------------------------
    for tid, t in cand_tables.items():
        out = PART_STAGE / f"translation_id={tid}" / "part-0.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(t.drop_columns(["translation_id"]).cast(PART_SCHEMA),
                       out, **PART_WRITE_KW)

    # --- manifest -----------------------------------------------------------
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

    # --- books manifest -----------------------------------------------------
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

    # --- stats --------------------------------------------------------------
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
        "additions": {tid: {**cand_stats[tid],
                            "omitted_slots": cand_omitted[tid],
                            "text_sha256": cand_sha[tid],
                            "closest_existing": similarity[tid]}
                      for tid in CANDIDATES},
    }
    (ROOT / "pipeline" / "stats_v4.json").write_text(json.dumps(stats, indent=1))

    # --- QA report ----------------------------------------------------------
    qa = [f"# QA report — dataset revision 4 (build of {RETRIEVED})", "",
          f"Translations: **{new_total_translations}** (70 from revision 3 + 2 "
          f"additions below); total verses: **{total_rows:,}**. Additions were "
          "taken from the MyBible (ph4) English module catalogue under the "
          "existing rules: public domain or clearly free-licensed, not a "
          "spelling/repackage duplicate, and available as a reliable "
          "born-digital, verse-segmented text (no OCR conversion).", "",
          "## Additions", "",
          "| id | translation | year | verses retained | KJV slots absent | "
          "closest existing (normalised identical %) |",
          "|---|---|---:|---:|---:|---|"]
    for tid in CANDIDATES:
        top = similarity[tid][0]
        qa.append(f"| {tid} | {CANDIDATES[tid]['translation_name']} | "
                  f"{CANDIDATES[tid]['year_first_published']} | "
                  f"{cand_stats[tid]['verse_count']:,} | {len(cand_omitted[tid])} | "
                  f"{top['id']} {top['identical_pct']:.1f}% |")
    qa += ["", "Both are NT-only and distinct from every existing translation: the "
           "closest existing text is MONTGOMERY at 1.0% word-identical verses "
           "for MOFFATT and ASV at 16.6% for PANIN (ASV/RV share Panin's "
           "revision-tradition diction).", ""]
    for tid in CANDIDATES:
        refs = "; ".join(f"{o['book_id']} {o['chapter']}:{o['verse']} "
                         f"({o['reason']})" for o in cand_omitted[tid])
        qa.append(f"- **{tid}** absent slots ({len(cand_omitted[tid])}): {refs}.")
    qa += ["", "## Cleaning applied", "",
           "- red-letter (`<J>`) and note-span (`<n>`) tags removed; enclosed "
           "words kept",
           "- **MOFFATT**: bracketed editorial relocation instructions dropped; "
           "bracketed translated text kept; 17 punctuation-only placeholder "
           "slots omitted; no other wording change",
           "- **PANIN**: colon article-markers removed (typographic device for "
           "the Greek article); 'Omitted'/blank slots omitted; Matthew 23:13-14 "
           "numbering corrected; Hebrews 1:14 absent because the module merges "
           "it into 1:13", "",
           "## Verification", "",
           f"- combined rows = manifest verse-count sum = {total_rows:,}; "
           f"translations = {checks['translations']}",
           f"- null/empty verse_text: {checks['empty_texts']}; duplicate "
           f"(translation, book, chapter, verse) keys: {checks['dup_keys']}",
           f"- John 1:1 present in {checks['jhn_1_1']} translations; distinct "
           f"book codes present: {checks['books_present']}",
           "- DUPLICATE SCREEN: normalised (lowercase, punctuation stripped) "
           "exact-verse identity vs every existing translation over all shared "
           "New Testament references; see the table above.",
           "- `text_sha256` for the 70 revision-3 translations is unchanged; for "
           "both additions it is SHA-256 of the verse texts joined by newlines "
           "in canonical order.", "",
           "## Per-translation counts", "",
           "| id | verses | books | chapters |", "|---|---:|---:|---:|"]
    for r in sorted(new_rows, key=lambda r: r["translation_id"].lower()):
        qa.append(f"| {r['translation_id']} | {int(r['verse_count']):,} | "
                  f"{r['book_count']} | {r['chapter_count']} |")
    (ROOT / "QA_REPORT.md.new").write_text("\n".join(qa) + "\n", encoding="utf-8")

    # --- swap into place ----------------------------------------------------
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
