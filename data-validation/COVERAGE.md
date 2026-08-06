# Coverage by country, release 1.0.2

Generated from the published assets. `coverage-1.0.2.csv` alongside this file
carries the same numbers plus source hosts and languages, for anyone who would
rather join against it than read it.

**Documents, not rows, is the number to compare across countries.** A row is a
paragraph in some countries and a whole document in others (#15), so row counts
say as much about the scraper as about how much an executive spoke. Documents are
distinct source URLs.

Coverage is very uneven. Ten countries hold fewer than 500 documents and three
fewer than 100, while the United States alone holds 60,404 — more than a third of
the release. The median country holds 1,648. Read this table before comparing
countries; several of these series cannot support a descriptive claim, let alone
a causal one.

| country | documents | rows | span | median text |
|---|---:|---:|---|---:|
| Russia | n/a * | 9,333 | 1999-12-31 → 2023-01-13 | 3,131 |
| Nigeria | 10 | 298 | 2022-11-10 → 2023-08-08 | 195 |
| Costa Rica | 19 | 122 | 2023-12-18 → 2024-08-20 | 98 |
| Bolivia | 67 | 426 | 2021-11-11 → 2024-05-29 | 288 |
| Azerbaijan | 153 | 1,848 | 2010-06-30 → 2023-10-08 | 344 |
| Hong Kong | 217 | 1,839 | 2022-12-12 → 2024-08-13 | 94 |
| Jamaica | 237 | 6,421 | 2016-03-03 → 2024-01-01 | 273 |
| Republic of Korea | 301 | 9,202 | 2022-03-10 → 2023-11-15 | 25 |
| Canada | 317 | 19,859 | 2015-11-26 → 2023-10-16 | 99 |
| Philippines | 402 | 16,814 | 2019-04-23 → 2023-10-16 | 207 |
| Austria | 490 | 13,894 | 2003-01-16 → 2022-12-06 | 188 |
| Japan | 609 | 7,079 | 2017-11-01 → 2023-11-15 | 109 |
| New Zealand | 710 | 728 | 2014-10-14 → 2023-10-29 | 2,224 |
| Norway | 813 | 8,323 | 2021-10-14 → 2024-08-09 | 142 |
| Indonesia | 827 | 15,871 | 2014-09-14 → 2022-11-30 | 225 |
| France | 922 | 16,380 | 2020-01-06 → 2024-07-30 | 375 |
| Iceland | 955 | 4,976 | 2019-01-08 → 2024-08-07 | 270 |
| Chile | 1,083 | 1,874 | 2018-03-26 → 2023-03-14 | 1,506 |
| Greece | 1,215 | 17,399 | 2012-07-20 → 2024-06-06 | 304 |
| Australia | 1,267 | 35,726 | 2022-05-23 → 2023-11-29 | 145 |
| Argentina | 1,619 | 1,619 | 2015-12-10 → 2023-03-13 | 7,624 |
| Turkey | 1,677 | 65,301 | 2014-08-28 → 2024-07-19 | 308 |
| Georgia | 1,782 | 11,224 | 2021-02-22 → 2024-01-29 | 241 |
| Colombia | 1,903 | 2,018 | 2019-08-10 → 2024-07-20 | 10,148 |
| Czechia | 2,013 | 55,406 | 2006-09-23 → 2024-09-06 | 57 |
| Brazil | 2,217 | 5,077 | 1985-03-15 → 2024-06-14 | 9,206 |
| Ecuador | 2,236 | 20,619 | 2023-11-23 → 2024-03-19 | 275 |
| Germany | 2,250 | 45,121 | 2021-08-02 → 2024-08-19 | 275 |
| Mexico | 2,253 | 338,445 | 2017-09-13 → 2024-07-19 | 207 |
| Hungary | 2,351 | 25,900 | 2013-02-20 → 2024-07-27 | 242 |
| Denmark | 2,658 | 49,595 | 1997-09-19 → 2024-07-08 | 135 |
| India | 3,029 | 82,682 | 2014-08-15 → 2024-08-31 | 290 |
| Spain | 3,252 | 159,964 | 2004-04-15 → 2023-10-27 | 326 |
| Uruguay | 3,525 | 27,252 | 2010-08-25 → 2024-08-15 | 316 |
| United Kingdom | 3,638 | 79,760 | 2010-05-12 → 2024-02-28 | 155 |
| Poland | 5,702 | 28,551 | 2015-08-06 → 2024-10-16 | 257 |
| Italy | 6,739 | 20,359 | 1996-05-18 → 2024-01-04 | 235 |
| Portugal | 7,788 | 64,068 | 2015-11-26 → 2025-06-04 | 235 |
| Israel | 8,376 | 55,462 | 2004-05-24 → 2024-01-24 | 184 |
| Dominican Republic | 12,758 | 187,932 | 2012-08-16 → 2020-08-16 | 161 |
| Venezuela | 17,804 | 17,804 | 2017-05-14 → 2024-07-19 | 2,108 |
| United States of America | 60,404 | 1,359,051 | 1963-01-01 → 2024-12-31 | 274 |

\* Russia's `url` is 100% null, so its documents cannot be counted (#22). Its
9,333 rows are the English-language kremlin.ru edition rather than Russian
originals.

## Notable

* **Nigeria is ten documents** by two presidents across nine months. Costa Rica is
  nineteen. These are not country series.
* **Ecuador is four months** — 2,236 documents, Daniel Noboa only. The wider span
  in 1.0.0 was an artefact of a corpus pooled with the Dominican Republic (#10).
* **The Dominican Republic stops in August 2020.** `gobiernodanilomedina.do` is
  Danilo Medina's government site, so there is no Luis Abinader corpus.
* **Only the United States reaches back before 1985.** Twenty-two of 42 countries
  begin in 2015 or later, ten in 2020 or later.
* **Median text length ranges from 26 to 10,201 characters**, which is the grain
  problem in #15 made visible.
