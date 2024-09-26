

<img src="hex-logo.png" data-fig-align="center" />

`ecdata` is a minimal package for downloading *Executive Communications
Dataset*. It includes subsets of all the country data, the full dataset,
data dictionaries, and a sample script to help users expand the dataset.
For our full replication archive, see the relevant subdirectories in
[our
GitHub](https://github.com/joshuafayallen/executivestatements/tree/main/raw-data).
For a Python implementation see
[execcommunications-py](https://github.com/joshuafayallen/executivecommunications-py).

## Installation

To install `ecdata` run.

``` r
pak::pkg_install('joshuafayallen/executivestatements')
```

## Usage

To see a list of countries in our dataset and the associated file name
in the GitHub release, you can run:

``` r
library(ecdata)

ecd_country_dictionary |>
    head()
```

      name_in_dataset  file_name
    1       Argentina  argentina
    2       Australia  australia
    3         Austria    austria
    4      Azerbaijan azerbaijan
    5         Bolivia    bolivia
    6          Brazil     brazil

To load a specific country’s or countries’ data, you can use the
`load_ecd` function like this.

``` r
load_ecd(country = 'United States of America') |>
    head()

load_ecd(country = c('United States of America', 'Turkey', 'Republic of South Korea')) |>
    tail()
```
