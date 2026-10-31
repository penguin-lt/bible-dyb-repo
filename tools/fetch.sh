#!/bin/bash
# Fetch every source the critical-editions build needs.
#
# All sources are public domain. Two are public-domain text with a modern
# transcription under a copyleft licence, noted below.
set -euo pipefail
RAW=/home/user/work/ed/raw
WH=$RAW/wh
mkdir -p "$RAW" "$WH"

# ---- eBible.org USFM (public domain) ----
for id in grcbyz grcmt grcsr grctcgnt grctr grc-tisch grclxx grcbrent \
          hbo hboWLC copbhc copcnt latVUC; do
  if [ ! -d "$RAW/$id" ]; then
    curl -s -o "/tmp/$id.zip" -L "https://ebible.org/Scriptures/${id}_usfm.zip"
    mkdir -p "$RAW/$id"
    unzip -q -o "/tmp/$id.zip" -d "$RAW/$id"
    rm -f "/tmp/$id.zip"
  fi
done

# ---- Westcott & Hort 1881, byztxt beta code (public domain) ----
if [ ! -d "$WH" ] || [ -z "$(ls -A "$WH" 2>/dev/null)" ]; then
  mkdir -p "$WH"
  curl -s "https://api.github.com/repos/byztxt/greektext-westcott-hort/git/trees/master?recursive=1" \
    | python3 -c 'import json,sys
for t in json.load(sys.stdin)["tree"]:
    if t["path"].startswith("textonly/") and t["path"].endswith(".WH"): print(t["path"])' > /tmp/whfiles.txt
  while read -r f; do
    curl -sL -o "$WH/$(basename "$f")" \
      "https://raw.githubusercontent.com/byztxt/greektext-westcott-hort/master/$f"
  done < /tmp/whfiles.txt
fi

# ---- Nestle 1904, one row per word. Morphology released CC0; the underlying
#      1904 text is public domain. ----
mkdir -p "$RAW/nestle"
[ -f "$RAW/nestle/nestle1904.csv" ] || curl -sL -o "$RAW/nestle/nestle1904.csv" \
  "https://raw.githubusercontent.com/biblicalhumanities/Nestle1904/master/morph/Nestle1904.csv"

# ---- Sahidic Coptic (Horner 1911), SWORD module. DistributionLicense=Public Domain ----
if [ ! -d "$RAW/sahidic/modules" ]; then
  mkdir -p "$RAW/sahidic"
  curl -sL -o /tmp/CopSahHorner.zip \
    "https://www.crosswire.org/ftpmirror/pub/sword/packages/rawzip/CopSahHorner.zip"
  unzip -q -o /tmp/CopSahHorner.zip -d "$RAW/sahidic"
  rm -f /tmp/CopSahHorner.zip
fi

# ---- Letteris 1866. The 1866 text is public domain; this transcription by
#      Avraham BenEmanuel is GPL-3.0, which is why the file records both. ----
if [ ! -d "$RAW/letteris" ]; then
  mkdir -p "$RAW/letteris"
  curl -s "https://api.github.com/repos/benemanuel/letteris/git/trees/master?recursive=1" \
    | python3 -c 'import json,sys
for t in json.load(sys.stdin)["tree"]:
    if t["path"].endswith(".utf8_txt"): print(t["path"])' > /tmp/letteris.txt
  while read -r f; do
    enc=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$f")
    curl -sL -o "$RAW/letteris/$(basename "$f")" \
      "https://raw.githubusercontent.com/benemanuel/letteris/master/$enc"
  done < /tmp/letteris.txt
  # unvocalised duplicate files, editor notes and stray copies are not sources
  rm -f "$RAW/letteris/Editornotes.utf8_txt" "$RAW/letteris/letteris.utf8_txt" \
        "$RAW/letteris/wlc_utf8.utf8_txt" "$RAW/letteris"/*_hebrew.utf8_txt
fi

echo "sources ready under $RAW"
du -sh "$RAW"
