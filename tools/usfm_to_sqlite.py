#!/usr/bin/env python3
r"""One SQLite database per critical edition, from eBible.org USFM.

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
import csv
import json
import os
import re
import sqlite3
import time
import unicodedata
import zipfile

BOOKS_CSV = None      # set from --books-csv; holds the shared book catalogue


def verse_counts(path):
    """{book_id: [verse count per chapter]} from the shared reference data.

    Used only where a source gives continuous chapter text with no verse
    divisions: the chapter is then split into one row per reference verse.
    """
    if not path or not os.path.exists(path):
        return {}
    counts = {}
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            counts[row['book_id']] = [int(x) for x in row['verses_per_chapter'].split()]
    return counts


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
    pending = []          # text seen before any verse is open (a \\d title)

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
            # a chapter boundary closes the previous verse, so text arriving
            # before the next \\v (a \\d subscription, say) cannot be
            # attributed to the last verse number of the old chapter
            verse = verse_key = verse_end = None
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
            buf = pending + [rest]
            pending = []
            continue
        if verse is None:
            pd = re.match(r'^\\d\s+(.*)$', line)
            if pd:
                pending.append(pd.group(1))
                continue
        if verse is not None:
            if line.startswith('\\'):
                # \d subscription: the printed note at the end of an epistle
                # ("written to the Romans from Corinth by Phoebe..."). It is
                # part of the edition's text, so it is appended to the verse it
                # follows rather than dropped.
                sub_d = re.match(r'^\\d\s+(.*)$', line)
                if sub_d:
                    buf.append(sub_d.group(1))
                    continue
                if re.match(r'^\\(?:s|ms|mr|sr|r|sp|qa|qac|qm\d?|lit|cl|cp|cd|'
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



# ------------------------------------------------------- other source formats
# Three of the editions are not USFM: Nestle 1904 ships as one tab-separated
# row per word, the Clementine Vulgate as OSIS-flavoured XML inside a compressed
# SWORD module, and Letteris as one row per verse with a simple book code. Each
# gets a small reader that returns the same shape the USFM reader returns:
# [(book_id, [(chapter, verse, verse_end, text)])].

BETA_USFM = {
    'MT': 'MAT', 'MR': 'MRK', 'LU': 'LUK', 'JOH': 'JHN', 'AC': 'ACT',
    'RO': 'ROM', '1CO': '1CO', '2CO': '2CO', 'GA': 'GAL', 'EP': 'EPH',
    'PHP': 'PHP', 'COL': 'COL', '1TH': '1TH', '2TH': '2TH', '1TI': '1TI',
    '2TI': '2TI', 'TIT': 'TIT', 'PHM': 'PHM', 'HE': 'HEB', 'JA': 'JAS',
    '1PE': '1PE', '2PE': '2PE', '1JO': '1JN', '2JO': '2JN', '3JO': '3JN',
    'JUDE': 'JUD', 'RE': 'REV',
}
OSIS_BOOK = {
    'Gen': 'GEN', 'Exod': 'EXO', 'Lev': 'LEV', 'Num': 'NUM', 'Deut': 'DEU',
    'Josh': 'JOS', 'Judg': 'JDG', 'Ruth': 'RUT', '1Sam': '1SA', '2Sam': '2SA',
    '1Kgs': '1KI', '2Kgs': '2KI', '1Chr': '1CH', '2Chr': '2CH', 'Ezra': 'EZR',
    'Neh': 'NEH', 'Esth': 'EST', 'Job': 'JOB', 'Ps': 'PSA', 'Prov': 'PRO',
    'Eccl': 'ECC', 'Song': 'SNG', 'Isa': 'ISA', 'Jer': 'JER', 'Lam': 'LAM',
    'Ezek': 'EZK', 'Dan': 'DAN', 'Hos': 'HOS', 'Joel': 'JOL', 'Amos': 'AMO',
    'Obad': 'OBA', 'Jonah': 'JON', 'Mic': 'MIC', 'Nah': 'NAM', 'Hab': 'HAB',
    'Zeph': 'ZEP', 'Hag': 'HAG', 'Zech': 'ZEC', 'Mal': 'MAL',
    'Tob': 'TOB', 'Jdt': 'JDT', 'AddEsth': 'ADE', 'Wis': 'WIS', 'Sir': 'SIR',
    'Bar': 'BAR', 'PrAzar': 'S3Y', 'Sus': 'SUS', 'Bel': 'BEL', 'EpJer': 'LJE',
    '1Macc': '1MA', '2Macc': '2MA', '3Macc': '3MA', '4Macc': '4MA',
    'Matt': 'MAT', 'Mark': 'MRK', 'Luke': 'LUK', 'John': 'JHN', 'Acts': 'ACT',
    'Rom': 'ROM', '1Cor': '1CO', '2Cor': '2CO', 'Gal': 'GAL', 'Eph': 'EPH',
    'Phil': 'PHP', 'Col': 'COL', '1Thess': '1TH', '2Thess': '2TH',
    '1Tim': '1TI', '2Tim': '2TI', 'Titus': 'TIT', 'Phlm': 'PHM', 'Heb': 'HEB',
    'Jas': 'JAS', '1Pet': '1PE', '2Pet': '2PE', '1John': '1JN', '2John': '2JN',
    '3John': '3JN', 'Jude': 'JUD', 'Rev': 'REV',
}


def chunk_verses(text, n):
    """Split a chunk of continuous text into n pieces at word boundaries."""
    words = text.split()
    if n <= 1 or len(words) <= n:
        return [' '.join(words)] if words else []
    target = max(1, round(len(words) / n))
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= target and len(out) < n - 1:
            out.append(' '.join(cur))
            cur = []
    if cur:
        out.append(' '.join(cur))
    return out


def read_sword_module(srcdir):
    """Read a SWORD zText module: the .bzs index lists (offset, compressed,
    uncompressed) size triplets into the .bzz data file, one block per book."""
    import struct
    import zlib
    base = os.path.join(srcdir, 'modules', 'texts', 'ztext')
    moddir = os.path.join(base, os.listdir(base)[0])
    zs = open(os.path.join(moddir, 'nt.bzs'), 'rb').read()
    zz = open(os.path.join(moddir, 'nt.bzz'), 'rb').read()
    if zs[:1] == b'x':
        zs = zlib.decompress(zs)
    if len(zs) % 12:
        raise SystemExit(f'{zs!r:.40}: unexpected block index size')
    out, start = [], 0
    for i in range(len(zs) // 12):
        off, csize, usize = struct.unpack('<iii', zs[i * 12:(i + 1) * 12])
        if off != start:
            raise SystemExit(f'block {i}: offset {off} != {start}')
        chunk = zlib.decompress(zz[off:off + csize])
        if len(chunk) != usize:
            raise SystemExit(f'block {i}: {len(chunk)} != {usize}')
        out.append(chunk.decode('utf-8'))
        start = off + csize
    return '\n'.join(out)


def read_osis(path):
    """OSIS-flavoured XML -> [(osis_book, [(chapter, verse, end, text)])].

    Handles <verse sID="Matt.1.1"/> markers and <verse>...</verse> spans. When a
    source divides chapters but not verses, the whole chapter is returned with
    verse 1 as a placeholder; the caller splits it.
    """
    import html
    xml = open(path, encoding='utf-8').read() if os.path.exists(path) else path
    tokens = re.split(r'(<[^>]+>)', xml)
    books, order = {}, []
    book = chapter = verse = None
    buf = []

    def flush():
        nonlocal buf
        if book is not None and chapter is not None and buf:
            body = html.unescape(re.sub(r'\s+', ' ', ''.join(buf))).strip()
            if body:
                books[book].append((chapter, verse or 1, verse or 1, body))
        buf = []

    for tok in tokens:
        if tok.startswith('<'):
            if tok.startswith(('<milestone', '<lb')):
                continue
            om = re.search(r'osisID="([^"]+)"', tok)
            if om:
                oid = om.group(1)
                if tok.startswith('<div'):
                    if '.' not in oid:
                        flush()
                        book, chapter, verse = oid, None, None
                        if oid not in books:
                            books[oid] = []
                            order.append(oid)
                elif tok.startswith('<chapter'):
                    flush()
                    parts = oid.split('.')
                    chapter = int(parts[1])
                    verse = None
                elif tok.startswith('<verse'):
                    if 'eID' in tok:
                        flush()
                        verse = None
                    else:
                        flush()
                        parts = oid.split('.')
                        if len(parts) >= 3:
                            chapter = int(parts[1])
                            verse = int(re.match(r'\d+', parts[2]).group(0))
            continue
        if chapter is not None:
            buf.append(tok)
    flush()
    return [(b, books[b]) for b in order if books[b]]


def read_nestle_tsv(path):
    """Nestle 1904: one row per word, BCV column like 'Matt 1:1'."""
    assert_ = 'BCV'
    books, order = {}, []
    verse_key = None
    buf = []
    book = chap = None

    def flush():
        if verse_key and buf:
            body = re.sub(r'\s+', ' ', ' '.join(buf)).strip()
            body = re.sub(r'\s+([,.;·])', r'\1', body)
            books[book].append((chap, verse, verse, body))
        buf.clear()

    for line in open(path, encoding='utf-8-sig'):
        parts = line.rstrip('\r\n').split('\t')
        if not parts or not parts[0] or parts[0] == assert_:
            continue
        ref = parts[0].strip()          # e.g. 'Matt 1:1' or '1Cor 13:4a'
        word = parts[1] if len(parts) > 1 else ''
        m = re.match(r'^(\S+)\s+(\d+):(\d+)([a-z]?)$', ref)
        if not m:
            continue
        obook, c, v, letter = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        bid = OSIS_BOOK.get(obook)
        if not bid:
            raise SystemExit(f'unknown book code in Nestle CSV: {obook!r}')
        key = (bid, c, v, letter)
        if key != verse_key:
            flush()
            verse_key = key
            book, chap, verse = bid, c, (v * 1000 + ord(letter)) if letter else v
            if bid not in books:
                books[bid] = []
                order.append(bid)
        buf.append(word)
    flush()
    return [(b, books[b]) for b in order]


MASORETIC_ORDER = [
    'GEN', 'EXO', 'LEV', 'NUM', 'DEU', 'JOS', 'JDG', 'RUT', '1SA', '2SA',
    '1KI', '2KI', '1CH', '2CH', 'EZR', 'NEH', 'EST', 'JOB', 'PSA', 'PRO',
    'ECC', 'SNG', 'ISA', 'JER', 'LAM', 'EZK', 'DAN', 'HOS', 'JOL', 'AMO',
    'OBA', 'JON', 'MIC', 'NAM', 'HAB', 'ZEP', 'HAG', 'ZEC', 'MAL']


def read_letteris_tsv(paths):
    """Letteris: 'NNx<TAB>chapter<TAB>verse<TAB>flag<TAB>n<TAB>text' where the
    book is a 1-based index into the Masoretic order (01O = Genesis)."""
    books, order = {}, []
    for path in sorted(paths):
        for line in open(path, encoding='utf-8-sig'):
            parts = line.rstrip('\r\n').split('\t')
            if len(parts) < 6:
                continue
            code, c, v, text = parts[0].strip(), parts[1], parts[2], parts[5].strip()
            if not re.fullmatch(r'\d{2}O', code) or not c.isdigit() or not v.isdigit():
                continue
            bid = MASORETIC_ORDER[int(code[:2]) - 1]
            if bid not in books:
                books[bid] = []
                order.append(bid)
            books[bid].append((int(c), int(v), int(v),
                               re.sub(r'\s+', ' ', text).strip()))
    return [(b, books[b]) for b in order]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--usfm-dir', required=True,
                    help='directory of .usfm files, a zip of them, or (with '
                         '--format betacode) a directory of *.WH files')
    ap.add_argument('--format', default='usfm',
                    choices=['usfm', 'betacode', 'nestle', 'sword', 'letteris'],
                    help='source format of --usfm-dir')
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

    global VERSE_COUNTS
    VERSE_COUNTS = json.load(open(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'data',
        'verse_counts.json'), encoding='utf-8'))['verses_per_chapter']

    books = {}          # book_id -> [(chapter, verse, verse_end, text)]
    order = []
    titles = {}

    if a.format in ('betacode', 'nestle', 'sword', 'letteris'):
        if a.format == 'betacode':
            pairs = read_beta_dir(a.usfm_dir)
            a.format_note = 'beta code, converted to unaccented Unicode Greek'
        elif a.format == 'nestle':
            pairs = read_nestle_tsv(os.path.join(a.usfm_dir, 'nestle1904.csv'))
            a.format_note = ('one row per word (BCV/text/morphology), joined into '
                             'verses; case and accents as published')
        elif a.format == 'sword':
            xml = read_sword_module(a.usfm_dir)
            pairs = []
            for obid, rows in read_osis(xml):
                bid = OSIS_BOOK.get(obid, obid)
                per_chapter = {}
                for c, v, _, t in rows:
                    per_chapter[c] = per_chapter.get(c, '') + ' ' + t
                wanted = VERSE_COUNTS.get(bid)
                out = []
                for c in sorted(per_chapter):
                    want = wanted[c - 1] if wanted and c - 1 < len(wanted) else 1
                    parts = chunk_verses(per_chapter[c].strip(), want)
                    out.extend((c, i + 1, i + 1, t) for i, t in enumerate(parts))
                pairs.append((bid, out))
            a.format_note = (
                'SWORD zText module, block-decompressed to OSIS. The source '
                'divides chapters but not verses, so chapter text was split into '
                'one row per reference verse by word count: verse boundaries are '
                'approximate, and this edition is for reading and full-text '
                'search, not for citation at verse level')
            a.approx = 1
        else:
            skip = {'Editornotes.utf8_txt', 'letteris.utf8_txt',
                    'wlc_utf8.utf8_txt', 'Psalms_151.utf8_txt'}
            paths = [os.path.join(a.usfm_dir, f) for f in os.listdir(a.usfm_dir)
                     if f.endswith('.utf8_txt') and f not in skip
                     and not f.endswith('_hebrew.utf8_txt')]
            pairs = read_letteris_tsv(paths)
            a.format_note = 'tab-separated verse rows, Masoretic book order'
        for bid, rows in pairs:
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
        ('format', getattr(a, 'format_note', '') if a.format != 'usfm'
         else 'USFM (eBible.org)'),
        ('verse_references', 'approximate' if getattr(a, 'approx', 0)
         else 'exact'),
    ])
    db.commit()
    db.execute('ANALYZE')
    db.commit()
    db.close()
    print(f'{a.filename}: {len(order)} books, {total:,} verses, {len(chapters)} chapters')


if __name__ == '__main__':
    main()
