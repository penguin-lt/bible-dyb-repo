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
python3 sword_plan.py      # fetch mods.d.tar.gz + rawzip index, resolve licences -> /tmp/plan.json
python3 harvest.py         # per module: fetch zip, mod2imp dump, normalise, write Parquet
python3 combine.py         # combined reference.parquet, manifests, stats.json
python3 verify.py          # independent checks; non-zero exit on failure
```

Four works come from outside SWORD and are harvested by their own parser into
the same partition format:

```bash
python3 opensource_harvest.py --only LSJ,BDB,TBESG,TBESH
```
LSJ is ~24 MB and takes ~3 minutes; the other three are seconds.

`sword_plan.py` is the policy checkpoint: it reads every module's
`DistributionLicense` and emits `selected` / `skipped` lists. Change the policy
there, not in the harvester.

`harvest.py` is streaming — one module in memory at a time, and the zip, the
unpacked module and the dump are deleted as soon as its Parquet file is written,
so peak disk is roughly one module (the largest is ~40 MB) rather than 600 MB.
A full run is about 9 minutes for 96 modules.

Publishing the built dataset:

```bash
export GH_TOKEN=...        # repo scope
python3 publish_github.py penguin-lt/bible-dyb-repo bible-reference-v1 \
    /tmp/out/reference.parquet /tmp/out/reference_partitioned.zip /tmp/out/modules.parquet
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
