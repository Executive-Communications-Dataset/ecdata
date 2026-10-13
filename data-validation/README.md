# Release validation

`ecd_validate.py` checks a set of ECD parquet assets before they are published.
It is a release gate, not a package test: it reads the files a release would ship
and reports anything that would make them unusable to somebody who downloads them.

[`DATA_AUDIT.md`](DATA_AUDIT.md) is the audit of release `1.0.0` that this script
came out of, and [`report-1.0.0.txt`](report-1.0.0.txt) is what the script says
about that release today: 19 CRITICAL, 55 ERROR, 107 WARN, 29 INFO. Running it
before 1.0.0 shipped would have held the release.

## What it checks

| group | check |
|---|---|
| `schema` | every asset carries the 17 documented columns with the documented dtypes, and a vertical concat of all of them would succeed |
| `columns` | all-null columns, unparseable or out-of-range dates, mis-decoded text, malformed urls, `year_of_statement` disagreeing with `date` |
| `dup` | exact duplicate rows, and documents replicated within themselves by a many-to-many join |
| `cross` | two countries publishing the same source urls, which means a pooled corpus was written out under two labels |
| `domain` | source hosts that do not match the country the rows are labelled with |
| `exec` | executives credited with documents for the same dates, near-identical names that split one person in two, composite values |
| `type` | `type` used as a controlled vocabulary |
| `full` | `full_ecd.parquet` reconciles row for row against the per-country assets |

Provenance that is unusual but understood is listed in `DOCUMENTED_PROVENANCE`
and reported as `INFO` with the reason attached, rather than as an error --
Colombia's YouTube transcripts and Russia's missing fields are both there. A check
that keeps reporting a known, accepted property trains people to ignore it.

Findings are graded `CRITICAL`, `ERROR`, `WARN`, `INFO`. `--fail-on` decides which
of those makes the run exit non-zero.

## Running it

```bash
pip install polars duckdb requests

# against a release that is already published
python ecd_validate.py --download 1.0.0 --data-dir ./data \
       --full-ecd ./data/full_ecd.parquet --fail-on ERROR

# against release candidates sitting in a directory
python ecd_validate.py --data-dir ./candidate --json findings.json --out report.txt
```

duckdb is optional but strongly recommended: it spills to disk, so the 8 million
row files do not have to fit in memory. Without it the duplicate, domain and
executive checks are skipped and the report says so.

Useful flags:

* `--skip schema,dup,...` -- skip check groups while iterating on one of them
* `--json findings.json` -- machine readable findings
* `--out report.txt` -- write the text report to a file instead of stdout
* `--memory-limit 8GB` -- raise duckdb's memory ceiling on a bigger machine

## In CI

[`.github/workflows/validate-release.yml`](../.github/workflows/validate-release.yml)
runs the script whenever a release is published, and on demand through
**Actions -> Validate release**, where you can pass the version and the severity to
fail on. The report and the JSON findings are uploaded as artifacts on every run.

The workflow does not fail the build by default, because release `1.0.0` does not
pass. Once a release is clean, set `fail-on` to `ERROR` so that a regression is
caught rather than reported.

---

# Coverage

[`COVERAGE.md`](COVERAGE.md) is a per-country table -- documents, rows, span,
median text length -- generated from the published assets, with the same numbers
plus source hosts in [`coverage-1.0.2.csv`](coverage-1.0.2.csv). Regenerate it
for a new release before publishing; the spread it shows is the substance of #21.

# Repairing a release

`ecd_repair.py` rebuilds the assets from a published release, fixing the defects
that can be derived from the parquet files themselves. It exists because most of
what is wrong with `1.0.0` does not need a re-scrape — the information needed to
repair it is already in the files.

```bash
python ecd_repair.py --data-dir ./data --out-dir ./candidate --full-ecd
python ecd_validate.py --data-dir ./candidate \
       --full-ecd ./candidate/full_ecd.parquet --fail-on ERROR
```

