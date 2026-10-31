#!/usr/bin/env python3
"""One SQLite database per critical edition, from eBible.org USFM.

Third source next to parquet_to_sqlite.py (verse corpus) and
reference_to_sqlite.py (reference works). Produces the same schema as a
translation database, so a critical edition drops into the same folder and the
same joins:

    translation  one row: id, name, year, language, edition, licence, source
    book         the books this edition contains, in its own order
    books        the shared book catalogue (optional, from books.csv)
    verse        book_id, chapter, verse, verse_end, text
    verse_fts    FTS5 over verse.text, external content
    note         k/v provenance

Markup is handled the same way the rest of the corpus handles it: word-level
markup is reduced to its text (\w word|strong="G1234"\w* -> word), notes and
cross-references are dropped, and paragraph marks are ignored. Nothing in the
verse text is invented.

    python3 tools/usfm_to_sqlite.py --usfm-dir raw/ --out-dir editions/ \\
        --id grcbyz --name "Patriarchal Greek New Testament (1904)" \\
        --language grc --year 1904 --license "Public Domain" \\
        --source "https://ebible.org/Scriptures/details.php?id=grcbyz"

Also reads the verse-per-line beta code layout used by the byztxt texts
(--format betacode), and converts beta code to Unicode Greek on the way in
(--transliterate), so those editions match the rest of the library.
"""
import argparse
import os
import re
import sqlite3
import time
import unicodedata
import zipfile

SCHEMA = """
PRAGMA page_size = 4096;
CREATE TABLE translation (
    translation_id TEXT PRIMARY KEY, translation_name TEXT NOT NULL,
    year_first_published INTEGER, edition TEXT, scope TEXT, canon TEXT,
    versification TEXT, dialect TEXT, license TEXT, license_type TEXT,
    license_url TEXT, source_name TEXT, source_url TEXT, source_retrieved TEXT,
    verse_count INTEGER, book_count INTEGER, chapter_count INTEGER,
    word_count INTEGER, ot_verses INTEGER, nt_verses INTEGER, dc_verses INTEGER,
    text_sha256 TEXT, notes TEXT);
CREATE TABLE book (book_id TEXT PRIMARY KEY, book_name TEXT NOT NULL,
    book_order INTEGER NOT NULL, book_sort INTEGER, testament TEXT);
CREATE TABLE books (book_id TEXT PRIMARY KEY, book_name_standard TEXT,
    "Testament" TEXT, book_sort INTEGER, translations_containing INTEGER);
CREATE TABLE verse (book_id TEXT NOT NULL REFERENCES book(book_id),
    chapter INTEGER NOT NULL, verse INTEGER NOT NULL, verse_end INTEGER,
    text TEXT NOT NULL, PRIMARY KEY (book_id, chapter, verse));
CREATE VIRTUAL TABLE verse_fts USING fts5(
    text, content='verse', content_rowid='rowid',
    tokenize="unicode61 remove_diacritics 2");
CREATE TABLE note (k TEXT PRIMARY KEY, v TEXT);
"""

# \w word|strong="G1234"\w*  ->  word      (also \+w, \nd, \qt ... variants)
WORD_TAG = re.compile(r'\\\+?w ([^|\\]*)(\|[^\\]*)?\\\+?w\*')
NOTE = re.compile(r'\\f\b.*?\\f\*', re.S)
XREF = re.compile(r'\\x\b.*?\\x\*', re.S)
# any \marker ... \marker* span: \bdit quoted OT text, \nd "Lord", \wj words
# of Jesus, \qt OT quotation, \fig figure captions, nested or not
SPAN = re.compile(r'\\\+?[a-z0-9]+(?:-[a-z0-9]+)?\s+([^\\]*?)\\\+?[a-z0-9]+(?:-[a-z0-9]+)?\*')
MARKER = re.compile(r'\\[a-z0-9\-]+\*?', re.I)


def sub_number(key):
    """'3' -> 3, '3a' -> 3003, '14α' -> 14011.

    Editions that print extra material as a sub-lettered verse (the LXX uses
    Greek letters: 14α, 14β) get a distinct key rather than colliding with the
    plain verse of the same number. The letter survives in the key, and the
    plain '14' is still present as its own row.
    """
    if isinstance(key, int):
        return key
    m = re.match(r'^(\d+)([^\s\d\-]?)$', str(key).strip())
    if not m:
        return 0
    n, letter = int(m.group(1)), m.group(2)
    return n * 1000 + ord(letter) if letter else n


