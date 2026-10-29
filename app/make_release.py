#!/usr/bin/env python3
"""Package the bulk artefacts for GitHub Releases.

GitHub allows 2 GB per release asset and does not charge against the repo size,
so the big deliverables live here rather than in git. This script writes, into
an output directory:

  search.db.zst                  the core query database (verses + linked works)
  works.db.zst.part-NN           the whole reference corpus, split for download
  obs-offline-<ver>.zip          (--bundle only) the same two databases with the
                                 reader bundled, so one download runs with no setup
  *.sha256                       one checksum file listing everything

The split parts are plain byte ranges of the compressed stream, so

    cat works.db.zst.part-* | zstd -d > works.db

reassembles it with no tool of ours in the loop.

    python3 app/make_release.py --dir /tmp/rel --search-db search.db \\
        --works-db works.db --app app/
"""
import argparse
import hashlib
import os
import zipfile

import zstandard as zstd

CHUNK = 1 << 22


def compress(src, out, level=12):
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(src):
        print(f"  {os.path.basename(out)}: up to date")
        return out
    with open(src, "rb") as i, open(out, "wb") as o:
        zstd.ZstdCompressor(level=level, threads=2).copy_stream(i, o)
    print(f"  {os.path.basename(out)}  {os.path.getsize(out)/1e6:.1f} MB "
          f"from {os.path.getsize(src)/1e6:.0f} MB")
    return out


def split(path, outdir, part_size):
    """Split a file into fixed-size parts, newest-first cleanup of old parts."""
    base = os.path.basename(path)
    for f in os.listdir(outdir):
        if f.startswith(base + ".part-"):
            os.remove(os.path.join(outdir, f))
    total = os.path.getsize(path)
    n = (total + part_size - 1) // part_size
    with open(path, "rb") as f:
        for k in range(n):
            name = f"{base}.part-{k + 1:02d}"
            with open(os.path.join(outdir, name), "wb") as o:
                left = min(part_size, total - k * part_size)
                while left:
                    buf = f.read(min(CHUNK, left))
                    if not buf:
                        break
                    o.write(buf)
                    left -= len(buf)
            print(f"  {name}  {os.path.getsize(os.path.join(outdir, name))/1e6:.0f} MB")
    return [f"{base}.part-{k + 1:02d}" for k in range(n)]


def bundle(outdir, dbs, appdir, version):
    """One zip: the databases compressed as stored, plus the reader."""
    name = f"obs-offline-{version}.zip"
    path = os.path.join(outdir, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
        for src, label in dbs:
            z.write(src, label)
        for f in sorted(os.listdir(appdir)):
            if f.endswith(".py") or f.endswith(".md"):
                z.write(os.path.join(appdir, f), f"app/{f}")
        z.writestr("RUN.txt", RUN_TXT)
    print(f"  {name}  {os.path.getsize(path)/1e6:.0f} MB")
    return name


RUN_TXT = """Open Bible Study — offline bundle
=================================

You need Python 3.9 or newer. Nothing else: no pip install, no server, no account.

  tar/unzip this archive, then:

      cd <this folder>
      python3 app/app.py --db search.db.zst --works works.db.zst

The first run decompresses the two databases next to the compressed files
(about 6 GB of disk, once), then opens a browser on http://localhost:8080.

  search.db   verses in 97 translations, the work catalogue, 298,075
              verse-linked reference entries, 389,305 lexicon entries and
              29,126 interlinear rows.
  works.db    the whole 1,071,199-entry reference corpus, full-text searchable.

Drop --works to start with only the core database.

Everything in these databases is public domain or explicitly free-licensed, and
every panel in the app shows the licence of the work it quotes.
"""


def checksums(outdir, names):
    path = os.path.join(outdir, "SHA256SUMS.txt")
    with open(path, "w") as o:
        for n in sorted(names):
            h = hashlib.sha256()
            with open(os.path.join(outdir, n), "rb") as f:
                for buf in iter(lambda: f.read(CHUNK), b""):
                    h.update(buf)
            o.write(f"{h.hexdigest()}  {n}\n")
    print(f"  SHA256SUMS.txt  {len(names)} files")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--search-db", required=True)
    ap.add_argument("--works-db", required=True)
    ap.add_argument("--app", default=os.path.join(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--release", default="bible-search-rev1")
    ap.add_argument("--part-size", type=int, default=768 << 20)
    ap.add_argument("--bundle", action="store_true",
                    help="also zip the databases plus the app into one download. "
                         "Off by default: it duplicates ~1.8 GB of assets that are "
                         "already on the release.")
    a = ap.parse_args()
    os.makedirs(a.dir, exist_ok=True)

    print("compressing")
    sd = compress(a.search_db, os.path.join(a.dir, "search.db.zst"))
    wd = compress(a.works_db, os.path.join(a.dir, "works.db.zst"))
    print("splitting works.db")
    parts = split(wd, a.dir, a.part_size)
    names = [os.path.basename(sd)] + parts
    if a.bundle:
        print("bundling")
        names.append(bundle(a.dir, [(sd, "search.db.zst"), (wd, "works.db.zst")],
                            a.app, a.release))
    print("checksums")
    checksums(a.dir, names)


if __name__ == "__main__":
    main()
