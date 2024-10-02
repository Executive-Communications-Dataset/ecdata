

<p align="center">
<a href="https://executive-communications-dataset.github.io/ecdata/">
<img src="hex-logo.png" height = "350" class = "center"> </a>
</p>

`ecdata` is a minimal package for downloading *Executive Communications
Dataset*. It includes subsets of all the country data, the full dataset,
data dictionaries, and a sample script to help users expand the dataset.
For our full replication archive, see the relevant subdirectories in
[our
GitHub](https://github.com/Executive-Communications-Dataset/ecdata/tree/main/raw-data).
For a Python implementation see
[execcommunications-py](https://github.com/Executive-Communications-Dataset/ecdata-py).

## Installation

To install `ecdata` run.

## R

``` r
pak::pkg_install('Executive-Communications-Dataset/ecdata')
```

## Python


    (uv) pip install git+https://github.com/Executive-Communications-Dataset/ecdata-py

## Usage

To see a list of countries in our dataset and the associated file name
in the GitHub release, you can run:

## R

``` r
library(ecdata)

ecd_country_dictionary |>
    head()
```

         country   language
    1  Argentina    Spanish
    2  Australia    English
    3    Austria    English
    4 Azerbaijan    English
    5    Bolivia    Spanish
    6     Brazil  Portugese

## Python

``` python
import ecdata as ec
import polars as pl 

ec.ecd_country_dictionary().head(int = 2)
```

## Loading the Executive Communications Dataset

We offer variety of options to load the ECD. You can specify single
countries

## R

``` r
load_ecd(country = 'United States of America') |>
    head(n = 2)
```

    ✔ Successfully downloaded data for United States of America

                       country
    1 United States of America
    2 United States of America
                                                                                              url
    1 https://www.presidency.ucsb.edu/documents/remarks-luncheon-for-the-us-olympic-medal-winners
    2 https://www.presidency.ucsb.edu/documents/remarks-luncheon-for-the-us-olympic-medal-winners
                                                                                                                                                                         text
    1                                                                                                                                                            About Search
    2 I hope you are understanding people. I appreciate your patience and ask for your forgiveness. I would like to introduce to you a few of our distinguished guests today.
            date title         executive   type language file isonumber gwc
    1 1964-12-01  <NA> Lyndon B. Johnson Speech  English <NA>       840 USA
    2 1964-12-01  <NA> Lyndon B. Johnson Speech  English <NA>       840 USA
      cowcodes polity_v polity_iv vdem year_of_statement
    1      USA      USA       USA   20              1964
    2      USA      USA       USA   20              1964

## Python

``` python
ec.load_ecd(country = 'United States of America').head(int = 2)
```

You can specify multiple countries to `load_ecd` like this

## R

``` r
load_ecd(country = c('United States of America', 'Turkey', 'France'))  |>
    head(n = 3)
```

    ✔ Successfully downloaded data for United States of America, Turkey, and France

      country
    1  France
    2  France
    3  France
                                                                                           url
    1 https://www.elysee.fr/emmanuel-macron/2020/01/06/conseil-des-ministres-du-6-janvier-2020
    2 https://www.elysee.fr/emmanuel-macron/2020/01/06/conseil-des-ministres-du-6-janvier-2020
    3 https://www.elysee.fr/emmanuel-macron/2020/01/06/conseil-des-ministres-du-6-janvier-2020
                               text       date
    1 6 janvier 2020 - Compte-rendu 2020-01-06
    2                PROJETS DE LOI 2020-01-06
    3                    ORDONNANCE 2020-01-06
                                        title executive                 type
    1 Conseil des ministres du 6 janvier 2020      <NA> Council Of Ministers
    2 Conseil des ministres du 6 janvier 2020      <NA> Council Of Ministers
    3 Conseil des ministres du 6 janvier 2020      <NA> Council Of Ministers
      language file isonumber gwc cowcodes polity_v polity_iv vdem
    1   French <NA>       250 FRN      FRN      FRN       FRN   76
    2   French <NA>       250 FRN      FRN      FRN       FRN   76
    3   French <NA>       250 FRN      FRN      FRN       FRN   76
      year_of_statement
    1              2020
    2              2020
    3              2020

## Python

``` python
ec.load_ecd(country = {'United States of America', 'Turkey', 'France'}).head(n = 2)
```

For the Python version you can feed `load_ecd` a list or a dictionary.

## Example Scrappers

We also provide a set of an example scrappers in part to quickly
summarize our replication files and for other researchers to either
collect more recent data or expand the cases in our dataset. To call
these scrappers simply run:

``` r
# static website scrapper
example_scrapper(scrapper_type = 'static')

# dynamic website scrapper 

example_scrapper(scrapper_type = 'dynamic')
```

If `scrapper_type = 'static'` this will open a R script in your current
editor. If `scrapper_type = 'dynamic'` this will open a Python script in
your editor.
