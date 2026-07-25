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
| `exec` | executives whose date spans overlap, near-identical names that split one person in two, composite values |
| `type` | `type` used as a controlled vocabulary |
| `full` | `full_ecd.parquet` reconciles row for row against the per-country assets |

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
