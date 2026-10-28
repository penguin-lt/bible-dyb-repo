# pipeline/sources

Binary source modules used by the build scripts. Because the workspace has a size
limit, the seven modules that are **not** part of the dataset are stored gzipped
(`*.gz`): CGV, COMM, FAA, HNC, NEV, RHB and SENT — all licence-reasoned
exclusions recorded in `NOT_INCLUDED.md`. `COMPRESSED.json` records each file's
original size.

The modules that *are* ingested stay unpacked so the build scripts can read them
directly: `NTM.SQLite3` (MOFFATT), `NumNT.SQLite3` (PANIN), `kjv1611.ont`
(KJV1611), the three `.nt` theWord modules (ABU1865, Worrell, RIVERSIDE),
`Wm._Whiston_s_…WhistonNT_1745__.nt` (WHISTON) and the small Anderson/Tyndale
artefacts.

    python3 pipeline/sources/unpack.py          # restore every gzipped module
    python3 pipeline/sources/unpack.py RHB.SQLite3   # just one
