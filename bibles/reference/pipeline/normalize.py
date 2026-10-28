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


NAMED_ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'",
                  "nbsp": " ", "mdash": "\u2014", "ndash": "\u2013",
                  "hellip": "\u2026", "lsquo": "\u2018", "rsquo": "\u2019",
                  "ldquo": "\u201c", "rdquo": "\u201d"}
ENTITY = re.compile(r"&(amp|lt|gt|quot|apos|nbsp|mdash|ndash|hellip|lsquo|rsquo|ldquo|rdquo);",
                    re.I)
NUMERIC_ENT = re.compile(r"&#(x?)([0-9a-fA-F]{2,6});")


def _charcode(hexflag, code):
    try:
        n = int(code, 16) if hexflag else int(code)
    except ValueError:
        return ""
    if n in (0x26, 0x3C, 0x3E, 0x22, 0x27):      # keep genuine ampersands etc as text
        return chr(n)
    if 0x20 <= n <= 0x10FFFF and not (0xD800 <= n <= 0xDFFF):
        return chr(n)
    return ""


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
    # Entities: unescape only the named ones we trust. html.unescape() also
    # eats things like "&lt;" inside already-escaped Greek, and leaves numeric
    # forms such as &#226; untouched; both showed up in the audit (MHC, Flavel).
    t = ENTITY.sub(lambda m: NAMED_ENTITIES.get(m.group(1).lower(), m.group(0)), t)
    # Sources double-escaped their ampersands (&#38;&#35;183; -> &#183;), so
    # repeat until nothing changes rather than once.
    for _ in range(3):
        if not NUMERIC_ENT.search(t):
            break
        t = NUMERIC_ENT.sub(lambda m: _charcode(m.group(1), m.group(2)), t)
    t = html.unescape(t)
    t = t.replace("\u00ad", "")
    # Editorial insertions from critical editions ("[[השמטה …]]", "[[see Rashi]")
    # are apparatus, not reading text, and were reaching the output from Sefaria.
    t = re.sub(r"\[\[[^\]]{0,600}\]\]?", " ", t)
    t = t.replace("[[", " ").replace("]]", " ")
    # Stray C0 control bytes survive in some OCR-era transcriptions upstream
    # (one 0x19 inside Rashba on Niddah); they are never part of the text.
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", t)
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
