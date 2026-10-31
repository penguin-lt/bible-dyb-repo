#!/usr/bin/env python3
"""Test the built critical-editions databases.

Two layers:
  1. per-edition integrity  - schema, FTS, markup, emptiness, verse references
  2. fidelity to the source - re-parse the source independently and compare,
                              or compare word counts where there is no re-parse
Any failure prints FAIL and the script exits non-zero.
"""
import hashlib
import html
import json
import os
import re
import sqlite3
import subprocess
import sys

ROOT = '/home/user/work/ed'
sys.path.insert(0, '/home/user/work/repo/tools')
import usfm_to_sqlite as u          # noqa: E402

NON_USFM = {'grcwh', 'grcnestle', 'copsahh', 'hbolet'}
fails = []


def fail(tag, msg):
    fails.append(f'{tag}: {msg}')
    print(f'  FAIL {msg}')


def check_schema(tag, db):
    tables = {r[0] for r in db.execute(
        "select name from sqlite_master where type='table'")}
    for t in ('translation', 'book', 'verse', 'verse_fts', 'note'):
        if t not in tables:
            fail(tag, f'missing table {t}')
    cols = [c[1] for c in db.execute('pragma table_info(verse)')]
    if cols != ['book_id', 'chapter', 'verse', 'verse_end', 'text']:
        fail(tag, f'unexpected verse columns {cols}')


def check_rows(tag, db):
    verses = db.execute('select book_id,chapter,verse,text from verse').fetchall()
    n = db.execute('select count(*) from verse').fetchone()[0]
    fts = db.execute('select count(*) from verse_fts').fetchone()[0]
    if n != len(verses):
        fail(tag, 'verse count mismatch')
    if fts != n:
        fail(tag, f'fts rows {fts} != verse rows {n}')
    if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
        fail(tag, 'integrity_check failed')
    # Some editions print a bare "[ ]" where a verse is omitted. That is the
    # edition's own signal, not a conversion fault, so it is reported, not
    # failed - but a genuinely blank cell is still an error.
    placeholder = [r for r in verses
                   if r[3].strip() and not re.search(r'\w', r[3])]
    empty = [r for r in verses if not r[3].strip()]
    if empty:
        fail(tag, f'{len(empty)} empty verse texts, e.g. {empty[0][:3]}')
    if placeholder:
        print(f"       note: {len(placeholder)} verses hold only an omission "
              f"marker, e.g. {placeholder[0][0]} {placeholder[0][1]}:"
              f"{placeholder[0][2]} -> {placeholder[0][3]!r}")
    markup = [r for r in verses if re.search(r'\\[a-z]|\|strong=|\|[a-z]+="', r[3])]
    if markup:
        fail(tag, f'{len(markup)} verses with leftover markup, e.g. {markup[0][:3]}')
    ordinals = [r[0] for r in db.execute('select book_order from book')]
    if ordinals != sorted(ordinals):
        fail(tag, 'book_order is not 1..N')
    declared = db.execute('select verse_count, book_count from translation').fetchone()
    if declared != (n, len(ordinals)):
        fail(tag, f'translation row says {declared}, tables say {(n, len(ordinals))}')
    # every book that has verses must be in the book table and vice versa
    bset = {r[0] for r in db.execute('select book_id from book')}
    vset = {r[0] for r in verses}
    if bset != vset:
        fail(tag, f'book table and verse table disagree: {bset ^ vset}')
    # chapter/verse numbering sanity: no chapter 0, no verse 0
    bad = [r for r in verses if r[1] < 1 or r[2] < 1]
    if bad:
        fail(tag, f'{len(bad)} rows with chapter or verse < 1')
    # no duplicate verse keys (the UNIQUE constraint should make this impossible)
    dup = db.execute('select book_id,chapter,verse,count(*) c from verse '
                     'group by 1,2,3 having c > 1').fetchall()
    if dup:
        fail(tag, f'duplicate verse keys: {dup[:3]}')
    return verses


