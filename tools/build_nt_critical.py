#!/usr/bin/env python3
r"""Build the additional legally-obtainable NT critical editions into SQLite.

Sources (all public domain):
  1. Tregelles, Novum Testamentum Graece (London 1864) - Greek critical
     edition. Verse-per-line transcription of the 1864 print (the print itself
     is public domain; a mechanical transcription adds no copyright).
     Source: github.com/mrgreekgeek/tregelles-greek-nt (CSNTM/Tyndale House
     digitisation of Tregelles 1864), file verse-per-line/TNT2.txt.
  2-5. CrossWire SWORD zText modules (chapter-level OSIS; verses reconstructed
     by word count, marked verse_references=approximate like the Sahidic):
       Peshitta      Syriac Peshitta NT, BFBS 1905 print  (Public Domain)
       VulgSistine   Vulgata Sistina 1590, NT               (Public Domain)
       CSlElizabeth  Church Slavonic Elizabeth Bible 1757, NT (Public Domain)
       ArmWestern    Western Armenian NT, 1853             (Public Domain)

Usage: python3 tools/build_nt_critical.py <workdir> <outdir>
   <workdir>/treg/verse-per-line/TNT2.txt
   <workdir>/mods/<Module>/modules/texts/ztext/<mod>/nt.bzs|.bzz
   <workdir>/books.csv  (shared book catalogue)
"""
import csv
import json
import os
import re
import sqlite3
import struct
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from usfm_to_sqlite import SCHEMA, OSIS_BOOK, chunk_verses  # noqa: E402

NT = ["MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH",
      "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS",
      "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"]

TRE_BOOK = {'Mat': 'MAT', 'Mark': 'MRK', 'Luke': 'LUK', 'John': 'JHN',
            'Acts': 'ACT', 'Rom': 'ROM', '1Co': '1CO', '2Co': '2CO',
            'Gal': 'GAL', 'Eph': 'EPH', 'Phi': 'PHP', 'Col': 'COL',
            '1Th': '1TH', '2Th': '2TH', '1Ti': '1TI', '2Ti': '2TI',
            'Tit': 'TIT', 'Phm': 'PHM', 'Phlm': 'PHM', 'Heb': 'HEB', 'Jas': 'JAS',
            '1Pet': '1PE', '2Pet': '2PE', '1John': '1JN', '2John': '2JN',
            '3John': '3JN', 'Jude': 'JUD', 'Rev': 'REV'}


def load_counts():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'data', 'verse_counts.json')
    return json.load(open(p, encoding='utf-8'))['verses_per_chapter']


def load_catalog(path):
    cat = {}
    for r in csv.DictReader(open(path, encoding='utf-8-sig')):
        cat[r['book_id']] = (r.get('book_name_standard') or r['book_id'],
                             r.get('Testament'),
                             int(r['book_sort']) if r.get('book_sort') else None)
    return cat


def parse_tregelles(path, counts):
    books, order = {}, []
    for ln in open(path, encoding='utf-8'):
        m = re.match(r'^([A-Za-z0-9]+)\.(\d+):(\d+)\s+(.*)$', ln.strip())
        if not m:
            continue
        bid = TRE_BOOK.get(m.group(1))
        if not bid:
            continue
        c, v, t = int(m.group(2)), int(m.group(3)), m.group(4).strip()
        if not t:
            continue
        books.setdefault(bid, [])
        if bid not in order:
            order.append(bid)
        books[bid].append((c, v, v, t))
    return [(b, books[b]) for b in order if b in books]


