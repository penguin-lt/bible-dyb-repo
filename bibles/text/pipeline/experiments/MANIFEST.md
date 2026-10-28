# PDF quality experiment — manifest

These files were measured for the "can Google Books / Internet Archive PDFs be parsed?"
question and then **deleted from the workspace** to stay inside its 226 MB / 1,165-file
size limit. Every one of them is a public download and can be re-fetched from the URLs
below; the measurements they produced are quoted in `PDF_ONLY_SOURCES.md`,
`NOT_INCLUDED.md` and the session QA notes.

| file (deleted) | size | source | what it was used for |
|---|---:|---|---|
| `primitivenewtest00whisuoft_bw.pdf` | 29.0 MB | `https://archive.org/download/primitivenewtest00whisuoft/primitivenewtest00whisuoft_bw.pdf` | Whiston 1745 scan, parsed with PyMuPDF to measure the OCR text layer |
| `newtestamenttran1858sawy_bw.pdf` | 22.7 MB | `https://archive.org/download/newtestamenttran1858sawy/newtestamenttran1858sawy_bw.pdf` | Sawyer 1858 scan, same measurement |
| `NENT.pdf` | 2.6 MB | `https://www.ubm2.org/books/pdf/NENT.pdf` | born-digital control (Panin Numeric NT) |
| `primitivenewtest00whisuoft_djvu.txt` | 1.3 MB | `https://archive.org/download/primitivenewtest00whisuoft/primitivenewtest00whisuoft_djvu.txt` | OCR layer, token-matched against the module text |
| `sawyer_djvu.txt` | 1.1 MB | `https://archive.org/download/newtestamenttran1858sawy/newtestamenttran1858sawy_djvu.txt` | same |

Recreate with:

```bash
cd pipeline/experiments
for f in primitivenewtest00whisuoft newtestamenttran1858sawy; do
  curl -LO "https://archive.org/download/$f/${f}_djvu.txt"
  curl -LO "https://archive.org/download/$f/${f}_bw.pdf"
done
curl -LO https://www.ubm2.org/books/pdf/NENT.pdf
```

| measurement | result |
|---|---:|
| Whiston 1745 scan text layer — correct words recovered | 61.6 % |
| Sawyer 1858 scan text layer — correct words recovered | ~95 % |
| Panin born-digital PDF — correct words recovered | 99.7 % |

Sawyer's defects: 29 `cv`/`w` substitutions, 36 hyphen splits and 26 non-alphabetic
characters per 10 pages. Whiston's: long s → `f`, `w` → `vv`, one text object per word,
running heads and catchwords inside verses. This is why no scan was ingested.
