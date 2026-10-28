# QA report — dataset revision 7 (build of 2026-10-28)

Translations: **77** (76 from revision 6 + the addition below); total verses: **1,577,225**. This revision takes in the English catalogue of bibliatodo.com (via the same British & Foreign Bible Society editions on bible.com, because bibliatodo is behind a Cloudflare challenge) and adds the one title that was neither present nor derived from a present one. See `BIBLIATODO_SOURCES.md` and `DBS_SOURCES.md`.

## Addition

| id | translation | year | verses | closest existing (normalised identical %) |
|---|---|---|---:|---|
| TEG | Tegid Isaiah (John Jones, from the Hebrew) | 1830 | 1,292 | KJVA 5.3% |

Tegid's Isaiah is a new witness, not a respelling: the closest Isaiah in the dataset (KJVA) shares 5.3 % of verses word-identically.

## Verification

- combined rows = manifest verse-count sum = 1,577,225; translations = 77
- null/empty verse_text: 0; duplicate keys: 0
- John 1:1 present in 67 translations; distinct book codes: 87
- scraped from verse-segmented HTML (`data-usfm` verse ids), no OCR, no retyping.

## Source sweeps behind this revision

**bibliatodo.com** — English catalogue read in full (the site itself answers only
with a Cloudflare challenge, so the texts were taken from the same British &
Foreign Bible Society editions on bible.com). One addition: `TEG` (John Jones /
Ioan Tegid, Isaiah 1830/1842). Per-version disposition: `BIBLIATODO_SOURCES.md`.
Held out on licensing, not quality: *St Paul from the Trenches 1916* (G. Warre
Cornish) — first published 1937, © BFBS 2014.

**arc.dbs.org / digitalbiblesociety/data** — the scripture dataset (6,829
publications, 241 English records, 129 flagged public domain) is an inventory, not text:
every public-domain record points at a translation already in the dataset or at a
paraphrase/metrical/orthography item. Taverner's Bible and Cheke's Matthew are
listed but have only page scans behind them. Details: `DBS_SOURCES.md`. The clone
was read for inventory only and is not kept in the workspace.

## Per-translation counts

| id | verses | books | chapters |
|---|---:|---:|---:|
| ABU1865 | 7,953 | 27 | 260 |
| ACV | 31,102 | 66 | 1189 |
| AKJV | 31,102 | 66 | 1189 |
| Anderson | 7,946 | 27 | 260 |
| ASV | 31,086 | 66 | 1189 |
| ASVBT | 37,761 | 84 | 1405 |
| BBE | 31,102 | 66 | 1189 |
| BISHOPS | 31,102 | 66 | 1189 |
| BLB | 7,941 | 27 | 260 |
| Brenton | 28,690 | 53 | 1116 |
| BSB | 31,086 | 66 | 1189 |
| Coverdale | 31,089 | 66 | 1189 |
| CPDV | 35,812 | 73 | 1334 |
| DBY | 31,099 | 66 | 1189 |
| DIAGLOTT | 7,910 | 27 | 260 |
| DRA | 35,811 | 73 | 1334 |
| E2T | 47 | 1 | 4 |
| Etheridge | 7,940 | 27 | 260 |
| F35 | 7,953 | 27 | 260 |
| FBV | 31,087 | 66 | 1189 |
| GHT | 7,956 | 27 | 260 |
| GNV1560 | 31,102 | 66 | 1189 |
| GNV1599 | 31,090 | 66 | 1189 |
| Godbey | 7,913 | 27 | 260 |
| GREAT | 31,095 | 66 | 1189 |
| HAWEIS | 7,957 | 27 | 260 |
| JPS1917 | 23,145 | 39 | 929 |
| JST | 30,829 | 65 | 1181 |
| KJV1611 | 31,102 | 66 | 1189 |
| KJVA | 36,822 | 80 | 1362 |
| Leeser | 23,143 | 39 | 929 |
| LIVINGORACLES | 7,955 | 27 | 260 |
| LSV | 31,104 | 66 | 1189 |
| LXX2012 | 28,324 | 54 | 1105 |
| LXXUP | 28,349 | 52 | 1104 |
| MACE | 7,957 | 27 | 260 |
| Matthew | 31,092 | 66 | 1189 |
| MOFFATT | 7,940 | 27 | 260 |
| MONTGOMERY | 7,927 | 27 | 260 |
| MSB | 31,098 | 66 | 1189 |
| Murdock | 7,947 | 27 | 260 |
| NHEB | 31,097 | 66 | 1189 |
| Noyes | 18,213 | 49 | 753 |
| OEBUS | 13,894 | 44 | 565 |
| OJB | 31,165 | 66 | 1189 |
| OnkelosETHERIDGE | 5,848 | 5 | 187 |
| OTTLEY | 1,286 | 1 | 66 |
| OURB | 15,230 | 14 | 540 |
| PANIN | 7,937 | 27 | 260 |
| PEV | 7,374 | 30 | 299 |
| RIVERSIDE | 7,932 | 27 | 260 |
| RKJNT | 7,956 | 27 | 260 |
| RNKJV | 31,102 | 66 | 1189 |
| Rotherham | 31,086 | 66 | 1189 |
| RV1895 | 36,836 | 80 | 1362 |
| SAWYER | 7,957 | 27 | 260 |
| SLT | 31,102 | 66 | 1189 |
| T4T | 30,640 | 66 | 1189 |
| TCENT | 7,954 | 27 | 260 |
| TCNT | 7,940 | 27 | 260 |
| TEG | 1,292 | 1 | 66 |
| THOMSON | 3,599 | 11 | 135 |
| TNT | 7,954 | 27 | 260 |
| Tyndale | 13,852 | 33 | 451 |
| UKJV | 31,102 | 66 | 1189 |
| ULT | 31,103 | 66 | 1189 |
| UST | 30,975 | 66 | 1189 |
| WEB | 38,029 | 81 | 1402 |
| Webster | 31,102 | 66 | 1189 |
| Wesley | 7,957 | 27 | 260 |
| Weymouth | 7,957 | 27 | 260 |
| WHISTON | 7,957 | 27 | 260 |
| WMB | 31,098 | 66 | 1189 |
| Worrell | 7,946 | 27 | 260 |
| Worsley | 7,958 | 27 | 260 |
| WYCLIFFE | 36,227 | 76 | 1345 |
| YLT | 31,102 | 66 | 1189 |