def sword_nt(moddir, counts, only_nt=True):
    zs = open(os.path.join(moddir, 'nt.bzs'), 'rb').read()
    zz = open(os.path.join(moddir, 'nt.bzz'), 'rb').read()
    if zs[:1] == b'x':
        zs = zlib.decompress(zs)
    xml = '\n'.join(zlib.decompress(zz[o:o + c]).decode('utf-8')
                    for o, c, u in (struct.unpack('<iii', zs[i * 12:(i + 1) * 12])
                                    for i in range(len(zs) // 12)))
    tokens = re.split(r'(<[^>]+>)', xml)
    books, order = {}, []
    book = chapter = None
    buf = []

    def flush():
        nonlocal buf
        if book and chapter and buf:
            import html as H
            body = H.unescape(re.sub(r'<[^>]+>', ' ', ''.join(buf)))
            body = re.sub(r'\s+', ' ', body).strip()
            if body:
                books[book].append((chapter, body))
        buf = []

    for tok in tokens:
        if tok.startswith('<'):
            om = re.search(r'osisID="([^"]+)"', tok)
            if not om:
                continue
            oid = om.group(1)
            if 'type="book"' in tok:
                flush()
                book, chapter = oid, None
                if oid not in books:
                    books[oid] = []
                    order.append(oid)
            elif tok.startswith('<chapter'):
                flush()
                chapter = int(oid.split('.')[1])
            continue
        if chapter is not None:
            buf.append(tok)
    flush()
    out = []
    for obid in order:
        bid = OSIS_BOOK.get(obid, obid)
        if only_nt and bid not in NT:
            continue
        rows = []
        for c, body in books[obid]:
            want = counts.get(bid, [0] * c)
            n = want[c - 1] if c - 1 < len(want) else 1
            for i, t in enumerate(chunk_verses(body, n)):
                rows.append((c, i + 1, i + 1, t))
        if rows:
            out.append((bid, rows))
    return out


def write_db(path, name, tid, year, edition, dialect, lic, licurl, source,
             source_name, scope, pairs, catalog, approx, notes):
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    order = [b for b, _ in pairs]
    order.sort(key=lambda b: (catalog.get(b, (b, None, 10 ** 6))[2] or 10 ** 6, b))
    db.executemany('INSERT INTO book VALUES (?,?,?,?,?)', [
        (b, catalog.get(b, (b, None, None))[0], i + 1,
         catalog.get(b, (None, None, None))[2],
         catalog.get(b, (None, 'NT', None))[1])
        for i, b in enumerate(order)])
    if catalog:
        db.executemany('INSERT INTO books VALUES (?,?,?,?,?)', [
            (b, v[0], v[1], v[2], None) for b, v in catalog.items()])
    total, chapters, words = 0, set(), 0
    nv = {}
    for bid, rows in pairs:
        db.executemany('INSERT INTO verse VALUES (?,?,?,?,?)',
                       [(bid, c, v, ve, t) for c, v, ve, t in rows])
        total += len(rows)
        chapters.update((bid, c) for c, _, _, _ in rows)
        words += sum(len(t.split()) for *_, t in rows)
        t = catalog.get(bid, (None, 'NT', None))[1]
        nv[t] = nv.get(t, 0) + len(rows)
    db.execute('INSERT INTO translation VALUES '
               '(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
               (name, name, year, edition, scope, '', '', dialect, lic,
                'Public Domain', licurl, source_name, source, '', total,
                len(order), len(chapters), words, nv.get('OT', 0),
                nv.get('NT', 0), nv.get('DC', 0), '', notes))
    db.execute("INSERT INTO verse_fts(verse_fts) VALUES('rebuild')")
    db.executemany('INSERT INTO note VALUES (?,?)', [
        ('schema', '2'), ('built', time.strftime('%Y-%m-%d')),
        ('source', source), ('generator', 'tools/build_nt_critical.py'),
        ('source_translation_id', tid), ('translation_name', name),
        ('format', 'SWORD zText module (CrossWire), NT' if approx else
         'verse-per-line transcription of the printed edition'),
        ('verse_references', 'approximate' if approx else 'exact')])
    db.commit()
    db.execute('ANALYZE')
    db.commit()
    db.close()
    print(f'{os.path.basename(path)}: {len(order)} books, {total:,} verses, '
          f'{len(chapters)} chapters')


def main():
    work, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    counts = load_counts()
    catalog = load_catalog(os.path.join(work, 'books.csv'))

    pairs = parse_tregelles(
        os.path.join(work, 'treg', 'verse-per-line', 'TNT2.txt'), counts)
    write_db(os.path.join(out, 'Tregelles Greek New Testament 1864.sqlite3'),
             'Tregelles Greek New Testament 1864', 'grctreg', 1864,
             'Novum Testamentum Domini nostri Jesu Christi Graece, ed. Tregelles 1864, with various readings in full',
             'Koine Greek', 'Public Domain',
             'https://en.wikipedia.org/wiki/Samuel_Prideaux_Tregelles',
             'https://github.com/mrgreekgeek/tregelles-greek-nt (CSNTM/Tyndale House digitisation of the 1864 print)',
             'mrgreekgeek/tregelles-greek-nt (Tregelles 1864 print, public domain)',
             'New Testament', pairs, catalog, False,
             'Greek critical edition of 1864. The printed text is public domain '
             '(London 1864); the verse-per-line transcription is a mechanical '
             'transcription of that print and adds no copyright. Polytonic '
             'accents as printed.')

    mods = [
        ('Peshitta', 'Syriac Peshitta New Testament (BFBS 1905).sqlite3',
         'syrpesh', 1905, 'Peshitta Syriac New Testament, British and Foreign Bible Society 1905 print',
         'Classical Syriac', 'https://www.crosswire.org/sword/modules/ModInfo.jsp?modName=Peshitta',
         'CrossWire SWORD module "Peshitta" (BFBS 1905 print of the ancient Peshitta; public domain)'),
        ('VulgSistine', 'Vulgate, Sixtine Edition 1590, New Testament.sqlite3',
         'latVulSist', 1590, 'Biblia Sacra Vulgatae Editionis Sixti Quinti, 1590, New Testament',
         'Ecclesiastical Latin', 'https://www.crosswire.org/sword/modules/ModInfo.jsp?modName=VulgSistine',
         'CrossWire SWORD module "VulgSistine" (Sixtine Vulgate 1590; public domain)'),
        ('CSlElizabeth', 'Church Slavonic Elizabeth Bible 1757, New Testament.sqlite3',
         'chuEliz', 1757, 'Church Slavonic Elizabeth Bible (1757 print, modernised spelling), New Testament',
         'Church Slavonic', 'https://www.crosswire.org/sword/modules/ModInfo.jsp?modName=CSlElizabeth',
         'CrossWire SWORD module "CSlElizabeth" (1757 Elizabeth Bible via rusbible.ru; underlying 16th-century Slavonic version is public domain)'),
    ]
    for mod, fname, tid, year, edition, dialect, licurl, src in mods:
        md = os.path.join(work, 'mods', mod, 'modules', 'texts', 'ztext',
                          mod.lower())
        pairs = sword_nt(md, counts)
        write_db(os.path.join(out, fname), fname[:-8], tid, year, edition,
                 dialect, 'Public Domain', licurl, src.split('(')[0].strip(),
                 src, 'New Testament', pairs, catalog, True,
                 'SWORD zText module: the source divides chapters but not '
                 'verses, so chapter text was split into one row per reference '
                 'verse by word count - verse boundaries are approximate; for '
                 'reading and full-text search, not verse-level citation.')


if __name__ == '__main__':
    main()
