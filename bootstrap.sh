#!/bin/sh
# Rebuild a working copy on a blank machine, from the repository alone.
#
# The repository is the workspace of record; the sandbox is disposable. Run this
# after any environment reset to get back to a state where the pipelines work.
#
#     export GH_TOKEN=...          # token with `repo` scope
#     sh bootstrap.sh              # repo -> sandbox
#
# What it does:
#   1. clones the repo
#   2. installs the tools the pipelines need (SWORD's mod2imp, unzip, pyarrow)
#   3. optionally pulls the reference-library release assets into /tmp
set -e
REPO="${GH_REPO:-penguin-lt/bible-dyb-repo}"
DEST="${1:-bible-db}"

echo "== clone $REPO -> $DEST"
if [ -d "$DEST/.git" ]; then
  git -C "$DEST" pull --ff-only
else
  git clone "https://github.com/$REPO.git" "$DEST"
fi
cd "$DEST"

echo "== python deps"
pip install -q pyarrow zstandard duckdb

echo "== sword tools (mod2imp for the module harvest)"
if ! command -v mod2imp >/dev/null 2>&1; then
  sudo -n apt-get install -y -q libsword-utils diatheke unzip curl zstd 2>/dev/null \
    || echo "  ! could not install; reference harvest needs mod2imp"
fi

echo "== sizes"
python3 tools/catalog.py | head -8

echo "== reference library assets (optional, 222 MB)"
REL="${REL:-bible-reference-v2}"
if [ "${SKIP_ASSETS:-0}" != "1" ]; then
  mkdir -p /tmp/refdata
  for f in reference.parquet reference_partitioned.zip modules.parquet; do
    [ -s "/tmp/refdata/$f" ] && continue
    curl -sSL -o "/tmp/refdata/$f" \
      "https://github.com/$REPO/releases/download/$REL/$f"
    echo "  /tmp/refdata/$f"
  done
else
  echo "  skipped (SKIP_ASSETS=1)"
fi

echo
echo "ready. examples:"
echo "  python3 tools/workspace.py stat"
echo "  python3 -c \"import duckdb; duckdb.sql(\\\"SELECT count(*) FROM 'bibles/text/bibles.parquet'\\\").show()\""
