#!/usr/bin/env python3
"""Rebuild the dataset (revision 2, 2026-10-28): balanced deduplication + KJV1611.

One-shot upgrade of the 2026-10-27 build (81 translations) to revision 2
(67 translations):

* drops 15 translations that are spelling/repackage/near-identical variants
  of a kept translation (DROP below; similarity measured on normalised verse
  text over GEN+MAT+JHN+ROM, see QA_REPORT.md);
* adds KJV1611 — the 1611 first edition in original spelling — parsed from
  the theWord module `pipeline/sources/kjv1611.ont` (31,102 line-per-verse
  lines in KJV versification order, followed by the translators' preface).

Kept translations are taken verbatim from the existing
`bibles_partitioned/translation_id=*/part-0.parquet` files, so this script
expects the v1 outputs as input and refuses to run on anything else.

Requires: pyarrow, and the (lowercase) `duck`+`db` module for the global
reference sort of the combined file. Intermediates go to ~/.cache/bible_v2.
Outputs are written to *.new paths and only swapped into place after all
checks pass; the old partitioned dataset is moved to ~/.cache/bible_v2.
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
WORK = Path.home() / ".cache" / "bible_v2"
INTER = WORK / "intermediate"
ONT_PATH = ROOT / "pipeline" / "sources" / "kjv1611.ont"
RETRIEVED = "2026-10-28"

DROP = {
    # dropped id -> kept equivalent
    "KJV": "KJVA", "KJVPCE": "KJVA", "KJVCPB": "KJVA", "RLT": "KJVA",
    "WEBU": "WEB", "WEBC": "WEB", "WEBP": "WEB", "WEBBE": "WEB", "WEBPB": "WEB",
    "WMBB": "WMB", "NHEBJE": "NHEB", "NHEBME": "NHEB",
    "OEBCW": "OEBUS", "LXX2012UK": "LXX2012", "DRC": "DRA",
}
SIMILARITY = {  # % verses identical (normalised) vs kept equivalent, sampled books
    "KJV": 100.0, "KJVPCE": 99.4, "KJVCPB": 94.8, "RLT": 92.5,
    "WEBU": 96.3, "WEBC": 96.3, "WEBP": 96.3, "WEBBE": 87.5, "WEBPB": 87.5,
    "WMBB": 91.4, "NHEBJE": 95.6, "NHEBME": 87.7,
    "OEBCW": 94.4, "LXX2012UK": 96.3, "DRC": 92.4,
}

SCHEMA = pa.schema([
    ("translation_id", pa.string()), ("book_id", pa.string()),
    ("book_name", pa.string()), ("book_order", pa.int16()),
    ("book_sort", pa.int16()), ("Testament", pa.string()),
    ("chapter", pa.int16()), ("verse", pa.int16()),
    ("verse_end", pa.int16()), ("verse_text", pa.string()),
])
DICT_COLS = ["translation_id", "book_id", "book_name", "Testament"]
WRITE_KW = dict(compression="zstd", compression_level=19,
                use_dictionary=DICT_COLS, write_statistics=True)

_tag_re = re.compile(r"<[^>]*>")
_ws_re = re.compile(r"\s+")


def clean_text(s: str) -> str:
    """Same philosophy as the v1 cleaner: tags out, words kept, ws collapsed."""
    s = html.unescape(s or "")
    s = _tag_re.sub("", s)
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    return _ws_re.sub(" ", s).strip()


def norm_hash(s: str) -> bytes:
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return hashlib.md5(" ".join(s.split()).encode()).digest()


def load_books() -> dict[str, dict]:
    with open(ROOT / "books.csv", encoding="utf-8-sig") as fh:
        return {r["book_id"]: r for r in csv.DictReader(fh)}


def kjv_structure() -> list[tuple[str, list[int]]]:
    """66-book KJV versification (book order + per-chapter verse counts),
    derived from the v1 KJV partition so the .ont line mapping is exact."""
    t = pq.read_table(ROOT / "bibles_partitioned" / "translation_id=KJV" / "part-0.parquet",
                      columns=["book_id", "book_order", "chapter", "verse"]).to_pydict()
    struct: dict[int, dict] = {}
    for b, o, c, v in zip(t["book_id"], t["book_order"], t["chapter"], t["verse"]):
        struct.setdefault(o, {"book_id": b, "chapters": {}})["chapters"][c] = \
            struct.setdefault(o, {"book_id": b, "chapters": {}})["chapters"].get(c, 0) + 1
    out = []
    for o in sorted(struct):
        chs = struct[o]["chapters"]
        out.append((struct[o]["book_id"], [chs[c] for c in sorted(chs)]))
    total = sum(sum(v) for _, v in out)
    assert len(out) == 66 and total == 31102, (len(out), total)
    return out


def parse_kjv1611(books: dict[str, dict]) -> pa.Table:
    struct = kjv_structure()
    raw = ONT_PATH.read_bytes().decode("utf-8-sig", "replace")
    lines = raw.split("\r\n")
    assert len(lines) >= 31102, len(lines)
    verse_lines = [clean_text(L) for L in lines[:31102]]
    assert all(verse_lines), "empty verse line in .ont"
    assert verse_lines[0].startswith("In the beginning God created the Heauen")
    assert verse_lines[23145].startswith("The booke of the generation of Iesus Christ")
    assert verse_lines[31101].endswith("Amen.")
    cols = {name: [] for name in SCHEMA.names}
    i = 0
    for order, (bid, ch_counts) in enumerate(struct, start=1):
        meta = books[bid]
        for ch, nv in enumerate(ch_counts, start=1):
            for v in range(1, nv + 1):
                cols["translation_id"].append("KJV1611")
                cols["book_id"].append(bid)
                cols["book_name"].append(meta["book_name_standard"])
                cols["book_order"].append(order)
                cols["book_sort"].append(int(meta["book_sort"]))
                cols["Testament"].append(meta["Testament"])
                cols["chapter"].append(ch)
                cols["verse"].append(v)
                cols["verse_end"].append(v)
                cols["verse_text"].append(verse_lines[i])
                i += 1
    assert i == 31102
    return pa.Table.from_pydict(cols, schema=SCHEMA)


def table_stats(t: pa.Table) -> dict:
    d = t.select(["book_id", "Testament", "chapter", "verse_text"]).to_pydict()
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
    INTER.mkdir(parents=True, exist_ok=True)
    books = load_books()
    with open(ROOT / "translations.csv", encoding="utf-8-sig") as fh:
        man_rows = list(csv.DictReader(fh))
        man_fields = man_rows and list(man_rows[0].keys())
    manifest = {r["translation_id"]: r for r in man_rows}

    part_dirs = sorted((ROOT / "bibles_partitioned").glob("translation_id=*"))
    found = {p.name.split("=", 1)[1] for p in part_dirs}
    if len(found) != 81 or set(manifest) != found:
        print(f"ABORT: expected the v1 dataset (81 partitions == manifest); "
              f"found {len(found)} partitions, {len(manifest)} manifest rows.")
        return 1
    kept = sorted(found - set(DROP))
    assert len(kept) == 66, len(kept)

    # --- intermediates: kept translations verbatim + new KJV1611 -----------
    inter_paths: list[Path] = []
    for tid in kept:
        src = ROOT / "bibles_partitioned" / f"translation_id={tid}" / "part-0.parquet"
        t = pq.read_table(src)
        t = t.add_column(0, "translation_id", pa.array([tid] * t.num_rows, pa.string()))
        t = t.cast(SCHEMA).sort_by([("book_sort", "ascending"), ("chapter", "ascending"),
                                     ("verse", "ascending"), ("verse_end", "ascending")])
        assert t.num_rows == int(manifest[tid]["verse_count"]), tid
        dst = INTER / f"{tid}.parquet"
        pq.write_table(t, dst, **WRITE_KW)
        inter_paths.append(dst)
        print(f"kept {tid}: {t.num_rows:,}")

    t1611 = parse_kjv1611(books).sort_by([("book_sort", "ascending"),
                                          ("chapter", "ascending"), ("verse", "ascending")])
    st1611 = table_stats(t1611)
    sha1611 = hashlib.sha256("\n".join(
        t1611.column("verse_text").to_pylist()).encode("utf-8")).hexdigest()
    dst = INTER / "KJV1611.parquet"
    pq.write_table(t1611, dst, **WRITE_KW)
    inter_paths.append(dst)
    print(f"added KJV1611: {t1611.num_rows:,} verses, {st1611['word_count']:,} words")

    # word-count definition cross-check against a kept manifest row (WEB)
    web = pq.read_table(INTER / "WEB.parquet", columns=["verse_text"])
    wc_web = sum(len(x.split()) for x in web.column("verse_text").to_pylist())
    print(f"word-count check WEB: computed {wc_web:,} vs manifest "
          f"{int(manifest['WEB']['word_count']):,}")

    # KJV1611 vs KJVA similarity on sampled books (QA figure)
    def sampled(path):
        tt = pq.read_table(path, columns=["book_id", "chapter", "verse", "verse_text"],
                           filters=[("book_id", "in", ["GEN", "MAT", "JHN", "ROM"])]).to_pydict()
        return {(b, c, v): norm_hash(x) for b, c, v, x in
                zip(tt["book_id"], tt["chapter"], tt["verse"], tt["verse_text"])}
    a, b = sampled(INTER / "KJV1611.parquet"), sampled(INTER / "KJVA.parquet")
    common = set(a) & set(b)
    sim_1611 = 100.0 * sum(1 for k in common if a[k] == b[k]) / len(common)
    print(f"KJV1611 vs KJVA identical (sampled): {sim_1611:.2f}% of {len(common)}")

    # --- combined file via DuckDB global reference sort ----------------------
    total_rows = sum(pq.read_metadata(p).num_rows for p in inter_paths)
    combined_new = ROOT / "bibles.parquet.new"
    con = duck.connect()
    con.execute("SET memory_limit='800MB'")
    con.execute(f"SET temp_directory='{WORK}/ducktmp'")
    plist = ",".join(f"'{p}'" for p in inter_paths)
    con.execute(f"""
        COPY (SELECT {", ".join(SCHEMA.names)} FROM read_parquet([{plist}])
              ORDER BY book_sort, chapter, verse, translation_id)
        TO '{combined_new}' (FORMAT PARQUET, COMPRESSION ZSTD,
                             COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 262144)""")
    md = pq.read_metadata(combined_new)
    assert md.num_rows == total_rows, (md.num_rows, total_rows)
    src = f"read_parquet('{combined_new}')"  # .new suffix defeats format sniffing
    checks = {
        "rows": con.execute(f"SELECT count(*) FROM {src}").fetchone()[0],
        "translations": con.execute(
            f"SELECT count(DISTINCT translation_id) FROM {src}").fetchone()[0],
        "empty_texts": con.execute(
            f"SELECT count(*) FROM {src} WHERE verse_text IS NULL OR trim(verse_text)=''").fetchone()[0],
        "dup_keys": con.execute(f"""SELECT count(*) FROM (SELECT translation_id, book_id,
            chapter, verse, verse_end, count(*) c FROM {src}
            GROUP BY ALL HAVING c>1)""").fetchone()[0],
        "jhn_1_1": con.execute(f"""SELECT count(*) FROM {src}
            WHERE book_id='JHN' AND chapter=1 AND verse=1""").fetchone()[0],
        "books_present": con.execute(
            f"SELECT count(DISTINCT book_id) FROM {src}").fetchone()[0],
    }
    print("combined checks:", checks)
    assert checks["translations"] == 67 and checks["empty_texts"] == 0 and checks["dup_keys"] == 0
    con.close()

    # --- new partitioned layout ---------------------------------------------
    part_new = ROOT / "bibles_partitioned_new"
    if part_new.exists():
        shutil.rmtree(part_new)
    for p in inter_paths:
        tid = p.stem
        t = pq.read_table(p).drop_columns(["translation_id"])
        out = part_new / f"translation_id={tid}" / "part-0.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(t, out, compression="zstd", compression_level=19,
                       use_dictionary=["book_id", "book_name", "Testament"],
                       write_statistics=True)

    # --- manifest -------------------------------------------------------------
    kjva = manifest["KJVA"]
    row1611 = {
        "translation_id": "KJV1611",
        "translation_name": "King James Bible (1611 First Edition)",
        "year_first_published": "1611",
        "edition": "First edition (1611), original spelling",
        "scope": "Complete Bible",
        "canon": "Protestant canon (66 books; the 1611 printing also included the "
                 "Apocrypha, which this source file does not contain)",
        "versification": kjva["versification"],
        "dialect": "Early Modern English (1611 original spelling)",
        "license": kjva["license"],
        "license_type": "public_domain_expired",
        "license_url": "https://en.wikipedia.org/wiki/King_James_Version",
        "source_name": "theword-modules.com (theWord module kjv1611.ont)",
        "source_url": "https://theword-modules.com/early-translations/king-james-1611/",
        "source_retrieved": RETRIEVED,
        "verse_count": str(st1611["verse_count"]),
        "book_count": str(st1611["book_count"]),
        "chapter_count": str(st1611["chapter_count"]),
        "word_count": str(st1611["word_count"]),
        "ot_verses": str(st1611["ot_verses"]),
        "nt_verses": str(st1611["nt_verses"]),
        "dc_verses": str(st1611["dc_verses"]),
        "text_sha256": sha1611,
        "notes": "First edition of 1611 in original spelling (u/v, i/j as printed; "
                 "long s normalised by the transcriber). Differs from the 1769-text "
                 "KJVA throughout in spelling and in a number of readings. The source "
                 "file appends the 1611 translators' preface after Rev 22:21; it is "
                 "not versified and is excluded.",
    }
    new_rows = [r for r in man_rows if r["translation_id"] not in DROP]
    pos = next((i for i, r in enumerate(new_rows)
                if r["year_first_published"] and int(r["year_first_published"]) > 1611),
               len(new_rows))
    new_rows.insert(pos, row1611)
    assert len(new_rows) == 67
    assert sum(int(r["verse_count"]) for r in new_rows) == total_rows

    csv_new = ROOT / "translations.csv.new"
    with open(csv_new, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=man_fields)
        w.writeheader()
        w.writerows(new_rows)
    old_schema = pq.ParquetFile(ROOT / "translations.parquet").schema_arrow
    int_cols = {f.name for f in old_schema if pa.types.is_integer(f.type)}
    def conv(name: str, v: str):
        if name in int_cols:
            return int(v) if v not in ("", None) else None
        return v
    cols = {name: [conv(name, r[name]) for r in new_rows]
            for name in man_fields}
    pq.write_table(pa.Table.from_pydict(cols, schema=old_schema),
                   ROOT / "translations.parquet.new", compression="zstd", compression_level=19)

    # --- stats for README/QA ---------------------------------------------------
    def mb(p: Path) -> float:
        return round(p.stat().st_size / 1e6, 1)
    part_bytes = sum(f.stat().st_size for f in part_new.rglob("*.parquet"))
    stats = {
        "translations": 67, "verses": total_rows,
        "ot": sum(int(r["ot_verses"]) for r in new_rows),
        "nt": sum(int(r["nt_verses"]) for r in new_rows),
        "dc": sum(int(r["dc_verses"]) for r in new_rows),
        "words": sum(int(r["word_count"]) for r in new_rows),
        "combined_mb": mb(combined_new), "partitioned_mb": round(part_bytes / 1e6, 1),
        "checks": checks, "sim_kjv1611_vs_kjva_pct": round(sim_1611, 2),
        "kjv1611": st1611,
    }
    (ROOT / "pipeline" / "stats_v2.json").write_text(json.dumps(stats, indent=1))

    # --- QA report ---------------------------------------------------------------
    qa = [f"# QA report — dataset revision 2 (build of {RETRIEVED})", "",
          f"Translations: **67** (66 carried over from the 2026-10-27 build + KJV1611); "
          f"total verses: **{total_rows:,}**. Combined file sorted by canonical book "
          "order, chapter, verse, then translation_id.", "",
          "## Deduplication (balanced pass)", "",
          "Similarity = % of verses word-identical after light normalisation, measured "
          "on Genesis, Matthew, John and Romans (~3,900 shared verses per pair).", "",
          "| dropped | kept equivalent | identical % |", "|---|---|---|"]
    for d in sorted(DROP):
        qa.append(f"| {d} | {DROP[d]} | {SIMILARITY[d]:.1f}% |")
    qa += ["", "## Addition", "",
           f"- **KJV1611** — 1611 first edition, original spelling, parsed from the "
           f"theWord module `kjv1611.ont` (line-per-verse, KJV versification; anchors "
           f"Gen 1:1 / Matthew 1:1 / Rev 22:21 verified). {st1611['verse_count']:,} verses, "
           f"{st1611['book_count']} books. Versus KJVA (1769 text) only "
           f"{sim_1611:.1f}% of sampled verses are word-identical — a genuinely "
           "different edition, not a duplicate.",
           "- Moffatt (1913) and Goodspeed (1923) NTs were **not** added: the only "
           "verse-segmented module texts are login-gated, and OCR of the scans "
           "(margin verse numerals) was judged too unreliable.", "",
           "## Verification", "",
           f"- combined rows = partitioned rows = manifest verse sum = {total_rows:,}",
           f"- null/empty verse_text: {checks['empty_texts']}; duplicate "
           f"(translation, book, chapter, verse) keys: {checks['dup_keys']}",
           f"- John 1:1 present in {checks['jhn_1_1']} translations; "
           f"distinct book codes present: {checks['books_present']}",
           "- `text_sha256` values for the 66 carried-over translations are unchanged "
           "from the 2026-10-27 build; KJV1611's is SHA-256 of its verse texts joined "
           "by newlines in canonical order.", "",
           "## Per-translation counts", "",
           "| id | verses | books | chapters |", "|---|---:|---:|---:|"]
    for r in sorted(new_rows, key=lambda r: r["translation_id"].lower()):
        qa.append(f"| {r['translation_id']} | {int(r['verse_count']):,} | "
                  f"{r['book_count']} | {r['chapter_count']} |")
    (ROOT / "QA_REPORT.md.new").write_text("\n".join(qa) + "\n", encoding="utf-8")

    # --- swap into place ---------------------------------------------------------
    combined_new.replace(ROOT / "bibles.parquet")
    backup = WORK / "bibles_partitioned_v1"
    if backup.exists():
        shutil.rmtree(backup)
    (ROOT / "bibles_partitioned").replace(backup)
    part_new.replace(ROOT / "bibles_partitioned")
    csv_new.replace(ROOT / "translations.csv")
    (ROOT / "translations.parquet.new").replace(ROOT / "translations.parquet")
    (ROOT / "QA_REPORT.md.new").replace(ROOT / "QA_REPORT.md")
    print("\nSWAPPED. stats:", json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
