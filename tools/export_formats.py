#!/usr/bin/env python3
"""Export every SQLite Bible/edition to plain .txt and EPUB 3, streamed into zips.

Usage: python3 export_formats.py <sqlite_dir> <out_prefix>
Writes <out_prefix>.txt.zip and <out_prefix>.epub.zip next to out_prefix.

TXT layout: title block, then per book: banner + book name, "--- Chapter N ---",
"N verse text" lines.

EPUB: minimal valid EPUB 3 (mimetype stored first, container.xml, content.opf,
nav.xhtml, one xhtml per book). No external dependencies.
"""
import html
import io
import os
import re
import sqlite3
import sys
import zipfile


def load(db_path):
    d = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    tid, full, lang, edition, lic, sname, surl = d.execute(
        "select translation_id, translation_name, dialect, edition, license, source_name, source_url from translation"
    ).fetchone()
    books = {b[0]: b[1] for b in d.execute("select book_id, book_name from book")}
    verses = d.execute(
        "select v.book_id, v.chapter, v.verse, v.text from verse v "
        "join book b on b.book_id = v.book_id order by b.book_sort, v.chapter, v.verse"
    ).fetchall()
    d.close()
    return dict(id=tid, full=full, lang=lang or "en", edition=edition or "",
                license=lic or "", source_name=sname or "", source_url=surl or "",
                books=books, verses=verses)


def safe_filename(name):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return s or "text"


def build_txt(data):
    lines = [data["full"], f"({data['id']})"]
    if data["edition"]:
        lines.append(data["edition"])
    if data["license"]:
        lines.append(f"License: {data['license']}")
    if data["source_url"]:
        lines.append(f"Source: {data['source_url']}")
    lines.append("")
    cur_book = cur_chap = None
    for bid, ch, v, text in data["verses"]:
        if bid != cur_book:
            cur_book = bid
            title = data["books"].get(bid, bid)
            lines += ["", "=" * 60, title, "=" * 60]
        if ch != cur_chap:
            cur_chap = ch
            lines += ["", f"--- Chapter {ch} ---"]
        lines.append(f"{v}  {text}")
    return ("\n".join(lines) + "\n").encode("utf-8")


CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""


def build_epub(data):
    title = html.escape(data["full"])
    base = safe_filename(data["full"])
    items, files = [], {}
    cur = last_ch = None
    for bid, ch, v, text in data["verses"]:
        if bid != cur:
            if cur is not None:
                files[fname] += "</body></html>\n"
            cur = bid
            fname = f"{base}_{bid}.xhtml"
            label = data["books"].get(bid, bid)
            items.append((fname, label))
            files[fname] = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
                f"<title>{html.escape(label)}</title></head><body>\n"
                f"<h1>{html.escape(label)}</h1>\n"
            )
            last_ch = None
        if ch != last_ch:
            last_ch = ch
            files[fname] += f"<h2>Chapter {ch}</h2>\n"
        files[fname] += f'<p><span class="v">{v}</span> {html.escape(text)}</p>\n'
    if cur is not None:
        files[f"{base}_{cur}.xhtml"] += "</body></html>\n"

    manifest, spine = [], []
    nav = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
           f"<head><title>Contents</title></head><body><nav epub:type=\"toc\"><h1>{title}</h1><ol>\n")
    for i, (fname, label) in enumerate(items):
        manifest.append(f'<item id="t{i}" href="text/{fname}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="t{i}"/>')
        nav += f'<li><a href="text/{fname}">{html.escape(label)}</a></li>\n'
    nav += "</ol></nav></body></html>\n"
    manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')

    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid" version="3.0">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:identifier id="uid">urn:uuid:{html.escape(data["id"])}</dc:identifier>'
        f"<dc:title>{title}</dc:title>"
        f'<dc:language>{html.escape(data["lang"])}</dc:language>'
        f"<dc:publisher>{html.escape(data['source_name'])}</dc:publisher>"
        '<meta property="dcterms:modified">2026-11-03T00:00:00Z</meta>'
        "</metadata>\n"
        f'<manifest>{"".join(manifest)}</manifest>\n'
        f'<spine>{"".join(spine)}</spine>\n</package>\n'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/nav.xhtml", nav)
        for fname, content in files.items():
            z.writestr(f"OEBPS/text/{fname}", content, compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def main():
    src_dir, out_prefix = sys.argv[1], sys.argv[2]
    txt_zip = zipfile.ZipFile(out_prefix + ".txt.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6)
    epub_zip = zipfile.ZipFile(out_prefix + ".epub.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6)
    dbs = sorted(f for f in os.listdir(src_dir) if f.endswith(".sqlite3"))
    for i, db in enumerate(dbs, 1):
        data = load(os.path.join(src_dir, db))
        stem = safe_filename(data["full"])
        txt_zip.writestr(f"{stem}.txt", build_txt(data))
        epub_zip.writestr(f"{stem}.epub", build_epub(data))
        print(f"[{i}/{len(dbs)}] {stem}", flush=True)
    txt_zip.close()
    epub_zip.close()
    print("done")


if __name__ == "__main__":
    main()
