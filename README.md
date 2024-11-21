

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

      name_in_dataset  file_name language abbr_three_letter abbr_two_letter
    1       Argentina  argentina  Spanish               ARG              AR
    2       Australia  australia  English               AUS              AU
    3         Austria    austria  English               AUT              AT
    4      Azerbaijan azerbaijan  English               AZE              AZ
    5      Azerbaijan azerbaijan  English               AZE              AZ
    6         Bolivia    bolivia  Spanish               BOL              BO
      other_valid_inputs common_abr
    1               <NA>       <NA>
    2               <NA>       <NA>
    3               <NA>       <NA>
    4               <NA>       <NA>
    5               <NA>       <NA>
    6               <NA>       <NA>

## Python

    import ecdata as ec
    import polars as pl 

    ec.ecd_country_dictionary().head(int = 2)

## Loading the Executive Communications Dataset

We offer variety of options to load the ECD. You can specify single
countries

## R

``` r
load_ecd(country = 'United States of America') |>
    head(n = 2)
```

    ✔ Successfully downloaded United States of America.

                       country
    1 United States of America
    2 United States of America
                                                                                                                              url
    1 https://www.presidency.ucsb.edu/documents/statement-the-president-american-women-concerning-their-role-securing-world-peace
    2 https://www.presidency.ucsb.edu/documents/statement-the-president-american-women-concerning-their-role-securing-world-peace
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  text
    1                                                                                                                                                                                                                                                                                                                                    AS THE mothers of our children, women are most intimately concerned with the future of the human race. They realize that the nuclear threat to their own families is a threat to all mankind.
    2 I have been asked how women can best translate their concern into effective participation toward preserving peace. As a first step, there is no substitute for information. While the issues may be complex, they are not beyond the understanding of any intelligent person who takes the time to study them. Understanding does not require either a military background or access to top secret documents. The best sources of information are your own congressman or the Arms Control and Disarmament Agency in Washington.
            date
    1 1963-11-01
    2 1963-11-01
                                                                                            title
    1 Statement by the President to American Women Concerning Their Role in Securing World Peace.
    2 Statement by the President to American Women Concerning Their Role in Securing World Peace.
            executive type language file isonumber gwc cowcodes polity_v polity_iv
    1 John F. Kennedy <NA>  English <NA>       840 USA      USA      USA       USA
    2 John F. Kennedy <NA>  English <NA>       840 USA      USA      USA       USA
      vdem year_of_statement office
    1   20              1963   <NA>
    2   20              1963   <NA>

## Python


    ec.load_ecd(country = 'United States of America').head(int = 2)

You can specify multiple countries to `load_ecd` like this

## R

``` r
load_ecd(country = c('United States of America', 'Turkey', 'France'))  |>
    head(n = 3)
```

**Note**: There is some tolerance for typos as long as the typos are in
the form of capitilization mistakes. So this works

``` r
load_ecd(country ='UnItED StatEs of America')
```

## Python



    ec.load_ecd(country = {'United States of America', 'Turkey', 'France'}).head(n = 2)

For the Python version you can feed `load_ecd` a list or a dictionary.

## Example Scrappers

We also provide a set of an example scrappers in part to quickly
summarize our replication files and for other researchers to either
collect more recent data or expand the cases in our dataset. To call
these scrappers simply run:

## R

``` r
# static website scrapper
example_scrapper(scrapper_type = 'static')

# dynamic website scrapper 

example_scrapper(scrapper_type = 'dynamic')
```

## Python

    ## static scrapper
    ec.example_scrapper(scrapper_type = 'static')

    # warning static scrapper outputs R file

    ec.example_scrapper(scraper_type = 'dynamic')

If `scrapper_type = 'static'` this will open a R script in your current
editor. If `scrapper_type = 'dynamic'` this will open a Python script in
your editor.
