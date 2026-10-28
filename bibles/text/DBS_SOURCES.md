# arc.dbs.org (Digital Bible Society) as a source

Source: <https://arc.dbs.org/data/> and <https://arc.dbs.org/data/scripture/>
(read 2026-10-28). The DBS "arc" site publishes five reference datasets:

| dataset | keyed by | records |
|---|---|---:|
| countries | ISO 3166a | — |
| languages | ISO 639-3 | — |
| scripts | ISO 15924 | — |
| organizations | slug | — |
| **scripture** | publication abbreviation | 6,829 |

The arc site states plainly that "there is no public download for the other three
sets: countries, organizations and scripture" and that the records are only
browsable as pages. The site also sits behind a Cloudflare challenge
(HTTP 403 to plain requests), so its pages could not be fetched directly here.

**The same data is public in the DBS GitHub organisation.** `digitalbiblesociety/data`
(the repo behind arc.dbs.org) clones to 441 MB / 33,384 files and contains:

* `bibles/` — 5,682 per-publication JSON files (`bibles/ENGKJV.json`, …), each with
  `abbr`, `title`, `description`, `iso`, `script`, `year`, `country_id`,
  `copyright`, `copyright_type`, `bible_links` (type/provider/url), `language`,
  `country`;
* `bibles.json` (5,367 records) and `bibles_dbs.json` (1,690 records) — the
  searchable index, with `id`, title (`tt`), vernacular title (`tv`), ISO code,
  language name, country and date;
* `bible_links.json`, `bible_equivalents.json` — cross-platform ids (YouVersion,
  Bible Brain, eBible, Davar);
* `organizations/`, `countries/`, `languages/`, `scripts/`, `alphabets/`,
  `languages.json`, `countries.json`, `organizations.json` — the other four sets.

## What the scripture dataset contains

**241 English publications** (`iso: eng` — 247 `ENG*` files, six of which are edition records without an `abbr`), each a catalogue record — not text.
The records are the *inventory*, with links out to where a text can be read.

Copyright fields across those 247 records:

| `copyright_type` | records |
|---|---:|
| `OPEN` ("Public Domain") | 57 |
| none stated | 175 |
| `RESERVED` | 4 |
| `CCBYNCND` / `CCBYND` / `CCBYSA` | 5 |

The 129 records whose copyright field says "Public Domain" are the useful list
(the machine-readable extract is `pipeline/research_dbs_inventory.json`).
Against those:

* **already in the dataset** — Wycliffe (1360/1380/1388/1395/1850 editions),
  Tyndale, Coverdale, Matthew, Great, Taverner's (a Matthew revision), Geneva,
  Bishops', Douay–Rheims and its Challoner revision, KJV 1611 and 1769, Whiston,
  Wesley, Worsley, Purver, Doddridge, Belsham, Kneeland, Campbell, Palfrey,
  Webster, Lowth, Macknight, Murdock (both entries), Brenton, Thomson, Newcome,
  Wakefield, Sharpe, Alford, Folsom, Davidson, J. E. Smith, J. W. Hanson, Weekes,
  Stevens, Rotherham, Ballentine, Godbey, Worrell, Moulton, JPS 1917, Anderson,
  ABU, Noyes, Young (1862 and 1898), Darby, Julia Smith, Twentieth Century,
  Weymouth, Moffatt, Torrey (1933 — in copyright), CLV (1926+ — in copyright);
* **catalogued but not scripture text of their own** — Baxter's paraphrase,
  Whitby's paraphrase, Samuel Clarke's portions, the *Negro Slave Bible*
  (extracts), the *Hieroglyphick Bible* (extracts), the *Illuminated Bible*
  (edition, not a translation), *Shaw's Old Testament in Art*, the *Hexaplar
  Psalter*, *Metrical Psalms 1650*, *Psalms by Poets*, the *Bay Psalm Book*
  (metrical), the *Phonotypic* and *Phonetic* New Testaments (orthography
  experiments, not new translations), the *Pronouncing Edition*, *Commonly
  Received NT* (a KJV reprint), *The Modern Reader's Bible* (arrangement), the
  *Sinaitic Manuscripts NT* (a translation of Codex Sinaiticus — a manuscript
  edition), the *Yahwist Bible* portions, and the LXX/WEB/Brenton/LSV/Darby/
  Wycliffe modern derivatives flagged in the same list;
* **still in copyright in fact, whatever the field says** — Ferrar Fenton,
  Byington, Goodspeed (the `AAT` records here are the 1976 printing),
  Westminster, Kent's Shorter Bible, Torrey, CLV.

## Why nothing was ingested from DBS in this round

Every record with a **public-domain** flag points to a text already in the
dataset (or to a paraphrase/metrical/orthography item that is not a translation of
the running text). The records that *would* be new (`ENGTVB` Taverner's Bible,
`ENGCHE` John Cheke's Matthew) have no digital text behind them: DBS's only link
for `ENGTVB` is an Internet Archive **scan** of the 1539 printing
(`archive.org/download/ENGTVB_DBS_HS/…`), and scans are excluded by rule.
`dbs-prod`, `browserbible-bibles` and `cdn` were checked for raw text too:
`browserbible-bibles` ships only five bibles (KJV, WEB, OEB, SBLGNT, WLC) and
`cdn` is behind the same Cloudflare challenge.

So DBS's contribution here is **inventory, not text**: it independently confirms
which pre-1930 English editions have digital witnesses at all, and its
`copyright` / `copyright_type` fields are a second opinion on the licence notes in
`translations.csv`. Where a title in `PDF_ONLY_SOURCES.md` also appears here with
only a print link (Taverner, Cheke), the scan remains the only witness.

Recorded but not ingested for a later pass: `bible_equivalents.json` maps DBS ids
to YouVersion, Bible Brain, eBible and Davar ids — useful if more BFBS editions
are added the way `TEG` was (see `BIBLIATODO_SOURCES.md`).
