#!/usr/bin/env python3
"""Open Bible Study — a free, local, Logos-style reader over the published corpus.

One Python file, standard library only. Serves a single-page app and a small JSON
API over `search.db` (verses + passage-linked works + lexicons + interlinears) and,
when present, `works.db` (the whole 1.07 M-entry reference corpus with full-text
search).

    python3 app.py --db search.db [--works works.db] [--port 8080]

Everything it reads is public domain or explicitly free-licensed; every panel
shows the licence of the work it quotes.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB = None
WDB = None


def open_db(path, tmpdir=None):
    """Open a SQLite file, decompressing a .zst or .gz on first use.

    The published databases are zstd-compressed release assets (search.db.zst is
    327 MB; decompressed it is 1.16 GB). Decompressing once into a cache and then
    serving from the plain file keeps startup fast on every later run.
    """
    if path.endswith(".zst") or path.endswith(".gz"):
        import gzip
        cache = (tmpdir or os.environ.get("OBS_CACHE")
                 or os.path.join(os.path.dirname(os.path.abspath(path)), ".obs-cache"))
        os.makedirs(cache, exist_ok=True)
        plain = os.path.join(cache, os.path.basename(path)[:-4])
        if not os.path.exists(plain):
            print(f"decompressing {path} -> {plain} (first run only)", flush=True)
            if path.endswith(".zst"):
                import zstandard
                with open(path, "rb") as i, open(plain, "wb") as o:
                    zstandard.ZstdDecompressor().copy_stream(i, o)
            else:
                with gzip.open(path, "rb") as i, open(plain, "wb") as o:
                    while True:
                        chunk = i.read(1 << 22)
                        if not chunk:
                            break
                        o.write(chunk)
        path = plain
    return conn(path)


def conn(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def q(sql, args=(), db=None):
    return [dict(r) for r in (db or DB).execute(sql, args)]


# ----------------------------------------------------------------- api routes
def api_meta():
    books = q("SELECT * FROM book ORDER BY book_order")
    trans = q("SELECT * FROM translation ORDER BY verses DESC")
    topics = q("SELECT topic, COUNT(*) works, SUM(entry_count) entries FROM work"
               " GROUP BY topic ORDER BY works DESC")
    counts = {r["k"]: r["v"] for r in q("SELECT k, v FROM note")}
    return {"books": books, "translations": trans, "topics": topics,
            "counts": counts, "works_db": WDB is not None}


def api_passage(book, ch, v, translations):
    ch = int(ch)
    v = int(v) if v else 0
    out = {"book": book, "chapter": ch, "verse": v, "translations": {}}
    if translations:
        rows = q("SELECT translation_id, verse, verse_end, verse_text FROM verse"
                 " WHERE book_id=? AND chapter=? AND translation_id IN (%s)"
                 " ORDER BY verse" % ",".join("?" * len(translations)),
                 (book, ch, *translations))
        for r in rows:
            out["translations"].setdefault(r["translation_id"], []).append(r)
    else:
        rows = q("SELECT translation_id, verse, verse_end, verse_text FROM verse"
                 " WHERE book_id=? AND chapter=? ORDER BY verse", (book, ch))
        for r in rows:
            out["translations"].setdefault(r["translation_id"], []).append(r)
    out["book_name"] = (q("SELECT book_name FROM book WHERE book_id=?", (book,))
                        or [{"book_name": book}])[0]["book_name"]
    return out


# OSIS/USFM book abbreviations used inside the reference works -> book_id
BOOKMAP = {
    "GEN": "GEN", "EXO": "EXO", "LEV": "LEV", "NUM": "NUM", "DEU": "DEU", "JOS": "JOS",
    "JDG": "JDG", "RUT": "RUT", "1SA": "1SA", "2SA": "2SA", "1KI": "1KI", "2KI": "2KI",
    "1CH": "1CH", "2CH": "2CH", "EZR": "EZR", "NEH": "NEH", "EST": "EST", "JOB": "JOB",
    "PSA": "PSA", "PS": "PSA", "PRO": "PRO", "ECC": "ECC", "SNG": "SNG", "ISA": "ISA",
    "JER": "JER", "LAM": "LAM", "EZK": "EZK", "EZE": "EZK", "DAN": "DAN", "HOS": "HOS",
    "JOL": "JOL", "AMO": "AMO", "OBA": "OBA", "JON": "JON", "MIC": "MIC", "NAM": "NAM",
    "HAB": "HAB", "ZEP": "ZEP", "HAG": "HAG", "ZEC": "ZEC", "MAL": "MAL", "MAT": "MAT",
    "MRK": "MRK", "MK": "MRK", "LUK": "LUK", "JHN": "JHN", "JN": "JHN", "ACT": "ACT",
    "ROM": "ROM", "1CO": "1CO", "2CO": "2CO", "GAL": "GAL", "EPH": "EPH", "PHP": "PHP",
    "COL": "COL", "1TH": "1TH", "2TH": "2TH", "1TI": "1TI", "2TI": "2TI", "TIT": "TIT",
    "PHM": "PHM", "HEB": "HEB", "JAS": "JAS", "JAM": "JAS", "1PE": "1PE", "2PE": "2PE",
    "1JN": "1JN", "2JN": "2JN", "3JN": "3JN", "JUD": "JUD", "JDE": "JUD", "REV": "REV",
}


def parse_ref(text):
    """'JHN.3.16' / 'Jhn 3:16' / 'PS.23.1' -> (book_id, chapter, verse) or None."""
    m = re.match(r"^\s*([1-3]?\s?[A-Za-z]{2,3})\.?\s*(\d{1,3})[:.]\s*(\d{1,3})", text or "")
    if not m:
        return None
    key = re.sub(r"[^A-Z0-9]", "", m.group(1).upper())
    bid = BOOKMAP.get(key)
    if not bid:
        return None
    return {"book_id": bid, "chapter": int(m.group(2)), "verse": int(m.group(3))}


def api_guide(book, ch, v):
    """The passage guide: everything in the database that touches this verse."""
    args = (book, int(ch), int(v))
    commentaries = q("""SELECT w.module_id, w.module_name, w.topic, w.license,
                               e.entry_key, e.entry_text
                        FROM entry e JOIN work w ON w.n = e.work_n
                        WHERE e.book_id=? AND e.chapter=? AND e.verse=?
                        ORDER BY w.module_name LIMIT 60""", args)
    # cross references stored as "JHN.3.16; ROM.5.8 (12)"
    xrefs = []
    for r in q("""SELECT e.entry_key, e.entry_text FROM entry e JOIN work w ON w.n=e.work_n
                  WHERE w.module_id IN ('TSK','XREF','Torrey','Nave')
                    AND e.book_id=? AND e.chapter=? AND e.verse=? LIMIT 5""", args):
        for chunk in re.findall(r"([1-3]?[A-Za-z]{2,3}[ .]\d+[:.]\d+)", r["entry_text"] or ""):
            if chunk not in xrefs:
                xrefs.append(chunk)
    interc = q("""SELECT w.module_id, w.module_name, i.body FROM interlinear i
                  JOIN work w ON w.n=i.work_n
                  WHERE i.book_id=? AND i.chapter=? AND i.verse=?""", args)
    # Strong's tags come from the verse-level Strong's datasets, not from the
    # interlinear text: the interlinear rows carry word/transliteration/gloss/
    # morphology, and the tags were deliberately kept out of that rendering.
    tags = []
    for r in q("""SELECT e.entry_text FROM entry e JOIN work w ON w.n=e.work_n
                  WHERE e.book_id=? AND e.chapter=? AND e.verse=?
                    AND w.module_id IN ('STRONGSGRK','STRONGSHEB')""", args):
        for tag in re.findall(r"\b([GH]\d{4}[A-Z]?)\b", r["entry_text"] or ""):
            if not tag.startswith(("H90", "H85", "G90")) and tag not in tags:
                tags.append(tag)
    seen, lexrows = set(), []
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        lexrows.extend(q("""SELECT w.module_id, l.head, l.strongs, substr(l.body,1,600) body
                            FROM lexicon l JOIN work w ON w.n=l.work_n
                            WHERE l.strongs=? LIMIT 4""", (tag,)))
        if len(seen) >= 25:
            break
    return {"commentaries": commentaries, "cross_references": xrefs[:40],
            "cross_ref_links": [parse_ref(x) for x in xrefs[:40]],
            "interlinear": interc, "lexicon": lexrows,
            "strongs": tags[:40]}


def api_search(term, scope="verses", translation="KJV", limit=60):
    term = (term or "").strip()
    if not term:
        return {"results": []}
    if scope == "verses":
        rows = q("""SELECT v.translation_id, v.book_id, b.book_name, v.chapter, v.verse,
                           highlight(verse_fts, 0, '<b>', '</b>') snippet, bm25(verse_fts) rank
                    FROM verse_fts JOIN verse v ON v.id = verse_fts.rowid
                    JOIN book b ON b.book_id = v.book_id
                    WHERE verse_fts MATCH ? AND v.translation_id = ?
                    ORDER BY rank LIMIT ?""", (fts_query(term), translation, limit))
        return {"results": rows, "scope": "verses"}
    if WDB is None:
        return {"results": [], "error": "works.db not installed"}
    rows = q("""SELECT w.module_id, w.module_name, w.topic, w.license,
                       e.entry_key, e.book_id, e.chapter, e.verse,
                       highlight(entry_fts, 1, '<b>', '</b>') snippet, bm25(entry_fts) rank
                FROM entry_fts JOIN entry e ON e.id = entry_fts.rowid
                JOIN work w ON w.n = e.work_n
                WHERE entry_fts MATCH ? ORDER BY rank LIMIT ?""",
             (fts_query(term), limit), db=WDB)
    return {"results": rows, "scope": "works"}


def api_lexicon(term):
    term = (term or "").strip()
    if not term:
        return {"entries": []}
    if re.match(r"^[GH]\d{1,5}", term.upper()):
        rows = q("""SELECT w.module_id, w.module_name, w.license, l.head, l.strongs,
                           substr(l.body,1,4000) body
                    FROM lexicon l JOIN work w ON w.n=l.work_n
                    WHERE l.strongs=? ORDER BY w.module_name""", (term.upper(),))
    else:
        rows = q("""SELECT w.module_id, w.module_name, w.license, l.head, l.strongs,
                           substr(l.body,1,4000) body
                    FROM lexicon l JOIN work w ON w.n=l.work_n
                    WHERE l.head LIKE ? ORDER BY length(l.head) LIMIT 40""",
                 (term + "%",))
    return {"entries": rows}


def api_works(topic="", term=""):
    sql = ("SELECT n, module_id, module_name, topic, language, license, entry_count,"
           " char_count FROM work")
    where, args = [], []
    if topic:
        where.append("topic = ?")
        args.append(topic)
    if term:
        where.append("module_name LIKE ?")
        args.append("%" + term + "%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY entry_count DESC LIMIT 500"
    return {"works": q(sql, args)}


def api_read(n, offset=0, limit=40):
    w = q("SELECT * FROM work WHERE n=?", (n,))
    if not w:
        return {"error": "no such work"}
    rows = q("""SELECT entry_key, book_id, chapter, verse, entry_text FROM entry
                WHERE work_n=? ORDER BY id LIMIT ? OFFSET ?""",
             (n, int(limit), int(offset)))
    total = q("SELECT COUNT(*) c FROM entry WHERE work_n=?", (n,))[0]["c"]
    return {"work": w[0], "entries": rows, "total": total,
            "offset": int(offset), "limit": int(limit)}


def fts_query(term):
    """Sanitise a user string into an FTS5 query: quoted tokens, AND'ed."""
    toks = re.findall(r'[\w\u0590-\u05ff\u0370-\u03ff]+', term)
    if not toks:
        return '""'
    return " AND ".join(f'"{t}"' for t in toks[:8])


