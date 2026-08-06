

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

We present the Executive Communications Dataset (ECD). The ECD covers
the years between 1964 and 2024 in 42 countries with 108,289
commmunications (speeches, press conferences, press releases etc) in 23
lanaguages. To faciliatate data distribution we developed the `ecdata`
package in R and Python. The ecdata package is a lightweight package
that is heavily inspired by [nflreadr](https://nflreadr.nflverse.com/)
for downloading data from the ECD repositories. The both packages
includes data dictionaries, lazy loading, and caching by default.

## Installation

You can download the latest stable releases of the packages through CRAN
and PyPi

### R

``` r
install.packages('ecdata')
library(ecdata)
library(dplyr)
```

### Python

``` python
%pip install ecdata
%pip install polars

import ecdata as ec
import polars as pl
```

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
