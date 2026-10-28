#!/usr/bin/env python3
"""Scrape verse text from studybible.info (one version at a time, politely).

The site serves one chapter per page at /<VERSION>/<Book>%20<chapter>, with each
verse wrapped in

    <sup><a class="verse_ref <VERSION>" ...>12</a></sup>  verse text

Chapter pages are preferred; when a chapter page comes back empty (only the
verse-of-the-day widget) the verse-by-verse pages /<VERSION>/<Book>%20<ch>:<v>
are used instead, because those are server rendered.

Everything is cached under pipeline/studybible_raw/<VERSION>/<BOOK>.json so the
run can be stopped and resumed. Nothing is downloaded twice.

  python3 pipeline/studybible_fetch.py Mace
  python3 pipeline/studybible_fetch.py --list
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "pipeline/studybible_raw"          # cache written by a live scrape
ARCHIVE = ROOT / "pipeline/studybible_raw.json.gz"  # what actually ships in the workspace
PROBE = ROOT / "pipeline/studybible_probe.json.gz"  # Matthew only, for the comparison table
BASE = "https://studybible.info"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
DELAY = 0.5  # seconds between requests

# standard 66-book order, as used by the site's own navigation
BOOKS = [
    ("GEN", "Genesis"), ("EXO", "Exodus"), ("LEV", "Leviticus"), ("NUM", "Numbers"),
    ("DEU", "Deuteronomy"), ("JOS", "Joshua"), ("JDG", "Judges"), ("RUT", "Ruth"),
    ("1SA", "1 Samuel"), ("2SA", "2 Samuel"), ("1KI", "1 Kings"), ("2KI", "2 Kings"),
    ("1CH", "1 Chronicles"), ("2CH", "2 Chronicles"), ("EZR", "Ezra"), ("NEH", "Nehemiah"),
    ("EST", "Esther"), ("JOB", "Job"), ("PSA", "Psalms"), ("PRO", "Proverbs"),
    ("ECC", "Ecclesiastes"), ("SNG", "Song of Songs"), ("ISA", "Isaiah"), ("JER", "Jeremiah"),
    ("LAM", "Lamentations"), ("EZK", "Ezekiel"), ("DAN", "Daniel"), ("HOS", "Hosea"),
    ("JOL", "Joel"), ("AMO", "Amos"), ("OBA", "Obadiah"), ("JON", "Jonah"),
    ("MIC", "Micah"), ("NAM", "Nahum"), ("HAB", "Habakkuk"), ("ZEP", "Zephaniah"),
    ("HAG", "Haggai"), ("ZEC", "Zechariah"), ("MAL", "Malachi"),
    ("MAT", "Matthew"), ("MRK", "Mark"), ("LUK", "Luke"), ("JHN", "John"),
    ("ACT", "Acts"), ("ROM", "Romans"), ("1CO", "1 Corinthians"), ("2CO", "2 Corinthians"),
    ("GAL", "Galatians"), ("EPH", "Ephesians"), ("PHP", "Philippians"), ("COL", "Colossians"),
    ("1TH", "1 Thessalonians"), ("2TH", "2 Thessalonians"), ("1TI", "1 Timothy"),
    ("2TI", "2 Timothy"), ("TIT", "Titus"), ("PHM", "Philemon"), ("HEB", "Hebrews"),
    ("JAS", "James"), ("1PE", "1 Peter"), ("2PE", "2 Peter"), ("1JN", "1 John"),
    ("2JN", "2 John"), ("3JN", "3 John"), ("JUD", "Jude"), ("REV", "Revelation"),
]
BOOKNAME = dict(BOOKS)

VERSE_RE = re.compile(
    r'<sup><a class="verse_ref [^"]*"[^>]*>\s*(\d+)\s*</a></sup>(.*?)(?=<sup><a class="verse_ref|</div>)',
    re.S)


def get(path: str, tries: int = 3) -> str | None:
    url = BASE + path
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            time.sleep(2 * (n + 1))
    return None


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
          .replace("&#8217;", "\u2019").replace("&#8216;", "\u2018")
          .replace("&mdash;", "\u2014").replace("&ndash;", "\u2013"))
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_verses(html: str) -> dict[str, str]:
    out = {}
    for num, body in VERSE_RE.findall(html):
        txt = clean(body)
        if txt:
            out.setdefault(num, txt)
    return out


def chapter_html(version: str, book: str, ch: int) -> str | None:
    return get(f"/{version}/{urllib.parse.quote(book)}%20{ch}")


def book_verses(version: str, book_id: str, max_ch: int, probe: bool = True) -> dict:
    book = BOOKNAME[book_id]
    chapters: dict[str, dict[str, str]] = {}
    empty_streak = 0
    for ch in range(1, max_ch + 2):
        h = chapter_html(version, book, ch)
        time.sleep(DELAY)
        verses = parse_verses(h) if h else {}
        if verses:
            chapters[str(ch)] = verses
            empty_streak = 0
            continue
        empty_streak += 1
        # a single empty chapter can be a gap; two in a row ends the book
        if empty_streak >= 2 or (ch > 1 and not probe):
            break
        if ch == 1:
            break  # no chapter pages at all for this book/version
    if not chapters:
        return {}
    return chapters


def known_max_chapters() -> dict[str, int]:
    """Largest chapter number per book across the dataset already built."""
    import pyarrow.parquet as pq
    t = pq.read_table(ROOT / "bibles.parquet", columns=["book_id", "chapter"])
    df = t.to_pandas()
    return df.groupby("book_id")["chapter"].max().to_dict()


def book_verses_parallel(version: str, book_id: str, max_ch: int, workers: int = 4) -> dict:
    """Fetch every chapter of a book concurrently (bounded, so the site is not hammered).

    Books are short (Psalms is the worst case at 150 chapters), and one bad chapter
    (a few psalm titles are missing on the site) must not stop the rest, so a failed
    chapter is skipped rather than ending the book.
    """
    from concurrent.futures import ThreadPoolExecutor

    book = BOOKNAME[book_id]
    chs = list(range(1, max_ch + 2))

    def one(ch):
        h = chapter_html(version, book, ch)
        time.sleep(DELAY / workers)
        return ch, (parse_verses(h) if h else {})

    out: dict[str, dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = dict(ex.map(one, chs))
    for ch in sorted(res):
        if not res[ch]:
            # two consecutive empty chapters past the end of the book end it
            if ch > 1 and not res.get(ch - 1):
                break
            continue
        out[str(ch)] = res[ch]
    return out


def load_archive() -> dict[str, dict[str, dict[str, dict[str, str]]]]:
    """Read the compressed scrape cache that ships with the repo.

    The plain tree is 17 MB in 193 files; the same data gzipped is 2 MB in one
    file, which keeps the workspace inside its size limit. A live scrape still
    writes the plain tree first and `pack_archive()` folds it back in.
    """
    import gzip
    if not ARCHIVE.exists():
        return {}
    with gzip.open(ARCHIVE, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def pack_archive() -> None:
    import gzip
    import shutil
    blob = {d.name: {f.stem: json.loads(f.read_text(encoding="utf-8"))
                     for f in sorted(d.glob("*.json"))}
            for d in sorted(RAW.iterdir()) if d.is_dir()}
    with gzip.open(ARCHIVE, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(blob, fh, ensure_ascii=False, separators=(",", ":"))
    shutil.rmtree(RAW)
    print(f"packed {len(blob)} codes -> {ARCHIVE.name} "
          f"({ARCHIVE.stat().st_size/1e6:.1f} MB)")


def fetch_version(version: str, books: list[str] | None = None) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    outdir = RAW / version
    outdir.mkdir(parents=True, exist_ok=True)
    maxch = known_max_chapters()
    todo = books or [b for b, _ in BOOKS]
    summary = {}
    for bid in todo:
        f = outdir / f"{bid}.json"
        if f.exists():
            summary[bid] = len(json.loads(f.read_text()))
            continue
        chapters = book_verses_parallel(version, bid, int(maxch.get(bid, 150)))
        if chapters:
            f.write_text(json.dumps(chapters, ensure_ascii=False), encoding="utf-8")
        summary[bid] = len(chapters)
        print(f"  {version} {bid}: {len(chapters)} chapters "
              f"({sum(len(v) for v in chapters.values())} verses)", flush=True)
    return summary


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "--list":
        idx = json.loads((ROOT / "pipeline/studybible/versions_index.json").read_text())
        for code, (name, desc) in idx.items():
            print(f"{code:20s} {desc}")
        return 0
    for version in argv:
        print(f"== {version}", flush=True)
        fetch_version(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
