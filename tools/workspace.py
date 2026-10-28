"""Operate on the GitHub repository as if it were the local workspace.

The repository is the workspace of record: every deliverable lives there.
The sandbox is only a build scratch area, and its filesystem is wiped between
sessions, so anything worth keeping is pushed here.

Credential handling: the token is read from $GH_TOKEN in the environment. It is
never written to disk, never put in a git remote, never committed.

Usage
-----
    export GH_TOKEN=...
    python3 tools/workspace.py ls [path]            # list a directory
    python3 tools/workspace.py cat <path>           # print a file
    python3 tools/workspace.py sync <path> [dest]   # download a file or directory
    python3 tools/workspace.py put <local> <path> [<local> <path> ...]
    python3 tools/workspace.py rm <path> [<path> ...]
    python3 tools/workspace.py stat                 # totals per top-level area

Environment: GH_REPO (default `penguin-lt/bible-dyb-repo`), GH_BRANCH (default `main`).
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
REPO = os.environ.get("GH_REPO", "penguin-lt/bible-dyb-repo")
BRANCH = os.environ.get("GH_BRANCH", "main")


def token():
    t = os.environ.get("GH_TOKEN", "").strip()
    if not t:
        sys.exit("GH_TOKEN is not set")
    return t


def api(path, method="GET", data=None, raw=False):
    url = path if path.startswith("http") else API + path
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
    r = urllib.request.Request(url, method=method, data=body)
    r.add_header("Authorization", "token " + token())
    r.add_header("Accept", "application/vnd.github+json")
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=600) as f:
            payload = f.read()
            return payload if raw else (json.loads(payload) if payload else {})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"{e.code} {e.reason}: {detail}")


def tree():
    """Every blob in the branch, as {path: entry}."""
    head = api(f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    t = api(f"/repos/{REPO}/git/trees/{head['object']['sha']}?recursive=1")
    return {x["path"]: x for x in t["tree"] if x["type"] == "blob"}


def blob(path):
    head = api(f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    t = api(f"/repos/{REPO}/git/trees/{head['object']['sha']}?recursive=1")
    for x in t["tree"]:
        if x["path"] == path and x["type"] == "blob":
            return api(f"/repos/{REPO}/git/blobs/{x['sha']}", raw=True)
    raise SystemExit(f"not found: {path}")


def head_commit():
    head = api(f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    return api(f"/repos/{REPO}/git/commits/{head['object']['sha']}")


def commit(files, message):
    """files: [(path, bytes)] — single commit via the trees API."""
    base = head_commit()
    entries = []
    for path, content in files:
        b = api(f"/repos/{REPO}/git/blobs", "POST",
                {"content": base64.b64encode(content).decode(), "encoding": "base64"})
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": b["sha"]})
    t = api(f"/repos/{REPO}/git/trees", "POST",
            {"base_tree": base["tree"]["sha"], "tree": entries})
    c = api(f"/repos/{REPO}/git/commits", "POST",
            {"message": message, "tree": t["sha"], "parents": [base["sha"]]})
    api(f"/repos/{REPO}/git/refs/heads/{BRANCH}", "PATCH", {"sha": c["sha"]})
    return c["sha"]


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def cmd_ls(args):
    prefix = (args[0].rstrip("/") + "/") if args else ""
    files = tree()
    if prefix and prefix not in files and not any(p.startswith(prefix) for p in files):
        if prefix[:-1] in files:
            print(prefix[:-1], human(files[prefix[:-1]]["size"]))
            return
        raise SystemExit("no such path: " + prefix)
    depth = prefix.count("/") + 1
    seen = {}
    for p, x in files.items():
        if not p.startswith(prefix):
            continue
        parts = p.split("/")
        if len(parts) == depth:
            print(f"{human(x['size']):>9}  {p}")
        else:
            seen["/".join(parts[:depth]) + "/"] = True
    for d in sorted(seen):
        n = sum(1 for p in files if p.startswith(d))
        print(f"{str(n) + ' files':>9}  {d}")


def cmd_cat(args):
    sys.stdout.write(blob(args[0]).decode("utf-8", "replace"))


def cmd_sync(args):
    path = args[0].rstrip("/")
    dest = args[1] if len(args) > 1 else os.path.basename(path)
    files = tree()
    targets = [p for p in files if p == path] or \
              [p for p in files if p.startswith(path + "/")]
    if not targets:
        raise SystemExit("no such path: " + path)
    total = 0
    for p in sorted(targets):
        rel = os.path.relpath(p, path) if len(targets) > 1 else os.path.basename(p)
        out = os.path.join(dest, rel) if len(targets) > 1 else dest
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        data = blob(p)
        with open(out, "wb") as fh:
            fh.write(data)
        total += len(data)
        print(f"{human(len(data)):>9}  {out}")
    print(f"synced {len(targets)} files, {human(total)}")


def cmd_put(args):
    pairs = list(zip(args[::2], args[1::2]))
    files = []
    for local, remote in pairs:
        with open(local, "rb") as fh:
            files.append((remote, fh.read()))
        print(f"{human(os.path.getsize(local)):>9}  {local} -> {remote}")
    sha = commit(files, "Update " + ", ".join(p for _, p in pairs[:4]) +
                 ("" if len(pairs) <= 4 else f" (+{len(pairs)-4} more)"))
    print("commit", sha)


def cmd_rm(args):
    files = [("", )]
    # deletions need a tree entry with a null sha
    base = head_commit()
    entries = [{"path": p, "mode": "100644", "type": "blob", "sha": None} for p in args]
    t = api(f"/repos/{REPO}/git/trees", "POST",
            {"base_tree": base["tree"]["sha"], "tree": entries})
    c = api(f"/repos/{REPO}/git/commits", "POST",
            {"message": "Remove " + ", ".join(args), "tree": t["sha"],
             "parents": [base["sha"]]})
    api(f"/repos/{REPO}/git/refs/heads/{BRANCH}", "PATCH", {"sha": c["sha"]})
    print("commit", c["sha"])


def cmd_stat(args):
    files = tree()
    areas = {}
    for p, x in files.items():
        top = p.split("/")[0]
        a = areas.setdefault(top, [0, 0])
        a[0] += 1
        a[1] += x["size"]
    for top, (n, size) in sorted(areas.items(), key=lambda kv: -kv[1][1]):
        print(f"{human(size):>10}  {n:5d} files  {top}")
    print(f"{human(sum(v[1] for v in areas.values())):>10}  "
          f"{len(files):5d} files  TOTAL")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    {"ls": cmd_ls, "cat": cmd_cat, "sync": cmd_sync, "put": cmd_put,
     "rm": cmd_rm, "stat": cmd_stat}[cmd](args)


if __name__ == "__main__":
    main()