| step | issue | what it does |
|---|---|---|
| `schema` | #14 | one set of 17 columns and dtypes; recovers `urls`/`subject`, which hold real data under a non-canonical name |
| `pooled` | #10 | splits the shared DR/Ecuador corpus by source domain and re-derives `executive` from the date |
| `dedupe` | #12 | drops exact duplicates on `(country, url, text, date)` |
| `labels` | — | fills country-level columns a partial join left null (brazil, 611 rows) |
| `text` | #16 | re-decodes UTF-8 that was read as latin-1, where the round-trip is clean |
| `url` | #17 | unwraps jamaica's doubled host prefix |
| `names` | #13 | corrects misspelled executives and brazil's `language` value |
| `full` | #11 | rebuilds `full_ecd.parquet` from the repaired assets |

Running it over `1.0.0` takes the validation report from **19 CRITICAL, 55 ERROR**
to **0 CRITICAL, 20 ERROR**:

| | 1.0.0 | repaired |
|---|---:|---:|
| rows | 16,845,134 | 2,808,940 |
| CRITICAL | 19 | **0** |
| ERROR | 55 | 20 |

The 20 remaining errors are the defects a repair pass cannot reach, and each has an
open issue: executive terms that overlap because there is no reviewed term table
(#13), columns that are null for a whole file and need a decision rather than a
transformation (#19), `type` holding president names in the US file (#20), and
Colombia's YouTube provenance (#18). Fixing those means changing the pipeline that
builds a release, which is the right place for all of them.

**Two things to know before publishing the output.** The repair drops 83% of the
rows, because that is how many were duplicates — check the change log it prints
against your expectations before you upload anything. And the tables it applies —
the DR and Ecuador presidential terms, the executive spellings — encode judgements
rather than derivations. They are at the top of the script, in one block, to be
reviewed.

---

# Restoring Colombia's punctuation

Colombia's rows are auto-generated YouTube captions. Each is a whole speech as
one run of words with no punctuation at all, and with no capitals through most
of Duque's term and YouTube's own through most of Petro's, which capitalise
some sentence starts and proper nouns and plenty of words that are neither.
`ecd_punctuate.py` puts the punctuation and capitals back, and changes nothing
else.

```bash
pip install polars torch transformers onnx onnxruntime sentencepiece huggingface_hub
python ecd_punctuate.py --data-dir ./data --out-dir ./candidate
```

Over `1.0.5` that adds 170,971 full stops, 372,343 commas and 2,119
questions to Colombia's 2,018 rows, 4.42 million words. It takes about
thirty-five minutes with `--device mps` on Apple silicon, and longer on a CPU;
the two give identical output.

## Why token classifiers

A token classifier labels the words it is given — a mark before, a mark after,
which letters are capitals. It can add punctuation and change case, but it has
no way to add, drop, reorder or respell a word. A generative model could punctuate
more fluently and would also quietly fix what it took for recognition errors,
which is not an edit a dataset can make. So every output row is checked against
its input, independently of the code that produced it: same whitespace, same
words up to case, at most a `¿` before a word and one of `.` `,` `?` after it.
If a single row fails, nothing is written.

Caption annotations — `[Aplausos]`, `[Risas]` — are left exactly as they are and
never shown to the models.

## Two models

| model | does | revision |
|---|---|---|
| [kredor/punctuate-all](https://huggingface.co/kredor/punctuate-all) | the mark after each word: `.` `,` `?` | `0fe3701` |
| [1-800-BAD-CODE/punctuation_fullstop_truecase_romance](https://huggingface.co/1-800-BAD-CODE/punctuation_fullstop_truecase_romance) | capitals, and `¿` | `1e8d395` |

The romance model punctuates too, and is the only one of the two that does
capitals or `¿` at all, but kredor is ahead on human punctuation by 0.10 F1 on
commas and 0.15 on full stops. So kredor places the marks, and the romance model
cases the words. The romance model decides capitals by first deciding
punctuation — it embeds the mark it chose after each token and conditions
capitalisation on that — so its graph is given kredor's marks in place of its
own, and the capitals follow the punctuation that is actually written: a word
after a comma is not left with the capital it would have had after a full stop.

Four rules on top:

* A sentence starts with a capital and a row ends with a terminal mark.
* Where kredor predicts a colon a comma is written, because there the human
  text has a comma more often than a colon.
* No mark is written inside a fixed phrase — 66 of them, in `FIXED_PHRASES`.
  kredor splits two kinds. Connectives, because it marks a parenthetical by
  putting a comma after every word of it and the word before: "y, por, lo,
  tanto," where a transcriber writes "y, por lo tanto,". And names and idioms
  whose words are also ordinary words: in `1.0.6` it wrote "Estados, Unidos"
  385 times, "Naciones, Unidas" 182 and "a, veces" 73.
* A `¿` is kept only in a sentence that a `?` closes, and a `?` with no `¿`
  gets one at the start of its sentence, so every question is opened and
  closed.

Which phrases are fixed is a judgement, so each one is also held to the
release's own human punctuation. `--review-phrases` checks that it occurs at
least 100 times in the Spanish-language files — enough to see a rate of 1 in
100 — and that the transcribers put a mark inside it in fewer than 1 in 100 of
them:

```bash
python ecd_punctuate.py --review-phrases --data-dir ./data
```

All 66 pass: across 274,828 uses in 753,095 rows from ten countries, the
transcribers split one 49 times. Three phrases came off the list that way.
*eso sí* is split 7.4% of the time, and rightly — "nada de eso. Sí se
afectaron" — while *más aún* is split 1.1% of the time and *por lo demás* is too
rare to judge, at 83 uses.

Input is lower-cased first, so Petro's rows are re-cased by the same model as
Duque's rather than keeping YouTube's capitals, and the two terms come out with
one convention.

## How good it is

`--evaluate` takes human-punctuated Spanish from the same release, strips its
punctuation and capitals, restores them, and scores the result: Mexico's
stenographic press-conference transcripts, which are spontaneous speech, and
Argentina's speeches. 60 documents of each, 3,000 words at most from each.

```bash
python ecd_punctuate.py --evaluate --data-dir ./data
```

| | Mexico precision | recall | F1 | Argentina precision | recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| `,` comma | 0.70 | 0.67 | **0.68** | 0.62 | 0.54 | **0.58** |
| `.` full stop | 0.57 | 0.75 | **0.65** | 0.48 | 0.69 | **0.57** |
| `?` question | 0.80 | 0.19 | 0.30 | 0.76 | 0.17 | 0.28 |
| `¿` opening | 0.80 | 0.19 | 0.30 | 0.69 | 0.16 | 0.26 |
| sentence boundary | 0.59 | 0.74 | **0.66** | 0.51 | 0.68 | **0.58** |
| capital letter | 0.75 | 0.87 | **0.80** | 0.70 | 0.77 | **0.73** |

177,280 words from Mexico and 98,276 from Argentina. The restored text has 1.26
and 1.34 times as many sentences as the transcripts.

Read these with two things in mind. They are an upper bound, because a
transcript has no recognition errors and a caption does. And they score every
disagreement with the transcriber as an error, when in spontaneous speech where
one sentence ends and the next begins is often a matter of style. About nine in
ten of the sentence breaks fall where the transcriber put a full stop or a
comma, and most of the rest of the disagreement is the model ending a sentence
at the transcriber's comma. Expect breaks at real clause boundaries, and
sentences somewhat shorter than a stenographer would make them.

**Questions are marked conservatively.** kredor marks about one question in
five and is right more than three times in four. Adding the romance model's
question marks would find more than twice as many and get more than half of
them wrong, turning statements into questions. A missed question reads as a statement,
which is what every row was before; a false one says something the speaker did
not.

---

# A sentence-level view

`ecd_sentences.py` derives one row per sentence from a release, and writes it
as a parallel set of files. The release it reads is left untouched.

```bash
pip install polars pysbd
python ecd_sentences.py --data-dir ./data --out-dir ./sentences --jobs 8
```

Over `1.0.5` that turns **2,891,622 rows into 9,207,251 sentences**, 3.2 per row.
It takes about twenty minutes on eight cores. Over `1.0.7`, where Colombia is
punctuated, it is **9,377,931 sentences**, and Colombia adds about a quarter of an
hour on one core: each of its rows is a whole speech, and pysbd's time grows
with the square of the length of what it is given.

## Why it is a separate view rather than a new release

The unit of observation already differs by country (#15) — a row is a whole
document in Brazil, a paragraph in Spain, a sentence in Canada, and an HTML
block in Czechia. Splitting into sentences gives one unit that means the same
thing everywhere, which is what cross-country text analysis needs. But
paragraph structure is real information for anything studying how an argument is
built, so this adds a view rather than replacing the release.

Every documented column is carried through, plus four that make the result
joinable and auditable:

| column | meaning |
|---|---|
| `document_id` | stable id for the source document, from its url |
| `block_index` | which original row within that document the sentence came from — the release's own grain, preserved |
| `sentence_index` | position of the sentence within the document |
| `segmenter` | which rules split it |

## Segmentation

[pysbd](https://github.com/nipunsadvilkar/pySBD) has rules for 11 of the 22
languages in the release: Spanish, German, French, Italian, Greek, Danish,
Polish, Japanese, Chinese, Hindi and English. The other 11 fall back to the
English rules.

The fallback was tested against real rows rather than assumed. In Czech,
Portuguese, Turkish, Korean, Hungarian, Hebrew, Indonesian, Icelandic,
Norwegian and Georgian, fewer than 4% of long passages collapse to a single
sentence. What it loses is language-specific abbreviation handling, so an
abbreviation followed by a capital letter can split early. The `segmenter`
column records which case each row was, so this is visible in the data rather
than only in this file.

## Where the output is poor, and why

Sentence splitting cannot improve on what it is given.

* **Colombia's sentence boundaries are a model's.** Its rows are auto-generated
  YouTube captions with no punctuation of their own. From `1.0.6` they carry the
  punctuation `ecd_punctuate.py` restores (above), and are segmented on it and
  marked `segmenter = "pysbd/es on restored punctuation"`: 2,018 rows become
  172,698 sentences, with a median of 121 characters. A few passages where the
  model chose commas throughout run on: 45 sentences are over 1,000 characters,
  0.3% of the text. A release without it, such as `1.0.5`, has no
  boundaries to find — 198 of 198 long rows yield a single "sentence" — so
  Colombia is passed through whole and marked
  `segmenter = "none (unpunctuated source)"` rather than silently split wrong.
* **Czechia (47% of sentences under 20 characters), Republic of Korea (25%),
  Japan (20%) and Hong Kong (18%)** are extracted block by block, so headings,
  captions and signature lines become "sentences". That is the source grain
  showing through, not a segmentation failure.
* **Italy** is OCR'd PDF text with a running page header, so some sentences are
  page furniture and some carry OCR noise.

## Checking the result

Total non-whitespace character mass is identical before and after, for all 42
countries — nothing is lost, duplicated or reordered:

```python
import polars as pl
mass = lambda p, c: (pl.read_parquet(p, columns=[c])[c]
                     .str.replace_all(r"\s+", "").str.len_chars().sum())
assert mass("sentences/canada.parquet", "text") == mass("data/canada.parquet", "text")
```

73 documents across Portugal, Ecuador, the Dominican Republic and Israel do not
appear in the output, because every row of those documents has empty text.
