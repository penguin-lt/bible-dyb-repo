"""Classify every work against the coverage taxonomy, and report what is thin.

The suite asked for twenty coverage areas. Each work gets one primary area
(`topic`) and any number of secondary areas, then the script prints a coverage
matrix so gaps are visible rather than implied.

Sources of signal, in order: the source's own categories (Sefaria categories,
CCEL DC.Subject/LCSH, SWORD module type, dataset name), then title keywords.

    python3 taxonomy.py                 # matrix over the built manifest
    python3 taxonomy.py --apply         # write topic/secondary into sidecars
"""
import argparse
import json
import os
import re
import sys

OUT = os.environ.get("REF_OUT", "/home/user/scratch/out")

# the twenty areas, in the order the brief lists them
AREAS = [
    "Apocrypha & Pseudepigrapha",
    "Rabbinic Literature & Targums",
    "Patristics & Early Church Fathers",
    "Textual Criticism & Variants",
    "Systematic Theology & Dogmatics",
    "Sermons & Homiletics",
    "Church History & Historiography",
    "Liturgy & Lectionaries",
    "Historical & Cultural Background",
    "Maps & Geography",
    "Cross-Reference Systems",
    "Morphology & Parsing Data",
    "Interlinears & Reverse Interlinears",
    "Hermeneutics & Exegetical Methods",
    "Reformation & Early Modern Texts",
    "Creeds & Confessions",
    "Mysticism & Asceticism",
    "Archaeology & Epigraphy",
    "Apologetics & Polemics",
    "Lexical Datasets (Domain/Semantic)",
]

# keyword -> area.  Checked against source category, title and About text.
# areas are tried in order; a work keeps its first hit as primary, but
# "commentary" must win over the weaker "history" match that many titles carry
RULES = [
    ("Apocrypha & Pseudepigrapha",
     ("apocryph", "pseudepigraph", "enoch", "jubilees", "didache", "tobit", "judith",
      "maccabee", "esdras", "baruch", "testament of the twelve", "second temple",
      "josephus", "philo", "against apion")),
    ("Rabbinic Literature & Targums",
     ("talmud", "mishnah", "midrash", "tosefta", "targum", "rabbinic", "gemara",
      "halakhah", "responsa", "zohar", "tanakh", "rashi", "abarbanel", "mekhilta",
      "sifre", "sifra", "bereshit rabbah", "jerusalem talmud", "bavli")),
    ("Patristics & Early Church Fathers",
     ("patristic", "fathers", "ante-nicene", "nicene", "post-nicene", "apostolic",
      "chrysostom", "augustine", "athanasius", "origen", "tertullian", "irenaeus",
      "clement", "eusebius", "jerome", "cyril", "gregory", "basil", "ambrose",
      "early church", "christian literature, early", "apostolic fathers")),
    ("Textual Criticism & Variants",
     ("textual criticism", "variant", "apparatus", "manuscript", "codex",
      "tischendorf", "nestle", "sblgnt", "spurious passages", "criticism, textual",
      "lectionary evidence")),
    ("Systematic Theology & Dogmatics",
     ("systematic theology", "dogmatic", "theology", "doctrine", "institutes",
      "summa", "scholastic", "christology", "soteriology", "ecclesiology",
      "pneumatology", "ethics", "philosophy of religion")),
    ("Sermons & Homiletics",
     ("sermon", "homilet", "preaching", "discourse", "address", "lecture",
      "morning and evening", "sermons on")),
    ("Hermeneutics & Exegetical Methods",
     ("hermeneutic", "exegetic", "biblical interpretation", "interpretation of scripture",
      "how to read", "method of study", "sacred hermeneutics", "commentary",
      "exposition", "expositor", "annotation", "notes on", "critical and explanatory",
      "homiletic commentary", "inspiration and interpretation")),
    ("Church History & Historiography",
     ("church history", "history of the christian", "historiography", "reformation",
      "crusade", "missionary", "councils", "historia", "ecclesiastical history",
      "annals", "chronicle", "persecution", "martyrs")),
    ("Liturgy & Lectionaries",
     ("liturg", "worship", "hymn", "prayer book", "sacrament", "psalter",
      "menaion", "missal", "breviary", "collects", "rites", "eucharist",
      "daily light", "common prayer")),
    ("Historical & Cultural Background",
     ("antiquit", "customs", "manners", "archaeolog", "background", "social life",
      "daily life", "civilization", "geography of the bible", "usages")),
    ("Maps & Geography",
     ("geograph", "atlas", "map", "gazetteer", "place name", "pleiades",
      "topograph", "itinerary")),
    ("Cross-Reference Systems",
     ("cross-reference", "cross reference", "treasury of scripture knowledge",
      "chain", "concordance", "parallel passages", "harmony of the gospels",
      "quoting scripture")),
    ("Morphology & Parsing Data",
     ("morpholog", "parsing", "analytical lexicon", "morphhb", "tagging",
      "code expansion", "robinson", "packard")),
    ("Interlinears & Reverse Interlinears",
     ("interlinear", "reverse interlinear", "transliterat", "amalgamated",
      "tagged text", "ognt", "tagnt")),
    ("Reformation & Early Modern Texts",
     ("reformation", "luther", "calvin", "zwingli", "melanchthon", "puritan",
      "westminster", "hooker", "baxter", "edwards", "bunyan", "knox", "tyndale",
      "erasmus", "sixteenth century", "seventeenth century")),
    ("Creeds & Confessions",
     ("creed", "confession", "catechism", "articles of religion", "canons of dordt",
      "augsburg", "heidelberg", "helvetic", "westminster standards", "thirty-nine")),
    ("Mysticism & Asceticism",
     ("mystic", "ascetic", "contemplat", "kabbalah", "chasidut", "musar", "zohar",
      "dark night", "cloud of unknowing", "interior castle", "imitation of christ",
      "devotional", "piety", "meditation")),
    ("Archaeology & Epigraphy",
     ("archaeolog", "epigraph", "inscription", "ostraca", "papyri", "excavation",
      "monument", "seal", "tell el-amarna", "gezer")),
    ("Apologetics & Polemics",
     ("apologet", "polemic", "evidences of christianity", "against heresy",
      "defence of", "defense of", "controversy", "unbeliever", "atheis",
      "miracles", "reasonable religion")),
    ("Lexical Datasets (Domain/Semantic)",
     ("semantic domain", "sdbh", "lexical", "lexicon", "dictionary", "gloss",
      "bdb", "lsj", "strong", "thayer", "vocabulary", "wordbook", "glossary")),
]