def clean(text):
    """Reduce USFM inline markup to plain reading text."""
    text = NOTE.sub('', text)
    text = XREF.sub('', text)
    text = WORD_TAG.sub(lambda m: m.group(1), text)
    for _ in range(4):                      # nested character markup
        prev = text
        text = SPAN.sub(r'\1', text)
        if text == prev:
            break
    text = re.sub(r'\\[a-z0-9]+(?:-[a-z0-9]+)?\*', '', text)
    text = text.replace('\\w*', '').replace('\\w', '')
    text = text.replace('\\\\', '\\')
    return re.sub(r'\s+', ' ', text).strip()


# ---------------------------------------------------------------- beta code
# Robinson / Sandborg-Petersen beta code as used by the byztxt texts:
#   q ps   y th   c ch   f ph   v sigma
#   h eta (word-initial h = rough breathing)   w omega   x ksi   u/y? ...
#   v = final sigma (written for sigma everywhere in this encoding)
BETA_BASE = {'a': 'α', 'b': 'β', 'g': 'γ', 'd': 'δ', 'e': 'ε', 'z': 'ζ',
             'h': 'η', 'q': 'θ', 'i': 'ι', 'k': 'κ', 'l': 'λ', 'm': 'μ',
             'n': 'ν', 'x': 'ξ', 'o': 'ο', 'p': 'π', 'r': 'ρ', 's': 'σ',
             't': 'τ', 'u': 'υ', 'f': 'φ', 'c': 'χ', 'y': 'ψ', 'w': 'ω'}
VOWELS = set('aehiouw')


def beta_word(word):
    """Convert one beta-code word to Unicode Greek.

    Robinson's encoding is *unaccented*: it marks rough breathing on a
    word-initial h but carries no accents, so the output is unaccented too.
    Nothing is invented. Prepositions and other words that begin with a vowel
    keep a smooth breathing where Greek orthography requires one.
    """
    if not word:
        return word
    out = []
    n = len(word)
    for i, ch in enumerate(word):
        low = ch.lower()
        if low == 'q':
            out.append('ψ')
        elif low == 'y':
            out.append('θ')
        elif low == 'c':
            out.append('χ')
        elif low == 'f':
            out.append('φ')
        elif low in ('s', 'v'):
            out.append('ς' if i == n - 1 else 'σ')
        elif low == 'h':
            # h is simply eta: this encoding marks no breathings, so none are
            # invented here either
            out.append('η')
        elif low in BETA_BASE:
            out.append(BETA_BASE[low])
        else:
            out.append(ch)
    return ''.join(out)


def beta_line(line):
    """Convert a beta-code verse line, leaving punctuation and numbers alone."""
    return re.sub(r'[a-zA-Z]+', lambda m: beta_word(m.group(0)), line)


def transliterate(text):
    """Convert beta code to Unicode Greek.

    A few verses carry marginal apparatus after a bare '|' (the text, then the
    alternatives). The reading itself is everything before the first separator;
    the marginal notes are not verse text and are dropped.
    """
    text = text.split(' | ')[0]
    return beta_line(text)


# ---------------------------------------------------------------- readers
def read_usfm_dir(path):
    """Yield (usfm_filename, text) for every book file, in canonical order."""
    if path.endswith('.zip'):
        with zipfile.ZipFile(path) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith('.usfm'):
                    yield n, z.read(n).decode('utf-8-sig')
        return
    for n in sorted(os.listdir(path)):
        if n.lower().endswith('.usfm'):
            yield n, open(os.path.join(path, n), encoding='utf-8-sig').read()


BETA_LINE = re.compile(r'^\s*(\d+):(\d+)(?:-(\d+))?\s+(.*)$')
BETA_FILE = re.compile(r'^([1-3]?[A-Z]{2,4})\.WH$')


# the byztxt files use their own short book codes; map them to USFM
BETA_BOOKS = {'MT': 'MAT', 'MR': 'MRK', 'LU': 'LUK', 'JOH': 'JHN',
              'AC': 'ACT', 'RO': 'ROM', 'RE': 'REV', 'JUDE': 'JUD',
              'GA': 'GAL', '1JO': '1JN', '2JO': '2JN', '3JO': '3JN'}