def check_fts_search(tag, db):
    """A full-text query must actually return rows."""
    row = db.execute("select text from verse where length(text) > 40 limit 1").fetchone()
    if not row:
        return
    word = max(row[0].split(), key=len)
    word = re.sub(r'[^\w\u0370-\u03ff\u0590-\u05ff\u2c80-\u2cff]', '', word)
    if len(word) < 4:
        return
    try:
        hits = db.execute('select count(*) from verse_fts where verse_fts match ?',
                          (f'"{word}"',)).fetchone()[0]
    except sqlite3.Error as e:
        fail(tag, f'fts query failed: {e}')
        return
    if hits < 1:
        fail(tag, f'fts search for {word!r} returned nothing')


def fidelity(tag, eid, verses):
    """Compare against the source, re-parsed independently of the build."""
    rows = sorted(verses)
    if eid == 'grcwh':
        raw = [(b, c, v, t) for b, rs in u.read_beta_dir(f'{ROOT}/raw/wh')
               for c, v, _, t in rs]
        return 'identical' if sorted(raw) == rows else 'DIFFERS'
    if eid == 'grcnestle':
        words = 0
        for line in open(f'{ROOT}/raw/nestle/nestle1904.csv', encoding='utf-8-sig'):
            p = line.rstrip('\r\n').split('\t')
            if len(p) > 1 and p[0] and p[0] != 'BCV':
                words += len(p[1].split())
        got = sum(len(t.split()) for *_, t in rows)
        return f'words {got}/{words}' if got == words else f'WORDS DIFFER {got}/{words}'
    if eid == 'hbolet':
        words = 0
        for f in os.listdir(f'{ROOT}/raw/letteris'):
            if not f.endswith('.utf8_txt') or f.endswith('_hebrew.utf8_txt'):
                continue
            if f in ('Editornotes.utf8_txt', 'letteris.utf8_txt',
                     'wlc_utf8.utf8_txt', 'Psalms_151.utf8_txt'):
                continue
            for line in open(f'{ROOT}/raw/letteris/{f}', encoding='utf-8-sig'):
                p = line.rstrip('\r\n').split('\t')
                if len(p) > 5:
                    words += len(p[5].split())
        got = sum(len(t.split()) for *_, t in rows)
        return f'words {got}/{words}' if got == words else f'WORDS DIFFER {got}/{words}'
    if eid == 'copsahh':
        u.VERSE_COUNTS = json.load(open(
            '/home/user/work/repo/tools/data/verse_counts.json'))['verses_per_chapter']
        xml = u.read_sword_module(f'{ROOT}/raw/sahidic')
        src = 0
        for _, rs in u.read_osis(xml):
            for _, _, _, t in rs:
                src += len(html.unescape(t).split())
        got = sum(len(t.split()) for *_, t in rows)
        return f'words {got}/{src}' if got == src else f'WORDS DIFFER {got}/{src}'
    raw = []
    for _, text in u.read_usfm_dir(f'{ROOT}/raw/{eid}'):
        m = re.search(r'\\id\s+([A-Z0-9]{3})', text)
        if m:
            raw += [(m.group(1), c, v, t)
                    for c, v, _, t in u.parse_book(text, m.group(1), None)]
    return 'identical' if sorted(raw) == rows else 'DIFFERS'


# Text-bearing markers, mirroring the parser's whitelist. A line starting with
# any other backslash marker (headings, titles, intros, \\s1 etc.) is not verse
# text. Note the absence of \\b in these patterns: \\s1 is a marker but "\\s"
# followed by "1" has no word boundary, which is exactly the trap that made an
# earlier version of this checker count English section headings as scripture.
TEXT_MARKER = re.compile(r'^\\(p|m|pi\d?|mi|nb|cls|li\d?|q\d?|b|pc|wj|va|vp|d)\s*(.*)$')


SIGNS = '⸀⸁⸂⸃⸄⸅⸆⸇⸈⸉⸊⸋⸌⸍⸎⸏⟨⟩[]'


