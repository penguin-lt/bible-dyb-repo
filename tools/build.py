#!/usr/bin/env python3
"""Build the public-domain critical editions as per-edition SQLite databases."""
import json
import os
import subprocess
import sys

ROOT = '/home/user/work/ed'
RAW = f'{ROOT}/raw'
OUT = f'{ROOT}/out'
BOOKS = '/home/user/work/repo/bibles/text/books.csv'
TOOL = '/home/user/work/repo/tools/usfm_to_sqlite.py'

# ebible id -> (filename, full name, language, year, scope, dialect, edition,
#               provenance note)
EDITIONS = [
    # ---- Greek New Testament ----
    ('grcbyz',
     'Patriarchal Greek New Testament (1904, Antoniades)',
     'grc', 1904, 'New Testament', 'Koine Greek',
     'The 1904 Patriarchal edition authorised by the Ecumenical Patriarchate of '
     'Constantinople, edited by Vasileios Antoniades, with 19-21 corrections '
     'from later editions. The received Byzantine text of the Orthodox churches.'),
    ('grcmt',
     'Greek New Testament, Majority Text (Robinson-Pierpont)',
     'grc', 2018, 'New Testament', 'Koine Greek',
     'The New Testament in the Original Greek: Byzantine Textform, Maurice A. '
     'Robinson and William G. Pierpont.'),
    ('grcsr',
     "Solid Rock Greek New Testament (Scholar's Edition)",
     'grc', 2020, 'New Testament', 'Koine Greek',
     "Solid Rock Greek New Testament, Scholar's Edition, ed. Joey McCollum and "
     "Stephen L. Brown. Its editors describe it as collated from other editions "
     "rather than a fresh critical edition."),
    ('grctcgnt',
     'Text-Critical Greek New Testament',
     'grc', 2021, 'New Testament', 'Koine Greek',
     'The Text-Critical Greek New Testament, Byzantine text with a critical '
     'apparatus; copyright is not claimed or asserted for the text.'),
    ('grctr',
     'Greek Textus Receptus (Stephanus, Elzevir, Scrivener)',
     'grc', 1550, 'New Testament', 'Koine Greek',
     'The Greek Textus Receptus, including the variants of Stephanus (1550), '
     'Elzevir and Scrivener (1894).'),
    ('grc-tisch',
     'Tischendorf Greek New Testament (8th edition)',
     'grc', 1872, 'New Testament', 'Koine Greek',
     "Constantin von Tischendorf, Novum Testamentum Graece, editio octava "
     "critica maior (1869-1872), with morphological tags."),
    # ---- Greek Old Testament ----
    ('grclxx',
     'Septuagint (Greek Old Testament)',
     'grc', 1930, 'Old Testament', 'Koine Greek',
     'The Old Testament in Ancient Greek, the Septuagint translation as digitised '
     'by eBible.org.'),
    ('grcbrent',
     "Brenton's Greek Text of the Septuagint",
     'grc', 1844, 'Old Testament', 'Koine Greek',
     "The Greek text printed alongside Sir Lancelot Brenton's English "
     "translation of the Septuagint (1844)."),
    # ---- Hebrew ----
    ('hbo',
     'Hebrew Masoretic Text (Westminster Leningrad Codex)',
     'hbo', 1008, 'Old Testament', 'Biblical Hebrew',
     'The Masoretic text of the Westminster Leningrad Codex (B19a), pointed, '
     'without morphological tagging.'),
    ('hboWLC',
     'Westminster Leningrad Codex with Strong\'s and morphology',
     'hbo', 1008, 'Old Testament', 'Biblical Hebrew',
     'The Westminster Leningrad Codex with word-level Strong\'s numbers and '
     'morphology tags (OSHM-style), reduced to reading text here.'),
    # ---- Coptic ----
    ('copbhc',
     'Coptic New Testament, Bohairic',
     'cop', 1905, 'New Testament', 'Bohairic Coptic',
     'The Bohairic (Memphitic) Coptic New Testament.'),
    ('copcnt',
     'Coptic New Testament (Bohairic, narrative form)',
     'cop', 1905, 'New Testament', 'Bohairic Coptic',
     'A second public-domain Bohairic Coptic New Testament, in narrative form. '
     'Verified Bohairic dialect, not Sahitic: the only Sahidic edition on '
     'eBible.org is Sahidica, which is copyrighted and therefore excluded.'),
    # ---- added later, Vulgate ----
    ('latVUC',
     'Vulgate (Clementine, 1598)',
     'lat', 1598, 'Old and New Testaments', 'Latin',
     'Biblia Sacra Vulgata, Clementine edition (1592-1598). The eBible edition '
     'carries the ordinary gloss and patristic commentary in footnotes; those are '
     'not part of the biblical text and are not included here.'),
    # ---- added later, non-USFM sources; built from the MANUAL list ----
    ('WH', None, None, None, None, None, None),
]

WH = {
    'dir': f'{RAW}/wh',
    'file': 'Westcott and Hort Greek New Testament (1881).sqlite3',
    'id': 'grcwh',
    'name': 'Westcott and Hort Greek New Testament (1881)',
    'language': 'grc', 'year': 1881, 'scope': 'New Testament',
    'dialect': 'Koine Greek',
    'edition': ('The New Testament in the Original Greek, Brooke Foss Westcott and '
                'Fenton John Anthony Hort (Cambridge, 1881). Text by Maurice A. '
                'Robinson, maintained by Ulrik Sandborg-Petersen. Unaccented; '
                'doubtful readings appear in square brackets as printed.'),
    'source_name': 'byztxt / ByzantineText.com (Robinson, Sandborg-Petersen)',
    'source': 'https://github.com/byztxt/greektext-westcott-hort',
}


