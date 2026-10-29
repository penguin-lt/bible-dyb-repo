# Open Bible Study — a free, local reader over this corpus

A Logos-style study app with nothing to buy, nothing to sign into and no server:
one Python file, the standard library, and two SQLite databases built from the
Parquet in this repository.

```
python3 app/app.py --db search.db.zst              # core
python3 app/app.py --db search.db.zst --works works.db.zst   # + full library search
```

First run decompresses the `.zst` files next to themselves (about 6 GB of disk,
once) and opens <http://localhost:8080>. Plain uncompressed `.db` files work too.

**Download the databases:** see the
[`bible-search-rev1` release](https://github.com/penguin-lt/bible-dyb-repo/releases/tag/bible-search-rev1).

## What it does

| | |
|---|---|
| **Read** | any chapter in any of the 97 translations, with a reference box that accepts `Jn 3:16`, `Ps 23`, `Sirach 2`, `1 Cor 13:4-7`. Arrow keys page chapters. |
| **Passage guide** | click a verse: every commentary and note linked to that verse, its cross-references (clickable), the interlinear with morphology, and Strong's tags that open the lexicon. |
| **Study** | one verse side by side in six translations, then original language, lexicon, commentary and cross-references on a single page. |
| **Search** | verses (FTS5, BM25 ranked) or the whole reference library — 1,071,199 entries once `works.db` is installed. |
| **Library** | all 9,141 works, filterable by title and by the twenty subject areas, each with its entry count and licence. |

Every panel shows the licence of the work it quotes, because the corpus spans
public domain, CC0, CC BY, CC BY-SA and two CC BY-NC-ND texts.

## The two databases

| file | size | contents |
|---|---|---|
| `search.db` | 1.16 GB | 2,176,498 verses · 97 translations · 9,141-work catalogue · 298,075 verse-linked reference entries · 389,305 lexicon entries · 29,126 interlinear rows · FTS5 verse index |
| `works.db` | 4.68 GB | all 1,071,199 reference entries with an FTS5 index — the full library, not just verse-linked works |

`search.db` alone is enough to read, study a passage and search verses.
`works.db` is optional and only adds whole-library full-text search.

## Building them yourself

```
python3 app/build_searchdb.py \
    --bibles bibles.parquet \
    --works modules.parquet \
    --reference reference.parquet \
    --out search.db --works-out works.db
```

`bibles.parquet` is in `bibles/text/`; `modules.parquet` and `reference.parquet`
are on the `bible-reference-v5` release. About six minutes and ~2 GB of RAM, and
the build streams every pass so it does not need more.

## API

The server is also a small JSON API, if you would rather build your own front end
than use this one:

| endpoint | |
|---|---|
| `/api/meta` | books, translations, topics, counts |
| `/api/passage?book=JHN&ch=3&t=WEB,AKJV` | verses for a chapter |
| `/api/guide?book=JHN&ch=3&v=16` | commentaries, cross-references, interlinear, Strong's, lexicon |
| `/api/search?q=living water&scope=verses\|works&t=WEB` | FTS5 search |
| `/api/lexicon?q=G0026` | lexicon entries by Strong's number |
| `/api/works?topic=…&q=…` | the work catalogue |
| `/api/read?n=<work>&offset=0&limit=40` | read through a work |

## Requirements

Python 3.9 or newer. No pip install. `zstandard` is only needed if you serve the
compressed `.zst` databases; decompress to plain `.db` first if you would rather
not install it at all.
