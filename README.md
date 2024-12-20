

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