# non-USFM sources: (format, source dir, licence, source name, source url)
EXTRA = {
    'grcwh': dict(format='betacode', dir=f'{RAW}/wh',
                  license='Public Domain',
                  source_name='byztxt / ByzantineText.com (Robinson, Sandborg-Petersen)',
                  source='https://github.com/byztxt/greektext-westcott-hort'),
    'grcnestle': dict(format='nestle', dir=f'{RAW}/nestle', license='Public Domain',
                      source_name='biblicalhumanities.org (morphology released CC0)',
                      source='https://github.com/biblicalhumanities/Nestle1904'),
    'copsahh': dict(format='sword', dir=f'{RAW}/sahidic', license='Public Domain',
                    source_name='CrossWire Bible Society (CopSahHorner module)',
                    source='https://www.crosswire.org/sword/modules/ModInfo.jsp?modName=CopSahHorner'),
    'hbolet': dict(format='letteris', dir=f'{RAW}/letteris', license='Public Domain',
                   source_name='benemanuel/letteris transcription (GPL-3.0)',
                   source='https://github.com/benemanuel/letteris'),
}

# the four non-USFM editions: id -> metadata
MANUAL = [
    dict(id='grcwh', name='Westcott and Hort Greek New Testament (1881)',
         language='grc', year=1881, scope='New Testament', dialect='Koine Greek',
         edition='The New Testament in the Original Greek, Brooke Foss Westcott and '
                 'Fenton John Anthony Hort (Cambridge, 1881). Text by Maurice A. '
                 'Robinson, maintained by Ulrik Sandborg-Petersen. Unaccented; '
                 'doubtful readings appear in square brackets as printed.'),
    dict(id='grcnestle', name='Nestle Greek New Testament (1904)',
         language='grc', year=1904, scope='New Testament', dialect='Koine Greek',
         edition='Novum Testamentum Graece, Eberhard Nestle (Stuttgart, 1904). '
                 'Accented text with its critical signs, from the CC0 morphological '
                 'edition.'),
    dict(id='copsahh', name='Sahidic Coptic New Testament (Horner, 1911)',
         language='cop', year=1911, scope='New Testament', dialect='Sahidic',
         edition='The Coptic Version of the New Testament in the Southern Dialect, '
                 'G. W. Horner (Oxford, 1911-1924). Chapter-level text spread across '
                 'reference verses; verse boundaries are approximate.'),
    dict(id='hbolet', name='Hebrew Bible (Letteris, 1866)',
         language='hbo', year=1866, scope='Old Testament', dialect='Biblical Hebrew',
         edition="Torah, Nevi'im and Ketuvim, edited by Meir Halevi Letteris "
                 '(2nd edition, Berlin 1866). Fully vocalised with te’amim. The '
                 '1866 text is public domain; this transcription is distributed '
                 'under GPL-3.0.'),
]

rows = []
for eid, name, lang, year, scope, dialect, note in EDITIONS:
    if eid == 'WH':
        continue                      # built from the MANUAL list below
    src = f'{RAW}/{eid}'
    fn = f'{name}.sqlite3'
    lic = 'Public Domain'
    source_name = 'eBible.org'
    source = f'https://ebible.org/Scriptures/details.php?id={eid}'
    fmt = 'usfm'
    if eid in EXTRA:
        e = EXTRA[eid]
        src, fmt = e['dir'], e['format']
        source_name, source = e['source_name'], e['source']
    subprocess.run([sys.executable, TOOL, '--usfm-dir', src, '--format', fmt,
                    '--out-dir', OUT, '--filename', fn, '--id', eid,
                    '--name', name, '--language', lang, '--year', str(year),
                    '--scope', scope, '--dialect', dialect, '--license', lic,
                    '--edition', note, '--source-name', source_name,
                    '--source', source, '--books-csv', BOOKS], check=True)
    rows.append({'id': eid, 'file': fn, 'name': name, 'language': lang,
                 'year': year, 'scope': scope, 'source': source})

for m in MANUAL:
    e = EXTRA[m['id']]
    fn = f"{m['name']}.sqlite3"
    subprocess.run([sys.executable, TOOL, '--usfm-dir', e['dir'],
                    '--format', e['format'], '--out-dir', OUT,
                    '--filename', fn, '--id', m['id'], '--name', m['name'],
                    '--language', m['language'], '--year', str(m['year']),
                    '--scope', m['scope'], '--dialect', m['dialect'],
                    '--license', e['license'], '--edition', m['edition'],
                    '--source-name', e['source_name'], '--source', e['source'],
                    '--books-csv', BOOKS], check=True)
    rows.append({'id': m['id'], 'file': fn, 'name': m['name'],
                 'language': m['language'], 'year': m['year'],
                 'scope': m['scope'], 'source': e['source']})

json.dump(rows, open(f'{ROOT}/editions.json', 'w'), indent=1, ensure_ascii=False)
print(f'{len(rows)} editions built')
