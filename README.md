

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

## Usage

### `load_ecd`

The primary function that is shared across the Python and R
distributions of the package is the `load_ecd` function. This function
accepts four primary arguments:

<table style="width:99%;">
<colgroup>
<col style="width: 7%" />
<col style="width: 46%" />
<col style="width: 46%" />
</colgroup>
<thead>
<tr>
<th>Argument</th>
<th>R Specific Quirks</th>
<th>Python Specific Quirks</th>
</tr>
</thead>
<tbody>
<tr>
<td>country</td>
<td>A String/A String Vector</td>
<td>String, Dictionary, or List</td>
</tr>
<tr>
<td>language</td>
<td>A String/A String Vector</td>
<td>String, Dictionary, or List</td>
</tr>
<tr>
<td>full_ecd</td>
<td>A boolean if set to TRUE downloads full dataset. Defaults to
FALSE</td>
<td>A boolean if set to True downloads full dataset. Defaults to
False</td>
</tr>
<tr>
<td>ecd_version</td>
<td>A character string of the ECD version you want to download. Defaults
to latest version</td>
<td>A character string of the ECD version you want to download. Defaults
to latest version</td>
</tr>
</tbody>
</table>

Functionally the `ecd_version` argument is not entirely useful since
there has only been one release of the data.

Say we only wanted data for South Korea[1] we can simply set the country
argument like this:

### R

``` r
rok = load_ecd(country = 'Republic of Korea')
```

    ✔ Successfully downloaded Republic of Korea.

### Python

``` python
rok = ec.load_ecd(country = 'Republic of Korea', ecd_version = '1.0.0', cache = False)

rok.head()
```

<div><style>
.dataframe > thead > tr,
.dataframe > tbody > tr {
  text-align: right;
  white-space: pre-wrap;
}
</style>
<small>shape: (5, 17)</small>

<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr>
<th data-quarto-table-cell-role="th">country</th>
<th data-quarto-table-cell-role="th">url</th>
<th data-quarto-table-cell-role="th">text</th>
<th data-quarto-table-cell-role="th">date</th>
<th data-quarto-table-cell-role="th">title</th>
<th data-quarto-table-cell-role="th">executive</th>
<th data-quarto-table-cell-role="th">type</th>
<th data-quarto-table-cell-role="th">language</th>
<th data-quarto-table-cell-role="th">file</th>
<th data-quarto-table-cell-role="th">isonumber</th>
<th data-quarto-table-cell-role="th">gwc</th>
<th data-quarto-table-cell-role="th">cowcodes</th>
<th data-quarto-table-cell-role="th">polity_v</th>
<th data-quarto-table-cell-role="th">polity_iv</th>
<th data-quarto-table-cell-role="th">vdem</th>
<th data-quarto-table-cell-role="th">year_of_statement</th>
<th data-quarto-table-cell-role="th">office</th>
</tr>
<tr>
<th>str</th>
<th>str</th>
<th>str</th>
<th>datetime[μs, UTC]</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>f64</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>f64</th>
<th>f64</th>
<th>str</th>
</tr>
</thead>
<tbody>
<tr>
<td>"Republic of Korea"</td>
<td>"https://www.president.go.kr/pr…</td>
<td>"​위대하고 자랑스러운 국민 여러분! 고맙습니다. 다시 …</td>
<td>2022-03-10 00:00:00 UTC</td>
<td>"정직한 정부, 정직한 대통령 되겠습니다."</td>
<td>"Yoon Suk Yeol"</td>
<td>"Speech"</td>
<td>"Korean"</td>
<td>null</td>
<td>410.0</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>42.0</td>
<td>2022.0</td>
<td>null</td>
</tr>
<tr>
<td>"Republic of Korea"</td>
<td>"https://www.president.go.kr/pr…</td>
<td>"​위대하고 자랑스러운 국민 여러분! 고맙습니다. 다시 …</td>
<td>2022-03-10 00:00:00 UTC</td>
<td>"정직한 정부, 정직한 대통령 되겠습니다."</td>
<td>"Yoon Suk Yeol"</td>
<td>"Speech"</td>
<td>"Korean"</td>
<td>null</td>
<td>410.0</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>42.0</td>
<td>2022.0</td>
<td>null</td>
</tr>
<tr>
<td>"Republic of Korea"</td>
<td>"https://www.president.go.kr/pr…</td>
<td>"​위대하고 자랑스러운 국민 여러분! 고맙습니다. 다시 …</td>
<td>2022-03-10 00:00:00 UTC</td>
<td>"정직한 정부, 정직한 대통령 되겠습니다."</td>
<td>"Yoon Suk Yeol"</td>
<td>"Speech"</td>
<td>"Korean"</td>
<td>null</td>
<td>410.0</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>42.0</td>
<td>2022.0</td>
<td>null</td>
</tr>
<tr>
<td>"Republic of Korea"</td>
<td>"https://www.president.go.kr/pr…</td>
<td>"​위대하고 자랑스러운 국민 여러분! 고맙습니다. 다시 …</td>
<td>2022-03-10 00:00:00 UTC</td>
<td>"정직한 정부, 정직한 대통령 되겠습니다."</td>
<td>"Yoon Suk Yeol"</td>
<td>"Speech"</td>
<td>"Korean"</td>
<td>null</td>
<td>410.0</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>42.0</td>
<td>2022.0</td>
<td>null</td>
</tr>
<tr>
<td>"Republic of Korea"</td>
<td>"https://www.president.go.kr/pr…</td>
<td>"늘 국민 편에 서겠습니다. "</td>
<td>2022-04-01 00:00:00 UTC</td>
<td>"초심을 잃지 않고, 겸손한 자세로 국민만 보고 가겠습니…</td>
<td>"Yoon Suk Yeol"</td>
<td>"Speech"</td>
<td>"Korean"</td>
<td>null</td>
<td>410.0</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>"ROK"</td>
<td>42.0</td>
<td>2022.0</td>
<td>null</td>
</tr>
</tbody>
</table>

