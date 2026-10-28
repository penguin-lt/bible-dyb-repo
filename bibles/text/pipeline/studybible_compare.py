#!/usr/bin/env python3
"""Compare studybible.info English versions against the dataset (Matthew).

For every version code cached in pipeline/studybible_raw/<CODE>/MAT.json, the
verse text is compared with each dataset translation over the same Matthew
verses, using the same normalised exact-verse identity used by the duplicate
screen in the build scripts. High scores mean the code is a repackaging of
something already in the dataset; low scores mean it is a distinct text (whose
copyright status then decides whether it may be added at all).

  python3 pipeline/studybible_compare.py            # all cached codes
  python3 pipeline/studybible_compare.py Goodspeed  # one code, with samples
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "pipeline" / "studybible_raw"
ARCHIVE = ROOT / "pipeline" / "studybible_probe.json.gz"  # Matthew for every probed code
KEEP = {"MACE", "SAWYER", "OTTLEY"}  # already added in revision 6


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in s)
    return " ".join(s.split())


_probe: dict | None = None


def matthew(code: str) -> dict[tuple[int, int], str]:
    global _probe
    f = RAW / code / "MAT.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
    else:
        import gzip
        if _probe is None:
            if not ARCHIVE.exists():
                return {}
            with gzip.open(ARCHIVE, "rt", encoding="utf-8") as fh:
                _probe = json.load(fh)
        d = _probe.get(code)
        if not d:
            return {}
    return {(int(c), int(v)): norm(t) for c, ch in d.items()
            for v, t in ch.items()}


def dataset_matthew() -> dict[str, dict[tuple[int, int], str]]:
    t = pq.read_table(ROOT / "bibles.parquet",
                      columns=["translation_id", "book_id", "chapter", "verse",
                               "verse_text"],
                      filters=[("book_id", "=", "MAT")]).to_pydict()
    out: dict[str, dict[tuple[int, int], str]] = {}
    for tid, c, v, x in zip(t["translation_id"], t["chapter"], t["verse"],
                            t["verse_text"]):
        out.setdefault(tid, {})[(int(c), int(v))] = norm(x)
    return out


def main(argv: list[str]) -> int:
    ds = dataset_matthew()
    if argv:
        codes = argv
    else:
        import gzip
        with gzip.open(ARCHIVE, "rt", encoding="utf-8") as fh:
            codes = sorted(json.load(fh))
        codes += sorted(p.name for p in RAW.iterdir()
                        if p.is_dir() and (p / "MAT.json").exists())
    print(f"{'code':14s} {'verses':>6s}  closest dataset translation "
          f"(word-identical Matthew verses after normalisation)")
    rows = []
    for code in codes:
        if code.upper() in KEEP:
            continue
        cand = matthew(code)
        if not cand:
            print(f"{code:14s} {'0':>6s}  -")
            continue
        scored = []
        for tid, m in ds.items():
            common = set(cand) & set(m)
            if len(common) < 500:
                continue
            same = sum(1 for k in common if cand[k] == m[k])
            scored.append((100.0 * same / len(common), tid, len(common)))
        scored.sort(reverse=True)
        top = " ".join(f"{t} {p:.1f}% ({n})" for p, t, n in scored[:3])
        print(f"{code:14s} {len(cand):>6d}  {top}")
        rows.append({"code": code, "verses": len(cand), "top": scored[:5]})
    if argv:
        for code in argv:
            cand = matthew(code)
            for v in (1, 2, 3):
                ex = next((t for t in json.loads(
                    (RAW / code / "MAT.json").read_text(encoding="utf-8"))["1"].values()
                    if True), "") if False else ""
            d = json.loads((RAW / code / "MAT.json").read_text(encoding="utf-8"))
            print(f"\n-- {code}")
            for v in ("1", "2", "3"):
                print(f"   {v}: {d['1'].get(v, '')[:160]}")
    (ROOT / "pipeline" / "studybible_compare.json").write_text(
        json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
