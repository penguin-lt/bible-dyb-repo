#!/usr/bin/env python3
"""Scrape one Bible version from bible.com (YouVersion) into per-book JSON.

bible.com exposes each chapter at /bible/<version_id>/<USFM_BOOK>.<chapter>.<ABBR>
with every verse carrying a `data-usfm="BOOK.chapter.verse"` attribute, so the
text is already verse-segmented and server rendered — no OCR, no JavaScript.

Why not bibliatodo.info: that site serves the same British & Foreign Bible
Society digital editions but fronts every page with a Cloudflare challenge
(403 to plain requests), so it cannot be scraped programmatically.

robots.txt of bible.com disallows only search, parallel-reader and RSC paths;
/bible/<id>/<book>.<ch>.<abbr> is allowed. Requests are spaced out.

  python3 pipeline/biblecom_fetch.py 3010 TEG          # Isaiah (Tegid)
  python3 pipeline/biblecom_fetch.py --book 3010 TEG GEN
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "pipeline" / "biblecom_raw"
BASE = "https://www.bible.com/bible"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml"}
DELAY = 1.2

BOOKS = [("GEN", "GEN"), ("EXO", "EXO"), ("LEV", "LEV"), ("NUM", "NUM"), ("DEU", "DEU"),
         ("JOS", "JOS"), ("JDG", "JDG"), ("RUT", "RUT"), ("1SA", "1SA"), ("2SA", "2SA"),
         ("1KI", "1KI"), ("2KI", "2KI"), ("1CH", "1CH"), ("2CH", "2CH"), ("EZR", "EZR"),
         ("NEH", "NEH"), ("EST", "EST"), ("JOB", "JOB"), ("PSA", "PSA"), ("PRO", "PRO"),
         ("ECC", "ECC"), ("SNG", "SNG"), ("ISA", "ISA"), ("JER", "JER"), ("LAM", "LAM"),
         ("EZK", "EZK"), ("DAN", "DAN"), ("HOS", "HOS"), ("JOL", "JOL"), ("AMO", "AMO"),
         ("OBA", "OBA"), ("JON", "JON"), ("MIC", "MIC"), ("NAM", "NAM"), ("HAB", "HAB"),
         ("ZEP", "ZEP"), ("HAG", "HAG"), ("ZEC", "ZEC"), ("MAL", "MAL"), ("MAT", "MAT"),
         ("MRK", "MRK"), ("LUK", "LUK"), ("JHN", "JHN"), ("ACT", "ACT"), ("ROM", "ROM"),
         ("1CO", "1CO"), ("2CO", "2CO"), ("GAL", "GAL"), ("EPH", "EPH"), ("PHP", "PHP"),
         ("COL", "COL"), ("1TH", "1TH"), ("2TH", "2TH"), ("1TI", "1TI"), ("2TI", "2TI"),
         ("TIT", "TIT"), ("PHM", "PHM"), ("HEB", "HEB"), ("JAS", "JAS"), ("1PE", "1PE"),
         ("2PE", "2PE"), ("1JN", "1JN"), ("2JN", "2JN"), ("3JN", "3JN"), ("JUD", "JUD"),
         ("REV", "REV")]

# bible.com wraps every verse span with data-usfm="BOOK.CH.VERSE"; a verse made of
# several poetic lines is emitted as several spans sharing one data-usfm, so all
# spans with the same id are joined in document order.
FRAG_RE = re.compile(r'data-usfm="([A-Z0-9]{3})\.(\d+)\.(\d+)"')


def get(url: str, tries: int = 3) -> str | None:
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=90) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(3 * (n + 1))
        except Exception:
            time.sleep(3 * (n + 1))
    return None


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'")
          .replace("&#39;", "'").replace("&mdash;", "\u2014").replace("&hellip;", "\u2026"))
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)   # span splits leave a space before punctuation
    return s.strip()


FRAG_RE = re.compile(r'data-usfm="([A-Z0-9]{3})\.(\d+)\.(\d+)"')


def get(url: str, tries: int = 3) -> str | None:
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=90) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(3 * (n + 1))
        except Exception:
            time.sleep(3 * (n + 1))
    return None


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'")
          .replace("&#39;", "'").replace("&mdash;", "\u2014").replace("&hellip;", "\u2026"))
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)   # span splits leave a space before punctuation
    return s.strip()


BLOCK_RE = re.compile(r'<div class="[^"]*ChapterContent_verse__[^"]*"\s*data-usfm="'
                       r'([A-Z0-9]{3})\.(\d+)\.(\d+)"(.*?)(?=<div class="[^"]*ChapterContent_verse__|\Z)', re.S)


def parse(html: str) -> dict[int, str]:
    """Collect the text of every span that carries this verse's data-usfm.

    bible.com marks each verse fragment with data-usfm="BOOK.CH.VERSE"; a verse is
    the concatenation of all fragments with the same id, in document order (poetic
    lines, italic words and supplied words are separate spans of the same verse).
    """
    parts: dict[int, list[str]] = {}
    for m in FRAG_RE.finditer(html):
        vs = int(m.group(3))
        start = m.end()
        nxt = FRAG_RE.search(html, start)
        end = min(nxt.start() if nxt else len(html), start + 4000)
        chunk = html[start:end]
        # keep only this span's own text, not following siblings' spans
        depth, i = 1, 0
        while i < len(chunk):
            if chunk.startswith("<span", i):
                depth += 1
                i = chunk.find(">", i) + 1
                continue
            if chunk.startswith("</span", i):
                depth -= 1
                if depth == 0:
                    chunk = chunk[:i]
                    break
                i = chunk.find(">", i) + 1
                continue
            i += 1
        txt = clean(chunk)
        # fragments of the span's own markup can leave angle brackets behind;
        # the verse label ("2 ") is the first text node inside the span
        txt = re.sub(r"[<>]", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        txt = re.sub(r"^\d+\s+", "", txt).strip()
        if txt:
            parts.setdefault(vs, []).append(txt)
    return {k: " ".join(v) for k, v in sorted(parts.items())}


def fetch_book(vid: str, abbr: str, usfm: str, max_ch: int = 150) -> dict[str, dict[str, str]]:
    book: dict[str, dict[str, str]] = {}
    blanks = 0
    for ch in range(1, max_ch + 2):
        html = get(f"{BASE}/{vid}/{usfm}.{ch}.{abbr}")
        time.sleep(DELAY)
        verses = parse(html) if html else {}
        if verses:
            book[str(ch)] = {str(k): v for k, v in sorted(verses.items())}
            blanks = 0
        else:
            blanks += 1
            if blanks >= 2:
                break
    return book


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    vid, abbr = argv[0], argv[1]
    only = argv[3:] if len(argv) > 3 and argv[2] == "--book" else ([argv[2]] if len(argv) > 2 else [])
    outdir = RAW / f"{abbr}"
    outdir.mkdir(parents=True, exist_ok=True)
    for bid, usfm in BOOKS:
        if only and bid not in only:
            continue
        f = outdir / f"{bid}.json"
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            print(f"  {abbr} {bid}: cached, {sum(len(v) for v in d.values())} verses")
            continue
        book = fetch_book(vid, abbr, usfm)
        if book:
            f.write_text(json.dumps(book, ensure_ascii=False), encoding="utf-8")
        print(f"  {abbr} {bid}: {len(book)} chapters, "
              f"{sum(len(v) for v in book.values())} verses", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
