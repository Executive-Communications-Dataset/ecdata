

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

## Known issues in release 1.0.0

An audit of the assets published in release `1.0.0` found problems in the data
itself: the Dominican Republic and Ecuador files hold the same pooled corpus
under swapped labels, `full_ecd.parquet` contains Ecuador twice and Portugal not
at all, about 82% of rows are exact duplicates, and Venezuela's text is
mis-decoded. The full write up, and the script that reproduces it from the
published assets, are in
[`data-validation/`](https://github.com/Executive-Communications-Dataset/ecdata/tree/main/data-validation).

`load_ecd()` warns when you load an affected file. It also combines files that do
not share a schema, and takes `deduplicate = TRUE` for the files that repeat
themselves. These are workarounds for defects in the data, not fixes.
