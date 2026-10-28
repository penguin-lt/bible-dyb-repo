# QA report

Independent verification of the current build. `pipeline/verify.py` is the
executable form of this report; it exits non-zero on any hard failure.

## Result: ALL CHECKS PASSED

```
PASS combined schema  [module_id, module_name, category, entry_key, entry_order,
                       book_id, chapter, verse, entry_text, char_count]
PASS module count / partition count  [9,141 modules, 9,141 partitions]
PASS manifest and partition module sets agree
PASS partitions sum to combined row count  [1,073,530 rows]
PASS manifest entry_count sum matches  [1,073,530]
PASS no empty entry text  [0]
PASS no null keys or texts  [0]
PASS no duplicate (module, key) pairs  [0 across 0 modules]
PASS scripture-linked entries parsed  [210,522]
PASS no copyrighted-only licences in the dataset
PASS spot LSJ:G0026  [love]
PASS spot BDB:אָבַד  [perish]
PASS spot TBESG:G0001G  [alpha]
PASS spot TBESH:H0001G  [father]
PASS spot Easton:AARON  [Amram]
PASS spot Smith:AARON  [Amram]
PASS spot StrongsGreek:00001  [alpha]
PASS spot Nave:AARON  [Lineage]
PASS spot Torrey:ACCESS TO GOD  [Christ]
PASS spot MHC:Genesis 1:1  [beginning]
PASS spot Webster1913:AARON'S ROD  [serpent]
PASS spot ISBE:AARON  [Amram]
PASS no U+FFFD replacement characters  [0]
PASS no residual markup in sample

modules=9,141 entries=1,073,530 chars=2,369,741,291
combined=787.0 MB partitions=793.0 MB
RESULT: ALL CHECKS PASSED
```

## What each check actually proves

