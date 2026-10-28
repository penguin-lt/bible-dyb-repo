"""Resolve the CrossWire SWORD module set we ingest.

Source of truth:  raw/mods.d.tar.gz  (every module .conf in the archive)
                  packages/rawzip/index  (every module zip that can be fetched)

Writes /tmp/plan.json:
    selected  — public-domain / explicitly-free, reference-class modules present in rawzip
    skipped   — same class but excluded, with the reason (licence, missing zip, empty shell)

Licence policy (same rule as the bibles dataset: public domain, or a licence that
permits redistribution): Public Domain, CC0, CC BY, CC BY-SA, GPL.  Everything
else — "Permission granted to CrossWire", non-commercial, NC/ND, or a blank
DistributionLicense that no Copyright line can redeem — is skipped and recorded.
"""
import glob
import io
import json
import os
import re
import subprocess
import tarfile

BASE = "https://www.crosswire.org/ftpmirror/pub/sword"
MODS_TAR = BASE + "/raw/mods.d.tar.gz"
RAWZIP = BASE + "/packages/rawzip/"
TMP = "/tmp"

REF_DRIVERS = {"zLD", "RawLD", "RawLD4", "zCom", "zCom4", "RawCom", "RawGenBook", "RawFiles"}
FREE_OK = {
    "Public Domain", "Creative Commons: CC0", "Creative Commons: BY 4.0",
    "Creative Commons: BY-SA 4.0", "GPL",
}
# distribution-licence strings that are free but worded differently
# NC / ND variants must NOT match: "BY" is followed by a non-commercial or
# no-derivatives clause that is not redistributable.
FREE_PAT = re.compile(r"^(public domain$|gpl$|creative commons: (cc0|by|by-sa)\\b(?!-nc|-nd))", re.I)


def fetch(url, path):
    subprocess.run(["curl", "-sS", "-m", "600", "-o", path, url], check=True)


def conf_fields(text):
    """Parse a SWORD .conf into a dict (multi-line values folded)."""
    meta, cur = {}, None
    for line in text.split("\n"):
        line = line.rstrip("\r")
        m = re.match(r"^([A-Za-z][A-Za-z0-9_]*)\s*=(.*)$", line)
        if m:
            k, v = m.group(1), m.group(2)
            if k.startswith("History_") or k.startswith("Lang_"):
                cur = None
                continue
            meta[k] = (meta[k] + " " + v).strip() if k in meta else v.strip()
            cur = k
        elif cur and line.strip() and not line.lstrip().startswith("#"):
            meta[cur] = (meta[cur] + " " + line.strip()).strip()
    return meta


def main():
    os.makedirs(TMP + "/mods", exist_ok=True)
    tar = TMP + "/mods.d.tar.gz"
    fetch(MODS_TAR, tar)
    with tarfile.open(tar) as tf:
        tf.extractall(TMP + "/mods")
    confs = glob.glob(TMP + "/mods/**/*.conf", recursive=True)
    idx = []
    for c in confs:
        text = open(c, encoding="utf-8", errors="replace").read()
        meta = conf_fields(text)
        # the real module name is the [Section] header, not the file name
        sec = re.search(r"(?m)^\s*\[([^\]]+)\]\s*$", text)
        if not meta.get("ModDrv"):
            continue
        idx.append({
            "file": os.path.basename(c),
            "path": c,
            "name": (sec.group(1).strip() if sec else os.path.basename(c)[:-5]),
            "moddrv": meta.get("ModDrv", ""),
            "lang": meta.get("Lang", ""),
            "dist": meta.get("DistributionLicense", ""),
            "desc": meta.get("Description", ""),
            "copyright": meta.get("Copyright", ""),
            "version": meta.get("Version", ""),
        })
    json.dump(idx, open(TMP + "/mods_index.json", "w"), indent=1)

    page = subprocess.run(["curl", "-sS", "-m", "300", RAWZIP],
                          capture_output=True, text=True, check=True).stdout
    zips = {z.lower(): z for z in re.findall(r'href="([^"]+)\.zip"', page)}
    zips = {k: v for k, v in zips.items()}
    with open(TMP + "/ziplist.txt", "w") as fh:
        fh.write("\n".join(sorted(zips.values())) + "\n")

    selected, skipped = [], []
    for m in idx:
        if m["moddrv"] not in REF_DRIVERS:
            continue
        free = m["dist"] in FREE_OK or bool(FREE_PAT.match(m["dist"] or ""))
        if not free:
            skipped.append({"module": m["name"], "reason": "licence: " + (m["dist"] or "blank"),
                            "desc": m["desc"], "lang": m["lang"]})
            continue
        z = zips.get(m["name"].lower())
        if not z:
            skipped.append({"module": m["name"], "reason": "not in crosswire rawzip",
                            "desc": m["desc"], "lang": m["lang"]})
            continue
        selected.append({"name": m["name"], "zip": z + ".zip", "lang": m["lang"],
                         "dist": m["dist"], "moddrv": m["moddrv"],
                         "desc": m["desc"], "version": m["version"]})
    json.dump({"selected": selected, "skipped": skipped},
              open(TMP + "/plan.json", "w"), indent=1)
    print(f"modules parsed {len(idx)} · zips {len(zips)} · "
          f"selected {len(selected)} · skipped {len(skipped)}")


if __name__ == "__main__":
    main()