# hard overrides by source, where the source knows better than keywords
SOURCE_DEFAULT = {
    "external:sefaria": "Rabbinic Literature & Targums",
    "external:dataset": None,
}
MODULE_TOPIC = {
    "XREF": "Cross-Reference Systems",
    "TEGMC": "Morphology & Parsing Data",
    "TEHMC": "Morphology & Parsing Data",
    "OHLEX": "Lexical Datasets (Domain/Semantic)",
    "PLEIA": "Maps & Geography",
    "LSJ": "Lexical Datasets (Domain/Semantic)",
    "BDB": "Lexical Datasets (Domain/Semantic)",
    "TBESG": "Lexical Datasets (Domain/Semantic)",
    "TBESH": "Lexical Datasets (Domain/Semantic)",
    "StrongsGreek": "Lexical Datasets (Domain/Semantic)",
    "StrongsHebrew": "Lexical Datasets (Domain/Semantic)",
    "VulgGlossa": "Rabbinic Literature & Targums",
    "VarApp": "Textual Criticism & Variants",
    "Spurious": "Textual Criticism & Variants",
    "TSK": "Cross-Reference Systems",
    "TCR": "Cross-Reference Systems",
    "Nave": "Cross-Reference Systems",
    "Torrey": "Cross-Reference Systems",
    "Scofield": "Cross-Reference Systems",
}


def blob(m):
    parts = [m.get("module_name", ""), m.get("about", ""), m.get("source_name", ""),
             m.get("topic", ""), m.get("categories", "") if isinstance(m.get("categories"), str)
             else " ".join(m.get("categories") or [])]
    return " ".join(parts).lower()


def areas_for(m):
    mid = m.get("module_id", "")
    hits = []
    if mid in MODULE_TOPIC:
        hits.append(MODULE_TOPIC[mid])
    b = blob(m)
    for area, keys in RULES:
        if any(k in b for k in keys):
            if area not in hits:
                hits.append(area)
    if not hits:
        # fall back on the source's own category before inventing one
        cat = (m.get("category") or "").lower()
        for area in ("Patristics & Early Church Fathers", "Commentary"):
            pass
        if "patristic" in cat:
            hits.append("Patristics & Early Church Fathers")
        elif "devotional" in cat:
            hits.append("Mysticism & Asceticism")
        elif "liturg" in cat:
            hits.append("Liturgy & Lectionaries")
        elif "sermon" in cat:
            hits.append("Sermons & Homiletics")
        elif "creed" in cat:
            hits.append("Creeds & Confessions")
        elif "theolog" in cat:
            hits.append("Systematic Theology & Dogmatics")
        elif "commentary" in cat or "reference" in cat:
            hits.append("Hermeneutics & Exegetical Methods"
                        if "hermeneutic" in b or "interpretation" in b
                        else ("Church History & Historiography"
                              if "histor" in b else "Systematic Theology & Dogmatics"))
        else:
            hits.append("Systematic Theology & Dogmatics")
    return hits[0], [h for h in hits[1:]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    sidecar = os.path.join(OUT, "manifests")
    rows = []
    for f in sorted(os.listdir(sidecar)):
        if not f.endswith(".json"):
            continue
        m = json.load(open(os.path.join(sidecar, f)))
        if m.get("status") != "ok":
            continue
        primary, secondary = areas_for(m)
        m["topic"] = primary
        m["topic_secondary"] = secondary
        rows.append(m)
        if a.apply:
            json.dump(m, open(os.path.join(sidecar, f), "w"), indent=1)

    counts = {x: [0, 0, 0] for x in AREAS}      # works, entries, chars
    for m in rows:
        for area in [m["topic"]] + m["topic_secondary"]:
            if area in counts:
                counts[area][0] += 1
                counts[area][1] += int(m.get("entry_count", 0))
                counts[area][2] += int(m.get("char_count", 0))
    print(f"{'area':42s} {'works':>6s} {'entries':>9s} {'Mchars':>9s}")
    for area in AREAS:
        w, e, c = counts[area]
        flag = "  <-- thin" if w < 5 else ""
        print(f"{area:42s} {w:6d} {e:9,d} {c/1e6:9.1f}{flag}")
    uncovered = [x for x in AREAS if counts[x][0] == 0]
    print()
    print(f"areas with no work: {len(uncovered)}"
          + (": " + ", ".join(uncovered) if uncovered else ""))
    if a.apply:
        print("applied to sidecars")


if __name__ == "__main__":
    main()