</div>

We implement caching by default so you will get a pretty shouty warning
every few hours in R. `load_ecd` has some tolerance for common names,
abbreviations, and mixed punctuations of countries so if we wanted to
download the same data using `RK`, `ROK`, or `South Korea` these will
all download the South Korean data.

### R

``` r
sk = load_ecd(country = 'South Korea')
```

    ✔ Successfully downloaded Republic of Korea.

### Python

``` python

sk = ec.load_ecd(country = 'South Korea')
```

If you are not interested in single country case studies you can feed
multiple countries to the country argument. In R we use a string vector.
For Python you can use a list!

``` python

list_version = ec.load_ecd(country = ['South Korea', 'Turkey'])
```

The same functionality is extended to the language argument too!

## lazy_load_ecd

Both versions of the package allow you to use lazy loading to defer
computation till you are done querying the dataset. To do this all you
need to is call `lazy_load_ecd`

### R

``` r
turkey_korea_lazy = lazy_load_ecd(country = c('South Korea', 'Turkey')) 
```

    ✔ Note: Data for: South Korea and Turkey was successfully downloaded. To bring data into memory call dplyr::collect()

``` r
turkey_korea_lazy |>
  filter(country == 'Turkey') |>
  collect() |>
  head()
```

    # A tibble: 6 × 17
      country url     text  date                title executive type  language file 
      <chr>   <chr>   <chr> <dttm>              <chr> <chr>     <chr> <chr>    <chr>
    1 Turkey  https:… Bugü… 2023-04-08 00:00:00 Başa… Recep Ta… Spee… Turkish  <NA> 
    2 Turkey  https:… Noks… 2023-04-08 00:00:00 Başa… Recep Ta… Spee… Turkish  <NA> 
    3 Turkey  https:… Nası… 2023-04-08 00:00:00 Başa… Recep Ta… Spee… Turkish  <NA> 
    4 Turkey  https:… Sizl… 2023-04-08 00:00:00 Başa… Recep Ta… Spee… Turkish  <NA> 
    5 Turkey  https:… Bir … 2023-04-08 00:00:00 Başa… Recep Ta… Spee… Turkish  <NA> 
    6 Turkey  https:… Ülke… 2023-04-08 00:00:00 Başa… Recep Ta… Spee… Turkish  <NA> 
    # ℹ 8 more variables: isonumber <dbl>, gwc <chr>, cowcodes <chr>,
    #   polity_v <chr>, polity_iv <chr>, vdem <dbl>, year_of_statement <dbl>,
    #   office <chr>

### Python

``` python
turkey_rok_lazy = ec.lazy_load_ecd(['South Korea','Turkey'])

turkey_rok_lazy.filter(pl.col('country') == 'Turkey').collect().head()
```

