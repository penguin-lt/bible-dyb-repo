"""OSIS / TEI / HTML (SWORD module markup) -> plain reading text.

Shared by the lexicon / dictionary / commentary harvest.  The goal is the same
convention as the bibles dataset: plain reading text, no markup, no Strong's
tags, no notes.  Cross references are extracted separately (see refs.py) so
that removing the markup does not lose the reference data entirely.

No external dependencies: a tolerant tag scanner plus html.unescape.
"""
import re
import html

# tags whose content is *not* reading text
DROP_BLOCK = re.compile(
    r"<(note|rdg|app|w|seg|milestone|pb|cb|fw|index|revisionDesc|encodingDesc)\b.*?</\1\s*>",
    re.S | re.I)
DROP_SELF = re.compile(r"<(pb|cb|milestone|index|w|seg|div|lb)\b[^>]*/>", re.I)
BLOCK_TAGS = (
    "p|div|br|lb|title|head|item|l|lg|entryFree|entry|def|sense|tr|row|table"
    "|ul|ol|list|chapter|verse|hi|q|seg|ab|fig|table|caption|note|td|th"
)
TAG = re.compile(r"</?[a-zA-Z][^>]*>")
WS = re.compile(r"[ \t\r\f\v\u00a0\u2000-\u200b\u202f\u205f\u3000]+")
NL = re.compile(r"\n{3,}")
STRONG_LEAD = re.compile(r"^\{?[GH]?\d{0,5}\}?\s*")
PHON = re.compile(r"\(\s*[?\u00b7\u02b9\u02bc\u02c8\u00b4\u2018\u2019\ufffd\u2022\s]{1,4}\s*\)")


def _img_alt(m):
    alt = re.search(r'alt="([^"]*)"', m.group(0))
    return alt.group(1) if alt else ""


def clean(text, keep_linebreaks=True):
    """Strip markup from a SWORD entry body."""
    if not text:
        return ""
    t = text
    t = DROP_BLOCK.sub(" ", t)
    t = re.sub(r"<note\b.*?(/>|</note\s*>)", " ", t, flags=re.S | re.I)
    t = re.sub(r"<img\b[^>]*>", _img_alt, t)
    # structural line breaks before the generic strip
    t = re.sub(r"<(br|lb)\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</(p|div|title|head|item|l|lg|tr|sense|def|entryFree|entry|li|h[1-6])\s*>",
               "\n", t, flags=re.I)
    t = re.sub(r"<(div|p|title|head|item|tr|li|ul|ol|table|lg|list)\b[^>]*>",
               "\n", t, flags=re.I)
    t = TAG.sub("", t)
    t = html.unescape(t)
    t = t.replace("\u00ad", "")
    # Pronunciation placeholders: SWORD dictionaries (Webster, ISBE) carry the
    # original "(?)" or an undefined glyph where a phonetic transcription could
    # not be encoded.  They are typesetting noise, not reading text.
    t = PHON.sub("", t)
    t = t.replace("\ufffd", "")
    t = re.sub(r"(?m)^[\s,;:.\u2014\u2013-]+(?=\S)", "", t)   # placeholder left a dangling comma
    t = re.sub(r"\s+([,;.:])(?=\s|$)", r"\1", t)
    if not keep_linebreaks:
        t = re.sub(r"\s+", " ", t)      # flow text: collapse newlines too
        return t.strip()
    # normalise whitespace line by line, keep paragraph breaks
    lines = [WS.sub(" ", ln).strip() for ln in t.split("\n")]
    out = "\n".join(lines)
    return NL.sub("\n\n", out).strip()


def one_line(text, limit=None):
    t = clean(text, keep_linebreaks=False)
    t = re.sub(r"\s+", " ", t).strip(" ,;:-–—")
    if limit and len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "…"
    return t


def split_entry_blocks(raw, marker="$$$"):
    """Split a mod2imp dump into (key, body) pairs."""
    out = []
    cur_key = None
    buf = []
    for line in raw.split("\n"):
        if line.startswith(marker):
            if cur_key is not None:
                out.append((cur_key, "\n".join(buf)))
            cur_key = line[len(marker):]
            buf = []
        elif cur_key is not None:
            buf.append(line)
    if cur_key is not None:
        out.append((cur_key, "\n".join(buf)))
    return out
