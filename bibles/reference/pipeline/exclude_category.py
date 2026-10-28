"""Build a filtered reference database by excluding a category of work.

The canonical releases carry everything. This script produces a *narrower*
edition from the same partitions — currently used to cut commentaries, so a
consumer who wants lexicons, dictionaries, texts and apparatus without running
commentary does not have to filter a 780 MB file themselves.

Two rules are combined:
  * a work whose SWORD category is `Commentary`
  * a Sefaria work that Sefaria itself files under a commentary category
    (`Rishonim on…`, `Acharonim on…`, `Modern Commentary on…`, `…/Commentary`,
    or a leaf of the form `<work> on <book|tractate>`)

Sefaria categories are read from `books.json` rather than guessed from titles,
because titles miss commentaries named after a tractate (Tosafot on Bava Metzia)
and mis-fire on texts that merely mention a book.

Nothing is deleted from a release: this writes a separate directory plus a
`removed.csv` inventory, so any exclusion can be reversed by module id.

    python3 exclude_category.py --what commentaries [--apply]
"""
import argparse
import collections
import csv
import json
import os
import re
import shutil
import sys
import urllib.request

import pyarrow as pa
import pyarrow.parquet as pq

OUT = os.environ.get("REF_OUT", "/home/user/scratch/out")
PART = os.path.join(OUT, "partitioned")
SIDE = os.path.join(OUT, "manifests")
BOOKS = os.environ.get("REF_CACHE", "/home/user/scratch") + "/books.json"
BOOKS_URL = "https://raw.githubusercontent.com/Sefaria/Sefaria-Export/master/books.json"

# Sefaria's own commentary taxonomy
SEF_COMMENTARY = re.compile(
    r"(^|/)(Rishonim on|Acharonim on|Modern Commentary on|Commentary)(/|$)"
    r"|on (Tanakh|Mishnah|Talmud|Mishneh Torah)", re.I)


def load_books():
    if not os.path.exists(BOOKS):
        req = urllib.request.Request(BOOKS_URL, headers={"User-Agent": "bible-dyb/1.0"})
        with urllib.request.urlopen(req, timeout=600) as r, open(BOOKS, "wb") as fh:
            shutil.copyfileobj(r, fh)
    books = json.load(open(BOOKS))["books"]
    idx = {}
    for b in books:
        idx.setdefault((b["title"], b.get("versionTitle") or ""), b)
        idx.setdefault((b["title"], None), b)
    return idx


def sefaria_categories(manifest_row, idx):
    title, _, ver = str(manifest_row.get("module_name", "")).partition(" — ")
    b = idx.get((title, ver)) or idx.get((title, None))
    return (b or {}).get("categories") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", default="commentaries")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default=os.path.join(OUT, "filtered"))
    a = ap.parse_args()
    if a.what != "commentaries":
        raise SystemExit("only --what commentaries is implemented")

    idx = load_books()
    rows = {}
    for f in os.listdir(SIDE):
        if f.endswith(".json"):
            m = json.load(open(os.path.join(SIDE, f)))
            if m.get("status") == "ok":
                rows[m["module_id"]] = m

    keep, drop = {}, {}
    for mid, m in rows.items():
        reason = None
        if m.get("category") == "Commentary":
            reason = "SWORD category Commentary"
        elif mid.startswith("sefaria"):
            path = "/".join(sefaria_categories(m, idx))
            if SEF_COMMENTARY.search(path):
                reason = "Sefaria category: " + path
        (drop if reason else keep)[mid] = reason or m

    print(f"works in database      {len(rows)}")
    print(f"commentaries removed   {len(drop)}")
    print(f"works kept             {len(keep)}")
    print()
    print("removed by reason:")
    for r, c in collections.Counter(v for v in drop.values() if isinstance(v, str)).most_common(6):
        print(f"  {c:5d}  {r[:90]}")
    kept_entries = sum(int(rows[m].get("entry_count", 0)) for m in keep)
    kept_chars = sum(int(rows[m].get("char_count", 0)) for m in keep)
    print(f"\nkept text: {kept_entries:,} entries, {kept_chars/1e6:.1f} Mchars")

    if not a.apply:
        print("\n(dry run — pass --apply to write)")
        return

    os.makedirs(a.out, exist_ok=True)
    dst_part = os.path.join(a.out, "partitioned")
    dst_side = os.path.join(a.out, "manifests")
    os.makedirs(dst_part, exist_ok=True)
    os.makedirs(dst_side, exist_ok=True)
    for mid in keep:
        src = os.path.join(PART, mid + ".parquet")
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst_part, mid + ".parquet"))
        shutil.copy2(os.path.join(SIDE, mid + ".json"), os.path.join(dst_side, mid + ".json"))

    with open(os.path.join(a.out, "removed.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["module_id", "module_name", "topic", "language", "license",
                    "entry_count", "char_count", "reason"])
        for mid, reason in sorted(drop.items()):
            m = rows[mid]
            w.writerow([mid, m.get("module_name", ""), m.get("topic", ""),
                        m.get("language", ""), m.get("license", ""),
                        m.get("entry_count", 0), m.get("char_count", 0), reason])
    json.dump({"removed": len(drop), "kept": len(keep)},
              open(os.path.join(a.out, "filter_report.json"), "w"), indent=1)
    print(f"\nwritten to {a.out}: {len(keep)} partitions, removed.csv lists {len(drop)}")


if __name__ == "__main__":
    main()