| check | method |
|---|---|
| schema | the combined file and every partition are opened separately and their Arrow schemas compared against the documented ten columns |
| counts | row counts from Parquet metadata (not from the build's own bookkeeping) are summed across partitions and compared with the combined file and with `entry_count` in the manifest |
| emptiness / nulls | `utf8_trim_whitespace` and null counts over every row of every partition |
| duplicate keys | full per-module key histogram — after the de-duplication fix this is zero |
| scripture linkage | `book_id` non-null counts, 210,522 entries |
| licences | manifest licence tally re-derived and asserted free of `Copyrighted…` values |
| content spot checks | eight known headwords looked up by key and matched against a word that must appear in the entry |
| encoding | scan of every `entry_text` for U+FFFD replacement characters |
| markup | sample scan for residual angle-bracket markup |

## Defects found and fixed during QA

1. **Broken de-duplicator.** The first build emitted 9 duplicate
   `(module_id, entry_key)` pairs in `Smith` and `VieStrongsGreek`
   (`ADAM (3)`, `0920 (3)`), because the counter that qualifies repeated keys
   read from the same dict it was writing to. Replaced with a simple
   probe-until-free loop; re-verified at zero.
2. **CC BY-NC-ND modules leaked in.** The licence regex
   `creative commons: (cc0|by|by-sa)` matched the `BY` prefix of `BY-NC-ND`,
   letting `GerStrongsGreek` and `SloHenoh` (non-commercial, no-derivatives) into
   an earlier module plan. Tightened with a negative lookahead; both are now
   excluded and listed in `modules_excluded.csv`.
3. **Webster's 1913 pronunciation placeholders.** The source marks a phonetic
   transcription that could not be encoded as `(?)` or as an undefined glyph.
   These were surviving as `?), n. A kind of timber truck…` in 15,957 entries.
   Stripped in `normalize.py` (placeholder, then any dangling punctuation), with
   a whole-corpus scan for U+FFFD added to the verifier. This is the only
   content change between the 615,459-row build and its predecessor: same rows,
   cleaner text (387,289,451 chars vs 388,870,469).
4. **Headword repeated at the start of the entry.** TEI entries begin with a
   `<title>` carrying the headword, so `AARON` read `Aaron\n\nThe eldest son…`.
   `strip_headword` now removes that repeat, tolerating a trailing accent, quote
   or degree mark (`Padreʹ`, `AARON'S ROD`).
5. **Latin-1 module broke the harvest.** `Smith` (and others) are
   `Encoding=ISO-8859-1`; `subprocess` decoded `mod2imp` output as UTF-8 and
   crashed. Output is now captured as bytes and decoded per the module's own
   `Encoding`.

6. **The "Perseus LSJ" is an alpha-only file.** The 42.9 MB
   `grc.lsj.perseus-eng1.xml` parses to 18,950 entries — and 18,586 of them begin
   with alpha. It is the alpha fascicle, not the complete lexicon, so ingesting it
   under the name "LSJ" would have shipped ~2 % of the work while claiming the
   whole. Replaced with STEPBible's TFLSJ (5,706 full LSJ articles for the
   biblical vocabulary, 4.61 M characters, keyed by Extended Strong's number).
   `SOURCES.md` records the rejected file so it is not retried.
7. **XML child elements were cleared before their parent was read.** Both new
   XML parsers reacted to every element's `end` event and called `clear()` on
   children, so `iterparse` handed back an emptied `<entryFree>` / `<entry>`.
   LSJ articles collapsed to ~20 % of their length and BDB entries to headword-only
   stubs. Both parsers now react to the container tag only.
8. **BDB's editor status flags leaked into the text.** `<status p="1">done</status>`
   is a progress marker; `ET.tostring` re-prefixes the namespace, so the remover
   missed it and entries ended `…in OT times.\ndone`. Now stripped by a
   namespace-agnostic pattern.
9. **STEPBible link stubs.** `[<a title="…">Refs 2nd c.AD+</a>]` reduced to
   `[Refs 2nd c.AD+]` and then removed — the `title` attribute holds the citation
   the anchor points at, so keeping the anchor text alone was noise.

10. **Non-commercial licences leaked in again (v3).** Sefaria files 103 of its
    English texts under `CC-BY-NC` / `CC-BY-NC-SA`. The licence test
    `"cc-by" in license` matches `"cc-by-nc"`, so they were ingested — the same
    substring bug that let SWORD's CC BY-NC-ND modules through in v1. Replaced
    with an ordered canonicaliser (`pipeline/repair.py`) that tests for
    `-nc` / `-nd` / "non-commercial" *first* and rejects the work outright.
    109 works removed; the output now carries only Public Domain, CC0, CC BY,
    CC BY-SA and GPL.
11. **CCEL page-image volumes were being ingested as text.** 74 works are page
    scans whose ThML still contains `Image of page i`, `Image of page ii`, …
    placeholders. They passed because the parser took whatever text the markup
    held. Detected by counting those markers (75 works, 74 essentially
    image-only), removed to `not_ingested/`, and a guard added to
    `ccel_harvest.py` so a rerun rejects them. This is the no-OCR rule being
    enforced at the source rather than assumed.
12. **Duplicate detection produced 62 false positives.** A shingle similarity
    threshold of 0.92 on samples dominated by shared series front matter declared
    Barnes on Isaiah a duplicate of Schaff's Encyclopedia. Rewritten to drop
    **only exact-text duplicates** (2), and to *report* cross-source same-work
    pairs (50) for review rather than deleting them — the editions genuinely
    differ in coverage.
13. **Parallel harvesters lost each other's manifest rows.** CCEL and Sefaria ran
    concurrently and both rewrote `modules.json`, so 1,388 partitions ended up
    with no manifest row. Manifests are now written as per-work sidecars under
    `manifests/` and assembled by `combine.py`; a shared JSON is never the
    writer's target. The 1,388 rows were reconstructed from the partitions and
    the source surveys.

## Known limitations

* **Commentary keys are prefaces as well as verses.** Modules such as `MHC` and
  `KD` open with synthetic keys (`[ Testament 1 Heading ]`, `Genesis 0:0`) that
  carry the book introduction. They are kept — they are real content — and are
  identifiable by `verse = 0` or a non-parsable key with a null `book_id`.
* **Repeated headwords are qualified.** Where a work genuinely defines the same
  headword twice with different text, the second row is keyed `ADAM (2)`. The
  count is in `repeated_keys_disambiguated`.
* **Webster's 1913 is a general English dictionary**, not a Bible dictionary; it
  is included because `AARON'S ROD`, `EPHAH`, `SHEKEL` and hundreds of other
  biblical terms are defined there. Filter on `category`/`module_id` if you only
  want scripture-focused works.
* **LSJ keys are Extended Strong's numbers, not Greek lemmas.** `G3056` is
  λόγος; there is no lemma index, so join LSJ to the corpus through the other
  lexicons rather than by headword.
* **1,052 works carry an inferred public-domain basis.** Where CCEL's
  `DC.Rights` is empty but the digitised print edition predates 1929, the work is
  ingested and flagged `license_basis=inferred_pre1929` with the print year in
  the licence string. Filter on `license_basis = 'stated'` for the
  conservatively licensed 1,075.
* **Public-domain status is the distributor's assertion**, recorded verbatim in
  the manifest, not independently re-verified against national copyright records.

14. **A licence-policy correction silently re-admitted 277 works with no data.**
    Deleting the parked partitions before knowing the storage budget meant
    `repair.py --recheck` moved manifest rows back to `ok` for files that no
    longer existed. Two guards were added: a rejection can only be overturned
    when the work has a preserved `license_raw` (otherwise `canonical(None)`
    reads as public domain, which is a guess), and a restore that finds no parked
    file corrects the manifest instead of failing. All 268 Sefaria works and the
    3 SWORD modules were then rebuilt from source and re-verified.
15. **`verify.py` now cross-checks the partition directory against the manifest in
    both directions.** This is what caught the above: 10,153 modules against
    10,156 partitions, then 10,156 against 10,156.

## Audit pass, v5 — seven defects found by random sampling

`pipeline/audit.py` was written for this pass and is now part of the release
gate. It samples partitions at random and checks row-level content, not just
counts. Seven real defects surfaced; each is fixed and each has a guard.

16. **The classifier was not idempotent.** `taxonomy.py` fed a work's *existing*
    `topic` into the text it classified, so an earlier guess became evidence for
    the next run. Re-running it drifted works between areas — Patristics went
    351 → 92 for reasons that had nothing to do with the data, and Mbit. The
    previous topic is no longer an input; two runs now produce identical output
    (verified by hashing the output).
17. **5,427 works carried the wrong language.** Sefaria JSON often omits
    `actualLanguage`, and the harvester fell back to `"en"`. 5,419 Hebrew, 3
    Arabic, 4 Greek and 1 Cyrillic work were labelled English. The text's script
    is now detected, and `audit.py` checks every prose work's declared language
    against its script in both directions.
18. **Numeric and named entities reached the output uncleaned.** `&#226;`,
    `&gt;`, `&quot;` appeared in Matthew Henry, Flavel, Westcott; one source had
    double-escaped entities (`&#38;&#35;183;`). The cleaner now resolves named
    entities, repeats numeric resolution until stable, and drops out-of-range
    code points instead of emitting mojibake.
19. **Template residue** (`{{rom|__PAGESEPARATOR__xv}}`, `{{corr|conste|constate}}`)
    survived in French and Latin sources; 184 partitions were affected and were
    re-cleaned in place with the corrected cleaner.
20. **Editorial insertions and control bytes.** Sefaria's critical editions mark
    insertions as `[[השמטה …]]`, which reached the output as odd brackets, and one
    row in Rashba on Niddah carried a stray `0x19` byte. Both are stripped.
21. **`entry_order` was not 0..n-1 in 58 partitions** (Smith, JESermons, Clarke,
    TSK, Webster1828, …) — a parse artefact that breaks "entries in order"
    queries. Now asserted and repaired.
22. **1,015 exact duplicates were being kept.** Sefaria publishes many works
    twice — a page-split edition and a merged one — and the page separators made
    the full-text hash differ. Duplicate detection now also matches on the body
    sample. The tie-break was also broken: it tested for the word "inferred" in
    the licence *label*, which says "Public Domain", so it never fired. It now
    reads `license_basis`, and prefers a merged edition over a page-split one.
    The same pass cut the same-work review list from 78,234 junk pairs to 94 real
    ones by ignoring words that appear in more than 40 titles.

Everything above was re-verified after the rebuild: `verify.py` passes, and
`audit.py` passes with 800 randomly sampled partitions / 90,507 rows, no residual
markup, entities, control bytes or template text, correct `char_count` on every
sampled row, and no identical text across partitions.