def read_beta_dir(path):
    """Yield (book_id, [(chapter, verse, verse_end, text)]) for byztxt texts.

    Layout: one file per book (JOH.WH), verses starting "1:1 " but wrapping
    across several physical lines, so every line that does not open a new verse
    continues the one before it.
    """
    for n in sorted(os.listdir(path)):
        m = BETA_FILE.match(n)
        if not m:
            continue
        bid = BETA_BOOKS.get(m.group(1), m.group(1))
        rows = []
        cur = None          # (chapter, verse, verse_end, [parts])
        with open(os.path.join(path, n), encoding='utf-8', errors='replace') as f:
            for line in f:
                vm = BETA_LINE.match(line)
                if vm:
                    if cur:
                        rows.append(cur)
                    c, v = int(vm.group(1)), int(vm.group(2))
                    ve = int(vm.group(3)) if vm.group(3) else v
                    cur = (c, v, ve, [vm.group(4)])
                elif cur is not None and line.strip():
                    cur[3].append(line.strip())
        if cur:
            rows.append(cur)
        out = []
        for c, v, ve, parts in rows:
            body = transliterate(re.sub(r'\s+', ' ', ' '.join(parts)).strip())
            if body:
                out.append((c, v, ve, body))
        if out:
            yield bid, out


def parse_book(text, book_id, state):
    """Return [(chapter, verse, verse_end, text)] for one USFM book body."""
    out = []
    chapter = 0
    verse = None          # numeric verse number
    verse_key = None      # full key as printed, e.g. "3" or "3a"
    verse_end = None
    buf = []
    front = True

    def flush():
        nonlocal buf, verse_end
        if verse is not None:
            body = clean(' '.join(buf))
            if body:
                out.append((chapter, sub_number(verse_key),
                            sub_number(verse_end or verse_key), body))
        buf, verse_end = [], None

    for line in text.splitlines():
        if line.startswith('\\id'):
            front = False
            continue
        if front and not line.startswith(('\\c', '\\v')):
            continue
        if re.match(r'^\\c\s', line):
            flush()
            m = re.match(r'\\c\s+(\d+)', line)
            if m:
                chapter = int(m.group(1))
            continue
        m = re.match(r'^\\v\s+(\d+)([^\s\d\-]?)(?:-(\d+)([^\s\d\-]?))?\s*(.*)$', line)
        if m:
            flush()
            verse = int(m.group(1))
            verse_key = m.group(1) + m.group(2)
            verse_end = (m.group(3) + m.group(4)) if m.group(3) else None
            rest = m.group(5)
            # a new verse can also start mid-line
            buf = [rest]
            continue
        if verse is not None:
            if line.startswith('\\'):
                if re.match(r'^\\(?:s|ms|mr|sr|r|d|sp|qa|qac|qm\d?|lit|cl|cp|cd|'
                            r'fig|bk|ef|ex|imt|imte|iex|ip|ipr|ib|iq|ili|iot|io)\b',
                            line):
                    continue          # headings, titles, intros: not verse text
                sub = re.match(r'^\\(?:p|m|pi\d?|mi|nb|cls|li\d?|q\d?|b|pc|'
                               r'wj|va|vp|vp\*)\s*(.*)$', line)
                if sub:
                    buf.append(sub.group(1))
                continue
            buf.append(line)
    flush()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--usfm-dir', required=True,
                    help='directory of .usfm files, a zip of them, or (with '
                         '--format betacode) a directory of *.WH files')
    ap.add_argument('--format', choices=['usfm', 'betacode'], default='usfm')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--filename', required=True, help='output .sqlite3 name')
    ap.add_argument('--id', required=True, help='translation_id, e.g. grcbyz')
    ap.add_argument('--name', required=True, help='full human name')
    ap.add_argument('--language', default='')
    ap.add_argument('--year', default='')
    ap.add_argument('--scope', default='')
    ap.add_argument('--license', default='Public Domain')
    ap.add_argument('--license-url', default='')
    ap.add_argument('--source', default='')
    ap.add_argument('--source-name', default='eBible.org')
    ap.add_argument('--edition', default='')
    ap.add_argument('--dialect', default='')
    ap.add_argument('--books-csv', default='', help='book catalogue to embed')
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    catalog = []
    if a.books_csv:
        import csv
        for r in csv.DictReader(open(a.books_csv, encoding='utf-8-sig')):
            catalog.append((r['book_id'], r.get('book_name_standard'),
                            r.get('Testament'),
                            int(r['book_sort']) if r.get('book_sort') else None,
                            int(r['translations_containing'])
                            if r.get('translations_containing') else None))

    books = {}          # book_id -> [(chapter, verse, verse_end, text)]
    order = []
    titles = {}

    if a.format == 'betacode':
        for bid, rows in read_beta_dir(a.usfm_dir):
            if bid not in books:
                books[bid] = []
                order.append(bid)
                titles[bid] = bid
            books[bid].extend(rows)
    else:
        for fname, text in read_usfm_dir(a.usfm_dir):
            m = re.search(r'\\id\s+([A-Z0-9]{3})', text)
            if not m:
                continue
            bid = m.group(1)
            rows = parse_book(text, bid, None)
            if not rows:
                continue
            if bid not in books:
                books[bid] = []
                order.append(bid)
                hm = re.search(r'\\h\s+(.+)', text) or re.search(r'\\toc2\s+(.+)', text)
                titles[bid] = hm.group(1).strip() if hm else bid
            books[bid].extend(rows)

    path = os.path.join(a.out_dir, a.filename)
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)

    sort_of = {c[0]: c[3] for c in catalog}
    test_of = {c[0]: c[2] for c in catalog}
    name_of = {c[0]: c[1] for c in catalog}

    # canonical book order where the catalogue knows the book, source order else
    order.sort(key=lambda b: (sort_of.get(b) is None, sort_of.get(b) or 0, b))

    db.executemany('INSERT INTO book VALUES (?,?,?,?,?)',
                   [(bid, titles[bid] or name_of.get(bid, bid), i + 1,
                     sort_of.get(bid), test_of.get(bid))
                    for i, bid in enumerate(order)])
    if catalog:
        db.executemany('INSERT INTO books VALUES (?,?,?,?,?)', catalog)

    total = 0
    chapters = set()
    for bid in order:
        rows = books[bid]
        db.executemany('INSERT INTO verse VALUES (?,?,?,?,?)',
                       [(bid, c, v, ve, t) for c, v, ve, t in rows])
        total += len(rows)
        chapters.update((bid, c) for c, _, _, _ in rows)

    ot = sum(1 for b in order if test_of.get(b) == 'OT')
    nt = sum(1 for b in order if test_of.get(b) == 'NT')
    dc = sum(1 for b in order if test_of.get(b) == 'DC')
    nv = {}
    for bid in order:
        for c, v, _, _ in books[bid]:
            nv[test_of.get(bid)] = nv.get(test_of.get(bid), 0) + 1
    words = sum(len(t.split()) for bid in order for *_, t in books[bid])

    db.execute('INSERT INTO translation VALUES '
               '(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
               (a.name, a.name, int(a.year) if a.year.isdigit() else None,
                a.edition, a.scope, '', '', a.dialect, a.license,
                'Public Domain' if 'public domain' in a.license.lower() else '',
                a.license_url, a.source_name, a.source, '', total, len(order),
                len(chapters), words, nv.get('OT', 0), nv.get('NT', 0),
                nv.get('DC', 0), '', ''))
    db.execute("INSERT INTO verse_fts(verse_fts) VALUES('rebuild')")
    db.executemany('INSERT INTO note VALUES (?,?)', [
        ('schema', '2'),
        ('built', time.strftime('%Y-%m-%d')),
        ('source', a.source),
        ('generator', 'tools/usfm_to_sqlite.py'),
        ('source_translation_id', a.id),
        ('translation_name', a.name),
        ('format', 'USFM (eBible.org)' if a.format == 'usfm'
         else 'beta code, converted to unaccented Unicode Greek'),
    ])
    db.commit()
    db.execute('ANALYZE')
    db.commit()
    db.close()
    print(f'{a.filename}: {len(order)} books, {total:,} verses, {len(chapters)} chapters')


if __name__ == '__main__':
    main()