<div><style>
.dataframe > thead > tr,
.dataframe > tbody > tr {
  text-align: right;
  white-space: pre-wrap;
}
</style>
<small>shape: (5, 17)</small>

<table class="dataframe" data-quarto-postprocess="true" data-border="1">
<thead>
<tr>
<th data-quarto-table-cell-role="th">country</th>
<th data-quarto-table-cell-role="th">url</th>
<th data-quarto-table-cell-role="th">text</th>
<th data-quarto-table-cell-role="th">date</th>
<th data-quarto-table-cell-role="th">title</th>
<th data-quarto-table-cell-role="th">executive</th>
<th data-quarto-table-cell-role="th">type</th>
<th data-quarto-table-cell-role="th">language</th>
<th data-quarto-table-cell-role="th">file</th>
<th data-quarto-table-cell-role="th">isonumber</th>
<th data-quarto-table-cell-role="th">gwc</th>
<th data-quarto-table-cell-role="th">cowcodes</th>
<th data-quarto-table-cell-role="th">polity_v</th>
<th data-quarto-table-cell-role="th">polity_iv</th>
<th data-quarto-table-cell-role="th">vdem</th>
<th data-quarto-table-cell-role="th">year_of_statement</th>
<th data-quarto-table-cell-role="th">office</th>
</tr>
<tr>
<th>str</th>
<th>str</th>
<th>str</th>
<th>datetime[μs, UTC]</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>f64</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>str</th>
<th>f64</th>
<th>f64</th>
<th>str</th>
</tr>
</thead>
<tbody>
<tr>
<td>"Turkey"</td>
<td>"https://www.tccb.gov.tr/konusm…</td>
<td>"Türkiye Cumhuriyeti’nin 11. Cu…</td>
<td>2014-08-28 00:00:00 UTC</td>
<td>"Devir Teslim Töreni’nde Yaptık…</td>
<td>"Recep Tayyip Erdogan"</td>
<td>"Speech"</td>
<td>"Turkish"</td>
<td>null</td>
<td>792.0</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>99.0</td>
<td>2014.0</td>
<td>null</td>
</tr>
<tr>
<td>"Turkey"</td>
<td>"https://www.tccb.gov.tr/konusm…</td>
<td>"Çok Değerli Abdullah Gül Karde…</td>
<td>2014-08-28 00:00:00 UTC</td>
<td>"Devir Teslim Töreni’nde Yaptık…</td>
<td>"Recep Tayyip Erdogan"</td>
<td>"Speech"</td>
<td>"Turkish"</td>
<td>null</td>
<td>792.0</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>99.0</td>
<td>2014.0</td>
<td>null</td>
</tr>
<tr>
<td>"Turkey"</td>
<td>"https://www.tccb.gov.tr/konusm…</td>
<td>"Saygıdeğer Devlet Başkanları,"</td>
<td>2014-08-28 00:00:00 UTC</td>
<td>"Devir Teslim Töreni’nde Yaptık…</td>
<td>"Recep Tayyip Erdogan"</td>
<td>"Speech"</td>
<td>"Turkish"</td>
<td>null</td>
<td>792.0</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>99.0</td>
<td>2014.0</td>
<td>null</td>
</tr>
<tr>
<td>"Turkey"</td>
<td>"https://www.tccb.gov.tr/konusm…</td>
<td>"Cumhurbaşkanları,"</td>
<td>2014-08-28 00:00:00 UTC</td>
<td>"Devir Teslim Töreni’nde Yaptık…</td>
<td>"Recep Tayyip Erdogan"</td>
<td>"Speech"</td>
<td>"Turkish"</td>
<td>null</td>
<td>792.0</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>99.0</td>
<td>2014.0</td>
<td>null</td>
</tr>
<tr>
<td>"Turkey"</td>
<td>"https://www.tccb.gov.tr/konusm…</td>
<td>"Meclis Başkanları ve Başbakanl…</td>
<td>2014-08-28 00:00:00 UTC</td>
<td>"Devir Teslim Töreni’nde Yaptık…</td>
<td>"Recep Tayyip Erdogan"</td>
<td>"Speech"</td>
<td>"Turkish"</td>
<td>null</td>
<td>792.0</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>"TUR"</td>
<td>99.0</td>
<td>2014.0</td>
<td>null</td>
</tr>
</tbody>
</table>

</div>

This has a lot of speed benefits when you are working with larger
datasets.

[1] I choose South Korea because the underlying file is relatively small
compared to some of the other country files.