# ------------------------------------------------------------------- routing
ROUTES = {
    "/api/meta": lambda p: api_meta(),
    "/api/passage": lambda p: api_passage(p.get("book", ["JHN"])[0], p.get("ch", ["3"])[0],
                                          p.get("v", ["0"])[0],
                                          [t for t in (p.get("t", [""])[0].split(",")) if t]),
    "/api/guide": lambda p: api_guide(p.get("book", ["JHN"])[0], p.get("ch", ["3"])[0],
                                      p.get("v", ["16"])[0]),
    "/api/search": lambda p: api_search(p.get("q", [""])[0], p.get("scope", ["verses"])[0],
                                        p.get("t", ["WEB"])[0], int(p.get("limit", ["60"])[0])),
    "/api/lexicon": lambda p: api_lexicon(p.get("q", [""])[0]),
    "/api/works": lambda p: api_works(p.get("topic", [""])[0], p.get("q", [""])[0]),
    "/api/read": lambda p: api_read(p.get("n", ["0"])[0], int(p.get("offset", ["0"])[0]),
                                    int(p.get("limit", ["40"])[0])),
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        if u.path == "/api/health":
            return self._send(200, json.dumps({"ok": True}))
        fn = ROUTES.get(u.path)
        if not fn:
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            self._send(200, json.dumps(fn(parse_qs(u.query)), ensure_ascii=False))
        except Exception as e:                      # never leak a stack to the UI
            self._send(500, json.dumps({"error": str(e)}))


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Open Bible Study</title>
<style>
:root{--bg:#fbfaf7;--ink:#1c1b19;--dim:#6b6862;--line:#e3ded4;--accent:#7a5c2e;
--panel:#fff;--hl:#fff3cf}
@media(prefers-color-scheme:dark){:root{--bg:#16171a;--ink:#e8e6e1;--dim:#9a978f;
--line:#2c2e33;--accent:#d9b26a;--panel:#1d1f23;--hl:#3a3320}}
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 Georgia,'Iowan Old Style',serif;background:var(--bg);color:var(--ink)}
header{display:flex;gap:14px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);
position:sticky;top:0;background:var(--bg);z-index:20;flex-wrap:wrap}
h1{font-size:17px;margin:0;font-weight:600;letter-spacing:.02em}
h1 span{color:var(--accent)}
nav{display:flex;gap:4px;margin-left:auto;flex-wrap:wrap}
nav button{font:inherit;font-size:14px;border:1px solid transparent;background:none;color:var(--dim);
padding:5px 11px;border-radius:7px;cursor:pointer}
nav button.on{background:var(--panel);border-color:var(--line);color:var(--ink)}
main{max-width:1180px;margin:0 auto;padding:18px 16px 80px}
.row{display:flex;gap:16px;align-items:flex-start}
.grid{display:grid;grid-template-columns:1fr 400px;gap:22px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
select,input[type=text]{font:inherit;font-size:14px;padding:6px 9px;border:1px solid var(--line);
border-radius:7px;background:var(--panel);color:var(--ink)}
input[type=text]{width:100%}
button.go{font:inherit;font-size:14px;padding:6px 14px;border-radius:7px;border:1px solid var(--accent);
background:var(--accent);color:#fff;cursor:pointer}
.verse{padding:5px 8px;border-radius:6px;cursor:pointer;display:flex;gap:9px}
.verse:hover{background:var(--panel)}
.verse.sel{background:var(--hl)}
.vn{color:var(--dim);font-size:12px;min-width:20px;text-align:right;padding-top:5px;
font-variant-numeric:tabular-nums}
.vt b{background:var(--hl);font-weight:600}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;
margin-bottom:14px}
.card h3{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.07em;
color:var(--dim);font-weight:600}
.entry{padding:8px 0;border-top:1px solid var(--line);font-size:14.5px}
.entry:first-of-type{border-top:0}
.entry .who{font-size:12px;color:var(--accent);font-family:system-ui,sans-serif;letter-spacing:.02em}
.entry .key{color:var(--dim);font-size:12px;font-family:system-ui,sans-serif}
.lic{font-size:11px;color:var(--dim);font-family:system-ui,sans-serif}
.small{font-size:13px;color:var(--dim)}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.tag{font:12px system-ui,sans-serif;border:1px solid var(--line);border-radius:99px;padding:2px 9px;
color:var(--dim);cursor:pointer;background:none}
.tag:hover{border-color:var(--accent);color:var(--accent)}
.pill{font:12px system-ui,sans-serif;background:var(--line);border-radius:99px;padding:2px 9px}
.hebd{font-family:'Ezra SIL','SBL Hebrew',serif;direction:rtl;unicode-bidi:embed;font-size:17px}
.grkd{font-family:'SBL Greek',Georgia,serif;font-size:16px}
.work{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-top:1px solid var(--line);
font-size:14.5px;cursor:pointer}
.work:hover{color:var(--accent)}
.hidden{display:none}
footer{padding:10px 2px;font:12px system-ui,sans-serif;color:var(--dim);
border-top:1px solid var(--line);margin-top:18px}
.spin{color:var(--dim);font-size:13px;padding:6px 0}
</style></head><body>
<header>
  <h1>Open <span>Bible</span> Study</h1>
  <nav>
    <button data-tab="read" class="on">Read</button>
    <button data-tab="study">Study</button>
    <button data-tab="search">Search</button>
    <button data-tab="library">Library</button>
  </nav>
</header>
<main>
  <section id="tab-read">
    <div class="row" style="margin-bottom:14px;gap:8px;flex-wrap:wrap">
      <select id="book"></select>
      <select id="chapter"></select>
      <select id="trans"></select>
      <button class="go" id="prev" title="Previous chapter">Prev</button>
      <button class="go" id="next" title="Next chapter">Next</button>
      <input type="text" id="refgo" placeholder="Go to reference — Jn 3:16, Ps 23, 1 Cor 13:4-7"
             style="max-width:330px">
    </div>
    <div class="grid">
      <div id="reader"></div>
      <div id="side"><div class="card"><h3>Passage guide</h3>
        <div class="small">Click a verse.</div></div></div>
    </div>
  </section>

  <section id="tab-study" class="hidden">
    <div class="card"><h3>Passage</h3><div id="study-head" class="small">Choose a verse in Read.</div></div>
    <div id="study-body"></div>
  </section>

  <section id="tab-search" class="hidden">
    <div class="row" style="gap:8px;margin-bottom:14px">
      <input type="text" id="q" placeholder="Search verses or the whole reference library…">
      <select id="scope"><option value="verses">Verses</option>
        <option value="works">Reference works</option></select>
      <select id="st"></select>
      <button class="go" id="doq">Search</button>
    </div>
    <div id="results"></div>
  </section>

  <section id="tab-library" class="hidden">
    <div class="row" style="gap:8px;margin-bottom:14px">
      <input type="text" id="lq" placeholder="Filter by title…">
      <select id="topic"><option value="">All topics</option></select>
    </div>
    <div id="library"></div>
  </section>
</main>
<footer id="foot">loading…</footer>
<script>
const $=s=>document.querySelector(s), esc=s=>(s==null?'':String(s)).replace(/[&<>"]/g,c=>
 ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const api=(p,q={})=>fetch(p+'?'+new URLSearchParams(q)).then(r=>r.json());
// AKJV/KJVA carry the KJV paragraph marks (¶) from the source text. The database is
// the archive of record, so they are stripped here, at display time only.
const clean=s=>(s==null?'':String(s)).replace(/\s*¶\s*/g,' ').replace(/\s{2,}/g,' ').trim();
let META,cur={book:'JHN',ch:3,tr:'WEB'},study=null;

function tab(t){document.querySelectorAll('main > section').forEach(s=>s.classList.add('hidden'));
  $('#tab-'+t).classList.remove('hidden');
  document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.tab===t));}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>tab(b.dataset.tab));

async function boot(){
  META=await api('/api/meta');
  const bg=$('#book'); META.books.forEach(b=>bg.insertAdjacentHTML('beforeend',
    `<option value="${b.book_id}">${esc(b.book_name)}</option>`));
  ['#trans','#st'].forEach(sel=>{const el=$(sel); META.translations.forEach(t=>
    el.insertAdjacentHTML('beforeend',`<option value="${t.translation_id}">${t.translation_id}</option>`));});
  $('#trans').value='WEB'; $('#st').value='WEB'; $('#st').classList.toggle('hidden',true);
  $('#topic').insertAdjacentHTML('beforeend', META.topics.map(t=>
    `<option value="${esc(t.topic)}">${esc(t.topic)} (${t.works})</option>`).join(''));
  $('#foot').textContent =
    `${(+META.counts.verses).toLocaleString()} verses · ${META.translations.length} translations · `+
    `${(+META.counts.works).toLocaleString()} reference works · ${(+META.counts.entries).toLocaleString()} entries`+
    (META.works_db?' · full-text library installed':' · install works.db for full-text search');
  bg.onchange=()=>{cur.book=bg.value;fillChapters();};
  $('#chapter').onchange=()=>{cur.ch=+$('#chapter').value;loadChapter();};
  $('#trans').onchange=()=>{cur.tr=$('#trans').value;loadChapter();};
  $('#prev').onclick=()=>{if(cur.ch>1){cur.ch--;loadChapter();}};
  $('#next').onclick=()=>{cur.ch++;loadChapter();};
  $('#refgo').onkeydown=e=>{if(e.key==='Enter')goRef($('#refgo').value);};
  $('#doq').onclick=doSearch; $('#q').onkeydown=e=>{if(e.key==='Enter')doSearch();};
  $('#scope').onchange=()=>$('#st').classList.toggle('hidden',$('#scope').value!=='verses');
  $('#topic').onchange=loadLibrary; $('#lq').oninput=loadLibrary;
  bg.value=cur.book;
  fillChapters();
  loadLibrary();
}
function fillChapters(){
  api('/api/passage',{book:cur.book,ch:1}).then(d=>{
    const max=Math.max(...Object.values(d.translations).flat().map(r=>r.verse),1);
    const sel=$('#chapter'); sel.innerHTML='';
    for(let i=1;i<=max;i++) sel.insertAdjacentHTML('beforeend',`<option value="${i}">${i}</option>`);
    sel.value=cur.ch<=max?cur.ch:1; cur.ch=+sel.value; loadChapter();
  });
}
async function loadChapter(){
  $('#reader').innerHTML='<div class="spin">loading…</div>';
  const d=await api('/api/passage',{book:cur.book,ch:cur.ch,t:cur.tr});
  const rows=(d.translations[cur.tr]||[]);
  $('#reader').innerHTML=`<div class="card"><h3>${esc(d.book_name)} ${cur.ch} · ${esc(cur.tr)}</h3>`+
    rows.map(r=>`<div class="verse" data-v="${r.verse}"><span class="vn">${r.verse}</span>
      <span class="vt">${esc(clean(r.verse_text))}</span></div>`).join('')+`</div>`;
  document.querySelectorAll('#reader .verse').forEach(el=>el.onclick=()=>{
    document.querySelectorAll('#reader .verse').forEach(x=>x.classList.remove('sel'));
    el.classList.add('sel'); openStudy(cur.book,cur.ch,+el.dataset.v);
    guide(cur.book,cur.ch,+el.dataset.v);});
}
async function guide(b,c,v){
  $('#side').innerHTML='<div class="card"><h3>Passage guide</h3><div class="spin">loading…</div></div>';
  const g=await api('/api/guide',{book:b,ch:c,v});
  let h=`<div class="card"><h3>${esc(META.books.find(x=>x.book_id===b)?.book_name||b)} ${c}:${v}</h3>`;
  h+=`<div class="tags">${g.strongs.slice(0,18).map(s=>`<span class="tag" onclick="lex('${s}')">${s}</span>`).join('')}</div>`;
  if(g.cross_references.length) h+=`<div style="margin-top:10px" class="small">Cross-references</div>
    <div class="tags">${g.cross_references.slice(0,24).map((x,i)=>{const l=(g.cross_ref_links||[])[i];
      return l?`<span class="tag" onclick="jump('${l.book_id}',${l.chapter},${l.verse})">${esc(x)}</span>`
              :`<span class="tag">${esc(x)}</span>`;}).join('')}</div>`;
  h+='</div>';
  h+=`<div class="card"><h3>Commentary &amp; notes (${g.commentaries.length})</h3>`+
    (g.commentaries.length?g.commentaries.map(c=>`<div class="entry"><div class="who">${esc(c.module_name)}
      <span class="lic">${esc(c.license)}</span></div>${esc((c.entry_text||'').slice(0,900))}</div>`).join('')
      :'<div class="small">No verse-linked commentary in the database for this verse.</div>')+'</div>';
  if(g.interlinear.length) h+=`<div class="card"><h3>Interlinear</h3>`+g.interlinear.map(i=>
    `<div class="entry"><div class="who">${esc(i.module_name)}</div><div class="hebd">${esc(i.body.slice(0,1200))}</div></div>`).join('')+'</div>';
  $('#side').innerHTML=h;
}
async function openStudy(b,c,v){
  study={b,c,v}; tab('study');
  $('#study-head').innerHTML=`${esc(META.books.find(x=>x.book_id===b)?.book_name||b)} ${c}:${v}`;
  $('#study-body').innerHTML='<div class="spin">loading…</div>';
  // KJV itself is not in this corpus; KJVA is the King James with Apocrypha and
  // AKJV the Authorised text. Offer whichever the corpus actually carries.
  const want=['WEB','AKJV','KJVA','ASVBT','YLT','DBY','RV1895'];
  const pick=want.filter(t=>META.translations.some(x=>x.translation_id===t)).slice(0,6);
  const p=await api('/api/passage',{book:b,ch:c,v,t:pick.join(',')});
  let h='<div class="card"><h3>Compare translations</h3>';
  for(const[tr,rows]of Object.entries(p.translations)){
    const row=rows.find(r=>r.verse===v); if(!row)continue;
    h+=`<div class="entry"><div class="who">${esc(tr)}</div>${esc(clean(row.verse_text))}</div>`;}
  h+='</div>';
  const g=await api('/api/guide',{book:b,ch:c,v});
  if(g.interlinear.length){
    h+='<div class="card"><h3>Original language</h3>'+g.interlinear.map(i=>
      `<div class="entry"><div class="who">${esc(i.module_name)} <span class="lic">${esc(i.license||'')}</span></div>
       <div class="hebd">${esc(i.body.slice(0,3000))}</div></div>`).join('')+'</div>';}
  if(g.lexicon.length){
    h+='<div class="card"><h3>Lexicon</h3>'+g.lexicon.map(l=>
      `<div class="entry"><div class="who">${esc(l.head)} — ${esc(l.module_id)}
        <span class="lic">${esc(l.license)}</span></div>${esc((l.body||'').slice(0,700))}</div>`).join('')+'</div>';}
  if(g.commentaries.length){
    h+='<div class="card"><h3>Commentary</h3>'+g.commentaries.map(c=>
      `<div class="entry"><div class="who">${esc(c.module_name)} <span class="key">${esc(c.entry_key)}</span>
        <span class="lic">${esc(c.license)}</span></div>${esc((c.entry_text||'').slice(0,2500))}</div>`).join('')+'</div>';}
  if(g.cross_references.length){
    h+='<div class="card"><h3>Cross-references</h3><div class="tags">'+
      g.cross_references.map((x,i)=>{const l=(g.cross_ref_links||[])[i];
        return l?`<span class="tag" onclick="jump('${l.book_id}',${l.chapter},${l.verse})">${esc(x)}</span>`
                :`<span class="tag">${esc(x)}</span>`;}).join('')+'</div></div>';}
  $('#study-body').innerHTML=h;
}
async function doSearch(){
  const term=$('#q').value.trim(); if(!term)return;
  const scope=$('#scope').value;
  $('#results').innerHTML='<div class="spin">searching…</div>';
  const d=await api('/api/search',{q:term,scope:scope,t:$('#st').value});
  if(d.error){$('#results').innerHTML=`<div class="card small">${esc(d.error)}</div>`;return;}
  if(!d.results.length){$('#results').innerHTML='<div class="card small">No results.</div>';return;}
  if(scope==='verses'){
    $('#results').innerHTML='<div class="card"><h3>'+d.results.length+' verses</h3>'+
      d.results.map(r=>`<div class="verse" onclick="jump('${r.book_id}',${r.chapter},${r.verse})">
        <span class="vn">${r.verse}</span><span class="vt"><b>${esc(r.book_name)} ${r.chapter}:${r.verse}</b>
        — ${r.snippet}</span></div>`).join('')+'</div>';
  }else{
    $('#results').innerHTML='<div class="card"><h3>'+d.results.length+' reference entries</h3>'+
      d.results.map(r=>`<div class="entry"><div class="who">${esc(r.module_name)}
        <span class="key">${esc(r.entry_key||'')}</span> <span class="lic">${esc(r.license)}</span></div>
        ${r.snippet}</div>`).join('')+'</div>';
  }
}
// Accepts "Jn 3:16", "John 3:16", "1 Cor 13:4-7", "Ps 23", "Gen 1".
// Book names are matched against the corpus's own list, so apocrypha work too.
function normTitle(s){return s.toLowerCase().replace(/\b(i{1,3}|iv|v|vi{0,3})\b/g,
  m=>({i:1,ii:2,iii:3,iv:4,v:5,vi:6,vii:7,viii:8,ix:9}[m]||m)).replace(/[^a-z0-9]/g,'');}
function goRef(text){
  const m=String(text).trim().match(/^\s*([1-3]?\s*[A-Za-z][A-Za-z.\s]*?)\s*(\d+)?\s*(?::\s*(\d+))?\s*$/);
  if(!m)return false;
  const want=[normTitle(m[1]), normTitle(m[1].replace(/\s+/g,''))];
  let best=null;
  for(const b of META.books){
    const cands=[normTitle(b.book_name), normTitle(b.book_id)];
    for(const c of cands){
      if(!c)continue;
      if(want.includes(c)||c.startsWith(want[0])||want[0].startsWith(c)){
        const score=(want.includes(c)?0:1)+(b.book_id.length);
        if(!best||score<best.score)best={b,score};}
    }
  }
  if(!best)return false;
  jump(best.b.book_id, m[2]?+m[2]:1, m[3]?+m[3]:0);
  return true;
}
function jump(b,c,v){cur.book=b;cur.ch=+c;$('#book').value=b;fillChapters();
  setTimeout(()=>{$('#chapter').value=c;cur.ch=+c;loadChapter();
    setTimeout(()=>{if(!v)return; const el=document.querySelector(`#reader .verse[data-v="${v}"]`);
      if(el){el.classList.add('sel');openStudy(b,+c,+v);guide(b,+c,+v);}},250);},200);tab('read');}
async function lex(t){tab('search');$('#q').value=t;$('#scope').value='verses';
  $('#results').innerHTML='<div class="spin">loading lexicon…</div>';
  const d=await api('/api/lexicon',{q:t});
  $('#results').innerHTML='<div class="card"><h3>'+esc(t)+' — '+d.entries.length+' entries</h3>'+
    d.entries.map(e=>`<div class="entry"><div class="who">${esc(e.head)} — ${esc(e.module_id)}
      <span class="lic">${esc(e.license)}</span></div><div class="grkd">${esc((e.body||'').slice(0,1200))}</div></div>`).join('')+'</div>';
}
async function loadLibrary(){
  const d=await api('/api/works',{topic:$('#topic').value,q:$('#lq').value});
  $('#library').innerHTML='<div class="card"><h3>'+d.works.length+' works</h3>'+
    d.works.map(w=>`<div class="work" onclick="readWork(${w.n})">
      <span>${esc(w.module_name)} <span class="lic">${esc(w.topic)} · ${esc(w.language)}</span></span>
      <span class="pill">${(+w.entry_count).toLocaleString()}</span></div>`).join('')+'</div>';
}
async function readWork(n){
  const d=await api('/api/read',{n:n,limit:40});
  if(d.error){alert(d.error);return;}
  $('#library').innerHTML=`<div class="card"><h3>${esc(d.work.module_name)}</h3>
    <div class="small">${esc(d.work.topic)} · ${esc(d.work.language)} · ${esc(d.work.license)} ·
    ${d.total.toLocaleString()} entries</div>
    <div style="margin:10px 0"><button class="go" onclick="loadLibrary()">← back to library</button></div>`+
    d.entries.map(e=>`<div class="entry"><div class="key">${esc(e.entry_key||'')}</div>
      <div class="${/[\u0590-\u05ff]/.test(e.entry_text)?'hebd':'vt'}">${esc((e.entry_text||'').slice(0,4000))}</div></div>`).join('')+
    `</div>`;
}
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='SELECT')return;
  if(e.key==='ArrowRight'){$('#next').click();} if(e.key==='ArrowLeft'){$('#prev').click();}});
boot();
</script></body></html>
"""


def main():
    global DB, WDB
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="search.db")
    ap.add_argument("--works", default="")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--cache", default="",
                    help="where to decompress .zst databases (default .obs-cache)")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        raise SystemExit(f"{a.db} not found — download it (see app/README.md) "
                         "or build it with build_searchdb.py")
    DB = open_db(a.db, a.cache)
    if a.works and os.path.exists(a.works):
        WDB = open_db(a.works, a.cache)
    print(f"Open Bible Study on http://{a.host}:{a.port}  db={a.db}"
          f"{'  works=' + a.works if WDB else '  (no works.db: verse-only search)'}")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
