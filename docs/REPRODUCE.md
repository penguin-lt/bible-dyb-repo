# Reproducing the database

Two independent pipelines, one per dataset. Both are idempotent, both verify
themselves, and neither needs the repository checked out — they write into a
scratch directory and the result is pushed as a release asset.

## Verse corpus (`bibles/text/`)

`bibles/text/pipeline/` holds the build history: one script per accepted
addition (`add_*_addition_rev*.py`), the fetchers, the source caches and the
research inventories. The final revision script rebuilds the whole dataset:

```bash
cd bibles/text/pipeline
python3 add_bibliatodo_addition_rev7.py
```

It rewrites `bibles.parquet`, `bibles_partitioned/`, `translations.parquet/.csv`,
`books.parquet/.csv` and `stats_v7.json`, then prints the swap report.
Original module sources (`.SQLite3`, `.gz`) live in `pipeline/sources/`;
`pipeline/sources/unpack.py` expands them.

**Memory note:** the build sets `memory_limit='400MB'`,
`preserve_insertion_order=false` and `threads=1` in its DuckDB connection.
Without those three, the rewrite is OOM-killed on a 2 GB box.

## Reference library (`bibles/reference/`)

```bash
sudo apt-get install -y libsword-utils diatheke unzip curl
pip install pyarrow zstandard

cd bibles/reference/pipeline
python3 sword_plan.py      # fetch mods.d.tar.gz + rawzip index, resolve licences -> plan.json
python3 harvest.py         # per module: fetch zip, mod2imp dump, normalise, write Parquet
python3 ccel_harvest.py --include-unstated   # 1,331 CCEL works -> 741 ingested (~40 min)
python3 sefaria_harvest.py                   # 19,815 Sefaria texts -> 1,282 ingested (~2 h)
python3 datasets_harvest.py                  # XREF, TEGMC, TEHMC, OHLEX, PLEIA
python3 opensource_harvest.py --only LSJ,BDB,TBESG,TBESH
python3 repair.py --apply  # licence canonicalisation + enforcement, empty rows,
                           # duplicate-key requalification   <-- do not skip
python3 dedupe.py --apply  # exact-text duplicates only; same-work pairs are reported
python3 taxonomy.py --apply # classify every work against the twenty subject areas
python3 combine.py         # combined reference.parquet, manifests, stats.json
python3 verify.py          # independent checks; non-zero exit on failure
```

The order matters. `repair.py` runs **before** `combine.py` because it may
reject a whole work on licence grounds — 112 works were removed this way — and
because `combine.py` must never have to make a licence decision. `dedupe.py`
runs after it for the same reason: do not delete a work, then discover its
neighbour was the duplicate.

### The sidecar manifest

Each harvester writes one JSON file per work to `$REF_OUT/manifests/<module_id>.json`
and nothing shared. An early design had all four harvesters appending to a single
`modules.json`; run in parallel they overwrote each other and 1,388 works ended up
in the data with no manifest row. The sidecar is the unit of truth: `combine.py`
assembles `modules.parquet` / `.csv` / `stats.json` from the directory, and a
partition without a sidecar is an error, not a default.

### The licence gate

`repair.py` is the only place allowed to decide whether a licence string is
permitted. Its canonical set is `Public Domain`, `CC0`, `CC BY`, `CC BY-SA`,
`GPL`; everything else is rejected and the work is moved to
`$REF_OUT/not_ingested/` with the reason recorded. Substring tests are unsafe in
both directions and have caused two leaks: `"cc-by" in s` is true for
`cc-by-nc` (102 Sefaria texts), and a naive "contains BY" pattern rejects
`Creative Commons: BY 4.0`. `canonical()` therefore matches an ordered list of
regexes with `(?!-nc|-nd)` lookaheads, and `verify.py` calls the same function
rather than re-implementing the test.

`license_raw` preserves the distributor's own wording; `license` is the canonical
value and `license_basis` is `stated` or `inferred_pre1929`.

Publishing the built dataset:

```bash
export GH_TOKEN=...        # repo scope
python3 publish_github.py penguin-lt/bible-dyb-repo bible-reference-v3 \
    $REF_OUT/reference.parquet /tmp/out/reference_partitioned.zip /tmp/out/modules.parquet
```

## Adding a work that is not a SWORD module

Done for four works, and the pattern generalises: `opensource_harvest.py` holds a
`SOURCES` dict of URL/licence metadata plus a row parser, and writes the same
ten-column partition the SWORD harvester writes, so `combine.py` and `verify.py`
pick it up with no special-casing. To add another, append a `SOURCES` entry, a
parser, and a `PARSERS` mapping.

One trap worth repeating: the Perseus `grc.lsj.perseus-eng1.xml` is the
**alpha-only** fascicle despite the filename — 18,586 of its 18,950 headwords
start with alpha. Always check a lexicon's key distribution before trusting its
name.

## Verification contract

Any rebuild must pass `verify.py` — counts agreeing across combined file,
partitions and manifest; no empty or null text; no duplicate `(module, key)`
pairs; no U+FFFD; no residual markup; spot checks of known headwords; and no
`Copyrighted…` licence in the output. The bibles build has the equivalent checks
recorded in `bibles/text/QA_REPORT.md`.
