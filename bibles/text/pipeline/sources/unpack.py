#!/usr/bin/env python3
"""Restore the compressed source modules.

The binary source modules (MyBible/theWord SQLite3 files, the 1611 KJV .ont,
the MyBible zips) are stored gzipped to keep the workspace inside its size
limit — they compress to about a third. The build scripts read the plain
names, so run this once before a rebuild:

    python3 pipeline/sources/unpack.py          # restore every .gz
    python3 pipeline/sources/unpack.py NTM.SQLite3   # just one

COMPRESSED.json records the original size and the gzipped size of each file.
"""
import gzip
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(names: list[str]) -> int:
    for gz in sorted(HERE.glob("*.gz")):
        plain = HERE / gz.name[:-3]
        if names and plain.name not in names:
            continue
        if plain.exists():
            continue
        with gzip.open(gz, "rb") as fi, open(plain, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        print(f"restored {plain.name} ({plain.stat().st_size:,} bytes)")
    man = HERE / "COMPRESSED.json"
    if man.exists():
        print(f"{len(json.loads(man.read_text()))} files are stored gzipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
