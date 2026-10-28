"""Publish the built dataset to GitHub as release assets.

Token handling: read from the GH_TOKEN environment variable only. Never written
to disk, never embedded in a git remote, never logged.

    GH_TOKEN=... python3 publish_github.py <owner/repo> <tag> <file> [<file> ...]

Release asset limit is 2 GB per file, so reference.parquet (~110 MB) and the
partition zip (~110 MB) both fit.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://api.github.com"


def req(url, token, method="GET", data=None, ctype="application/json"):
    r = urllib.request.Request(url, method=method, data=data)
    r.add_header("Authorization", "token " + token)
    r.add_header("Accept", "application/vnd.github+json")
    if data is not None:
        r.add_header("Content-Type", ctype)
    with urllib.request.urlopen(r, timeout=300) as fh:
        body = fh.read()
        return json.loads(body) if body else {}


def upload(url, token, path, name):
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        r = urllib.request.Request(url, method="POST", data=fh)
        r.add_header("Authorization", "token " + token)
        r.add_header("Content-Type", "application/octet-stream")
        r.add_header("Content-Length", str(size))
        with urllib.request.urlopen(r, timeout=1800) as resp:
            return json.loads(resp.read() or b"{}")


def main():
    token = os.environ.get("GH_TOKEN", "").strip()
    if not token:
        sys.exit("GH_TOKEN not set")
    repo, tag = sys.argv[1], sys.argv[2]
    files = sys.argv[3:]

    me = req(API + "/user", token)["login"]
    print("authenticated as", me)

    try:
        rel = req(f"{API}/repos/{repo}/releases/tags/{tag}", token)
        print("existing release", rel["id"])
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        body = json.dumps({
            "tag_name": tag,
            "name": "Public-domain Bible reference library (SWORD harvest)",
            "body": ("Public-domain / freely licensed Bible lexicons, dictionaries, "
                     "topical indexes and commentaries harvested from CrossWire SWORD "
                     "modules and normalised to plain text Parquet. See README.md in the "
                     "repository for schema, scope and provenance."),
            "draft": False,
            "prerelease": False,
        }).encode()
        rel = req(f"{API}/repos/{repo}/releases", token, "POST", body)
        print("created release", rel["id"])

    existing = {a["name"]: a for a in rel.get("assets", [])}
    base = rel["upload_url"].split("{")[0]
    for f in files:
        name = os.path.basename(f)
        if name in existing:
            print("skip existing", name)
            continue
        t0 = time.time()
        q = urllib.parse.urlencode({"name": name})
        asset = upload(base + "?" + q, token, f, name)
        print(f"uploaded {name} {os.path.getsize(f)/1e6:.1f} MB "
              f"({time.time()-t0:.0f}s) -> {asset.get('browser_download_url')}", flush=True)
    print("done")


if __name__ == "__main__":
    main()
