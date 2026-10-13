

<p align="center">
<a href="https://executive-communications-dataset.github.io/ecdata/">
<img src="hex-logo.png" height = "350" class = "center"> </a>
</p>

When political executives speak, the world – citizens, markets,
international organizations, allies, rivals, the press listens. Indeed,
few things shape politics more than what political executives say in
public. It is not surprising, therefore, that vast literatures in
American and Comparative Politics, International Relations, Political
Psychology, Communications, and Political Theory debate the origins and
impact of leaders’ rhetoric. What is surprising is the absence of a
broad, cross-national dataset of speeches by political executives.
Without it, scholars cannot answer even basic descriptive questions
related to the rate, content, and timing of political executive
communications over time and space, let alone more theoretically
interesting questions about the causes and consequences of executive
communications.

We present the Executive Communications Dataset (ECD). Release `1.0.1`
holds 166,588 documents from 42 countries in 22 languages -- speeches,
press conferences, press releases and similar -- spanning 1963 to
2025. Coverage is uneven, and deliberately reported rather than
averaged over: the median country contributes 1,648 documents, but the
United States alone contributes 60,404 and Nigeria 10. Twenty-five of
the 42 countries hold at least 1,000 documents. Anyone comparing
countries should look at
[`data-validation/`](https://github.com/Executive-Communications-Dataset/ecdata/tree/main/data-validation)
and the open issues first. A per-country breakdown -- documents, span and source -- is in
[`data-validation/COVERAGE.md`](https://github.com/Executive-Communications-Dataset/ecdata/blob/main/data-validation/COVERAGE.md). To facilitate data distribution we
developed the `ecdata` package in R and Python. It is a lightweight
package heavily inspired by [nflreadr](https://nflreadr.nflverse.com/)
for downloading data from the ECD repositories. Both packages include
data dictionaries, lazy loading, and caching by default.

## Installation

Install both packages from GitHub. **Neither package index currently serves a
current version**: the R package was archived from CRAN on 2025-01-12, and PyPI
still holds `1.1.3`, which predates the data audit. Until both are re-published,
GitHub is the only route to a package that defaults to the repaired data.

### R

``` r
pak::pkg_install('Executive-Communications-Dataset/ecdata')
library(ecdata)
library(dplyr)
```

### Python

``` python
%pip install git+https://github.com/Executive-Communications-Dataset/ecdata-py
%pip install polars

import ecdata as ec
import polars as pl
```

Both give you version `1.4.0`, which defaults to data release
[`1.0.5`](https://github.com/Executive-Communications-Dataset/ecdata/releases/tag/1.0.5) --
the first release that validates with no critical or error findings.
`install.packages('ecdata')` will fail while the CRAN archival stands, and
`pip install ecdata` will silently give you `1.1.3`, which defaults to `1.0.0` and
carries the defects the audit found.

## Sentences instead of documents

A row means different things in different countries: a whole document in Brazil,
a paragraph in Spain, a sentence in Canada, an HTML block in Czechia. Counting
rows across countries therefore measures the scraper as much as the executive,
which is why the per-country table in
[`data-validation/COVERAGE.md`](data-validation/COVERAGE.md) reports documents
rather than rows.

`unit = 'sentence'` loads a sentence-level view of the same release --
**9,207,251 sentences against 2,891,622 rows**:

``` r
load_ecd(country = 'Chile')                     # 1,874 rows
load_ecd(country = 'Chile', unit = 'sentence')  # 16,787 sentences
```

``` python
ec.load_ecd(country='Chile')                    # 1,874 rows
ec.load_ecd(country='Chile', unit='sentence')   # 16,787 sentences
```

It adds `document_id`, `block_index` and `sentence_index`, so a sentence can be
put back in its document and the release's own grain is still visible, plus
`segmenter` recording which rules split each row.

Two things to know before using it. **Colombia is not segmented** -- its rows are
auto-generated YouTube captions with no punctuation to split on, and come back
whole. **Czechia, the Republic of Korea, Japan and Hong Kong** are extracted
block by block upstream, so a good share of their "sentences" are headings and
captions rather than prose.

The view is published as
[`1.0.5-sentences`](https://github.com/Executive-Communications-Dataset/ecdata/releases/tag/1.0.5-sentences)
and built by
[`data-validation/ecd_sentences.py`](data-validation/ecd_sentences.py). The
document-level release is untouched.

## Releases, and what is still wrong

`load_ecd()` defaults to release `1.0.1`. That is `1.0.0` with the defects that
could be derived from the published files repaired: the pooled Dominican
Republic/Ecuador corpus split by source domain, exact duplicates removed,
Venezuela's mis-decoded text fixed, Jamaica's urls unwrapped, one schema across all
42 assets, misspelled executives corrected, and `full_ecd.parquet` rebuilt from the
country assets. **Row counts are 82.8% lower than in `1.0.0`** -- 2,891,622 against
16,845,134 -- because that is how many rows were duplicates. Pass
`ecd_version = '1.0.0'` for the original assets, which are still published.

What `1.0.1` does not fix needs the source data back or a decision about what a
column means: overlapping executive terms, Colombia's YouTube provenance, Russia's
English translations, `type` in the US file, and the columns that are null for a
whole country. `load_ecd()` warns for the assets those affect.

The audit behind all of this, and the scripts that reproduce and repair it, are in
[`data-validation/`](https://github.com/Executive-Communications-Dataset/ecdata/tree/main/data-validation).