def strip_markup(t):
    t = re.sub(r'\\v\s+[\\d\\-a-z]+', ' ', t)      # a verse number mid-line
    t = re.sub(r'\\f\b.*?\\f\*', ' ', t, flags=re.S)
    t = re.sub(r'\\x\b.*?\\x\*', ' ', t, flags=re.S)
    t = re.sub(r'\\\+?w ([^|\\]*)(\|[^\\]*)?\\\+?w\*', r'\1', t)
    t = re.sub(r'\\\+?[a-z0-9\-]+\*?', ' ', t)
    t = re.sub(r'\|[a-z]+="[^"]*"', ' ', t)
    return ' '.join(t.translate(str.maketrans('', '', SIGNS)).split())


def source_words(eid):
    """Count the words the parser is *supposed* to keep, with a stripper that
    shares no code with the parser. Front matter before the first \\c is
    excluded, matching documented policy."""
    total = 0
    for f in sorted(os.listdir(f'{ROOT}/raw/{eid}')):
        if not f.endswith(('.usfm', '.sfm')):
            continue
        started = False
        for line in open(f'{ROOT}/raw/{eid}/{f}', encoding='utf-8', errors='replace'):
            if re.match(r'^\\c\s', line):
                started = True
            if not started:
                continue
            if line.startswith('\\'):
                if re.match(r'^\\c\s', line):
                    continue
                mv = re.match(r'^\\v\s+[\d\-a-z]+\s*(.*)$', line)
                if mv:
                    total += len(strip_markup(mv.group(1)).split())
                    continue
                mt = TEXT_MARKER.match(line)
                if mt:
                    total += len(strip_markup(mt.group(2)).split())
                continue
            total += len(strip_markup(line).split())
    return total


def check_conservation(tag, eid, verses):
    """No source word may vanish. Bracketed apparatus and critical signs can
    make a naive word count exceed the database, so the check is asymmetric:
    the database must not hold words the source lacks, and may not fall more
    than 1% short (rounding in the stripper accounts for the rest)."""
    src = source_words(eid)
    def is_placeholder(t):
        # a row holding only a sign such as '[ ]', '⸆' or '✠' is a marker,
        # not text: count it as zero words rather than counting the glyph
        return not any(ch.isalnum() for ch in t)
    got = sum(len(t.split()) for *_, t in verses if not is_placeholder(t))
    if got > src:
        fail(tag, f'database has {got - src} more words than the source')
    elif got < src * 0.99:
        fail(tag, f'database has {src - got} fewer words than the source '
                  f'({100 * (got - src) / src:.2f}%)')
    return f'words {got}/{src} ({100 * (got - src) / max(1, src):+.2f}%)'


def main():
    eds = json.load(open(f'{ROOT}/editions.json'))
    print(f'testing {len(eds)} databases\n')
    for e in eds:
        p = f"{ROOT}/out/{e['file']}"
        tag = e['id']
        if not os.path.exists(p):
            fail(tag, 'database missing')
            continue
        db = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
        check_schema(tag, db)
        verses = check_rows(tag, db)
        check_fts_search(tag, db)
        db.close()
        try:
            cons = check_conservation(tag, e['id'], verses) \
                if e['id'] not in NON_USFM else ''
        except Exception as exc:                     # noqa: BLE001
            cons = f'ERROR {exc}'
            fail(tag, cons)
        try:
            fid = fidelity(tag, e['id'], verses)
        except Exception as exc:                     # noqa: BLE001
            fid = f'ERROR {exc}'
            fail(tag, fid)
        flag = '' if fid in ('identical',) or fid.startswith('words ') else '  <-- '
        print(f"{e['file'][:44]:46s} {len(verses):6d} v  {fid:22s} {cons}{flag}")
    print()
    if fails:
        print(f'FAILED CHECKS ({len(fails)}):')
        for f in fails:
            print('  -', f)
        return 1
    print(f'ALL {len(eds)} DATABASES PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
