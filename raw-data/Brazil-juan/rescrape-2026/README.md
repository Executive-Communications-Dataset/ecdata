# ecd_BRAZIL — a rescrape of Brazilian presidential communications

Rebuilt October 2026 for the Executive Communications Dataset (ecdata), because
the Brazil file in releases 1.0.0–1.0.7 has a hole from March 1991 to December
2002 (no Itamar Franco, no Fernando Henrique Cardoso, most of Collor missing),
439 rows without an executive, and dates that cannot be checked. The raw files
that release was built from were never committed, so this goes back to source.

## Where the text comes from, and why not the live sites

Both official sources were unreachable when this was built (2026-10-14):

* **Presidency Library** — `biblioteca.presidencia.gov.br/presidencia/ex-presidentes/`,
  which holds every former president's speeches, interviews, messages to
  Congress and more — answers every page with "Esta página está em manutenção".
* **Planalto** — `gov.br/planalto/.../discursos-e-pronunciamentos/`, Lula's current
  term — redirects to a login page.

Both coincide with Brazil's 2026 general election (first round 4 October, runoff
25 October): electoral law restricts institutional publicity on government sites
in the three months before a vote. That is an inference, not something either
site says. The same pattern explains gaps in the existing dataset in 2014, 2018
and 2022.

So the text is taken from **web archives** of those two sites:

* the **Internet Archive's Wayback Machine** — the main source; and
* **Common Crawl** — a second archive, for documents the Wayback Machine only
  holds a bad copy of.

## A trap in the archived copies

From late 2018 the library served an anti-bot JavaScript challenge (F5 "TSPD")
to some crawlers instead of the page, and the archives stored those challenges
as if they were the documents. Every download here is checked by content
(`scraper/classify.py`): a challenge or a maintenance page is never saved, and
the next archived copy of the same document is tried instead. Documents for
which every archived copy is a challenge are recorded as such, not dropped
silently.

## Layout

```
scraper/                     the code; each script says what it does at the top
  wayback_index.py           list of archived URLs (one capture per URL)
  wayback_captures.py        every capture, with size and type
  targets.py                 one row per document, with its captures in order of promise
  fetch.py                   downloads, resumable, paced for the archive's rate limit
  classify.py                is this capture a real document, a challenge, or a maintenance page
  commoncrawl_index.py       Common Crawl's records for the same sites
  commoncrawl_fetch.py       fills from Common Crawl what the Wayback Machine lacked
  repair_pdfs.py             replaces truncated PDFs with a complete copy, where one exists
  parse.py                   pages and PDFs -> tables
  build_ecd.py               data/ + release 1.0.7 -> build/brazil.parquet, for the dataset
  repair_kept.py             repairs to the rows kept from 1.0.7 (called by build_ecd.py)
  status.py                  progress
raw/
  index/                     the archives' indexes, as fetched
  targets.tsv                what to fetch
  manifest.tsv               the outcome for every document (resumes from here)
  pages/<source>/<folder>/   every document as archived: PDFs as they are, HTML gzipped
data/
  documents.parquet / .csv   one row per document with text
  documents_index.csv        the same without the text column, for browsing
  catalogue.parquet / .csv   every document the library's own listings say exists
  missing.csv                catalogue entries whose text could not be recovered
  no_text.csv                downloads with no text (empty index pages, image PDFs)
logs/                        fetch.log (throttling, outages), run.log (progress)
```

## Columns in `data/documents`

| column | meaning |
|---|---|
| `executive` | the president whose section of the library the document is in — who spoke, not inferred from the date |
| `date`, `date_source` | the document's date, and where it came from: the library's catalogue entry, the title, the dateline, the URL, the page's publication date, or (least reliable) the year folder |
| `type` | Speech, Pronouncement, Interview, Message to Congress, Official note, Article, Radio programme or column — from the library's section |
| `title`, `text`, `n_words`, `n_chars` | the document; for PDFs the library's standard cover block is removed |
| `kind`, `n_pages` | `pdf` or `html` |
| `original_url`, `archive_url`, `archive_timestamp` | the page on the government site, and the archived copy the text was taken from |
| `raw_path` | the file under `raw/pages/` |

## The file for the dataset

`scraper/build_ecd.py` writes **`build/brazil.parquet`**: Brazil on the dataset's 17
columns, with only the eight presidents since 1985 — Sarney, Collor, Itamar Franco,
Fernando Henrique Cardoso, Lula, Dilma Rousseff, Temer and Bolsonaro. It merges
the rescrape with release 1.0.7 (`reference/brazil.parquet`): a 1.0.7 row the
rescrape also has, matched by its text, is replaced by the rescrape's copy; one
it lacks is kept, so nothing 1.0.7 had is lost. `build/report.md` has the counts
by president and year; `build/before_taking_office.csv` lists the documents left
out because they predate their speaker's term. The script's docstring lists
every rule it applies.

The rows kept from 1.0.7 are repaired by `scraper/repair_kept.py` before they
go in: words broken across lines in the PDF text are rejoined where the joined
form is a word in the clean web text, the press office's header is stripped
from Lula's 2003–10 PDFs -- at the top and at every page break, where it fell
in mid-sentence -- and their own title used instead, the editors' news notes
set into Sarney's published volumes are removed, Sarney's rows take title and
type from their headings, dates are corrected where the file name and header
agree or the speech's own dateline (within its speaker's term) says otherwise,
and duplicates, a placeholder and HTML tags are removed. The line-break and
header repairs apply to the rescrape's PDF text as well. Every rule is in that
script's docstring; `build/report.md` counts what each one did and lists every
date it changed.

`parse.py` reads PDFs with `pypdf`, which puts a space after every letter of
some fonts ("C o p y r i g h t"); those are read again with `pypdfium2`.

PDFs larger than 1 MB (or 5 MB) were cut off at that size by the crawlers, in
every archived copy; `scraper/repair_pdfs.py` looked for a complete one and
found none for 106 documents. PDFs made of page images are read with the OCR
built into macOS (`ocrmac`), cached under `raw/ocr/`.

## Running it

Everything runs from this folder with its own environment in `.venv`:

```bash
.venv/bin/python scraper/status.py          # progress
.venv/bin/python scraper/fetch.py           # resume the download (skips what is done)
.venv/bin/python scraper/parse.py           # rebuild data/ from whatever is downloaded
.venv/bin/python scraper/build_ecd.py       # build/brazil.parquet, from data/ and reference/brazil.parquet
```

The order from scratch is `wayback_index.py`, `wayback_captures.py`,
`commoncrawl_index.py`, `targets.py`, `fetch.py`, `commoncrawl_fetch.py`,
`repair_pdfs.py`, `parse.py`, `build_ecd.py`. `reference/brazil.parquet` is
`brazil.parquet` from release 1.0.7.

The Wayback Machine refuses connections from an address that sends much more
than about ten requests a minute, so `fetch.py` sends one at a time at nine a
minute and waits out refusals and outages. The full run takes most of a day.
When the official sites come back after the election, the same `parse.py` logic
applies to live pages, and the library's listings in `data/catalogue` say
exactly which documents are still missing.
