# Data audit of release 1.0.0

An audit of every asset published in release `1.0.0` -- the 42 country parquet
files and `full_ecd.parquet` -- carried out in July 2026. Every finding below is
reproduced from the published assets alone, and every one of them is re-derived
automatically by [`ecd_validate.py`](ecd_validate.py); the report that script
produces for 1.0.0 is checked in as [`report-1.0.0.txt`](report-1.0.0.txt)
(19 CRITICAL, 55 ERROR, 107 WARN, 29 INFO).

These are problems in the published data, so they have to be fixed in the pipeline
that builds a release rather than in the R or Python packages that download it. The
packages can only work around them:

* `load_ecd()` and `lazy_load_ecd()` put every country file onto the 17 documented
  columns before combining them, so #4 no longer makes a multi country call fail.
* Both functions warn when you load a file affected by #1, #5, #9 or #11, and when
  you load `full_ecd.parquet`, which is affected by #2 and #3.
* `load_ecd(deduplicate = TRUE)` drops the repeated rows described in #5.

Reproductions assume the release assets have been downloaded locally, e.g.

```bash
curl -LO https://github.com/Executive-Communications-Dataset/ecdata/releases/download/1.0.0/ecuador.parquet
```

The examples use Python because the audit was run with polars and duckdb; the
findings are properties of the files, not of the reader.

---

## 1. Dominican Republic and Ecuador assets contain the same pooled corpus with swapped country labels

**Severity:** blocker — the two country series are not usable as published.

`dominican_republic.parquet` and `ecuador.parquet` each contain 214,977 rows drawn
from an identical set of 14,994 source URLs (Jaccard similarity 1.00). The URL set
mixes both countries' government sites; `country` and `executive` appear to have been
assigned by date order rather than by source domain.

```python
import polars as pl
dr = pl.read_parquet('dominican_republic.parquet', columns=['url','country','executive'])
ec = pl.read_parquet('ecuador.parquet',            columns=['url','country','executive'])

set(dr['url']) == set(ec['url'])   # True
dr.height, ec.height               # (214977, 214977)

for df in (dr, ec):
    print(df.with_columns(host=pl.col('url').str.extract(r'https?://([^/]+)'))
            .group_by(['host','executive']).len().sort('len', descending=True))
```

Result:

| file | source host | rows | labelled `executive` |
|---|---|---|---|
| `dominican_republic` | `gobiernodanilomedina.do` | 193,751 | Danilo Medina / Luis Abinader |
| `dominican_republic` | `comunicacion.gob.ec`, `presidencia.gob.ec` | 21,226 | **Luis Abinader** (Ecuadorian sources) |
| `ecuador` | `gobiernodanilomedina.do` | 193,751 | **Rafael Correa / Lenín Moreno** (Dominican sources) |
| `ecuador` | `comunicacion.gob.ec`, `presidencia.gob.ec` | 21,226 | Daniel Noboa |

So ~90% of the "Ecuador" rows are Dominican Republic content and ~10% of the
"Dominican Republic" rows are Ecuadorian. Spot-checking the text confirms it: rows in
`dominican_republic.parquet` attributed to Luis Abinader discuss Noboa, and rows in
`ecuador.parquet` attributed to Rafael Correa discuss Medina.

`load_ecd(country=['Dominican Republic','Ecuador'])` therefore returns every document
twice, under two different country labels.

**Expected:** each country asset contains only that country's documents, with
`country` and `executive` derived from the source rather than from row order.

**Suggested fix:** partition the pooled scrape by source domain before the executive
join, then re-run the term-based executive assignment per country. Worth auditing
whether any other pair of countries was scraped into a shared frame — the validation
script attached to this audit checks all pairs.

---

## 2. Portugal is reduced to a single empty row in `full_ecd.parquet`

**Severity:** blocker — 64,521 documents are silently absent from the full dataset.

```python
import polars as pl
full = pl.scan_parquet('full_ecd.parquet')
full.filter(pl.col('country') == 'Portugal').collect()
# 1 row: url, title, date, text, type, executive, language all null;
#        only isonumber=620, gwc='POR', cowcodes='POR', vdem=21 populated

pl.scan_parquet('portugal.parquet').select(pl.len()).collect()   # 64,522
```

A single all-null row carrying only the country-level metadata is the signature of a
left join that matched nothing — most likely because `portugal.parquet` lacks the
`url`, `type`, `language` and `year_of_statement` columns the join expects (see #4).

**Expected:** `full_ecd` contains Portugal's 64,522 rows.

---

## 3. Ecuador is concatenated twice into `full_ecd.parquet`

**Severity:** high.

```python
full.filter(pl.col('country') == 'Ecuador').select(pl.len()).collect()   # 429,954
pl.scan_parquet('ecuador.parquet').select(pl.len()).collect()            # 214,977
```

Exactly 2×, with every per-executive count doubled (Correa 101,581 → 203,162,
Moreno 92,170 → 184,340, Noboa 21,226 → 42,452).

The arithmetic reconciles the whole file and confirms both this and #2:

```
sum of the 42 country assets     16,845,134
  + Ecuador counted twice           +214,977
  - Portugal collapsed to 1 row      -64,521
  = full_ecd.parquet row count   16,995,590   ✓
```

**Suggested fix:** build `full_ecd` by iterating a deduplicated manifest of country
assets and assert `full_ecd.group_by('country').len()` matches the per-file row counts
exactly before publishing. The attached validation script does this reconciliation.

---

## 4. Country assets do not share a schema, so multi-country loads raise

**Severity:** blocker — this breaks the package's headline feature.

Across the 42 assets there are 27 distinct column names, not the 17 the README
documents, and `date` has two different dtypes.

```python
import polars as pl
pl.concat([pl.scan_parquet('france.parquet'),
           pl.scan_parquet('portugal.parquet')], how='vertical').head(1).collect()
# polars.exceptions.InvalidOperationError:
#   'union'/'concat' inputs should all have the same schema
```

| file | missing canonical columns | extra columns | `date` dtype |
|---|---|---|---|
| `portugal` | `url`, `type`, `language`, `file`, `year_of_statement`, `office` | `link`, `urls`, `tags`, `saving_name`, `start_date`, `end_date` | `Date` |
| `dominican_republic` | `title`, `file`, `office` | `subject`, `exec_name`, `term_start`, `term_end` | `Date` |
| `united_states_of_america` | — | `saving_name` | `Datetime(us, UTC)` |
| `germany` | — | `saving_name` | `Datetime(us, UTC)` |
| all others | — | — | `Datetime(us, UTC)` |

Because `load_ecd()` calls `pl.concat(..., how='vertical')`, **any** call that touches
Portugal, the Dominican Republic, the United States or Germany fails.

**Both multi-country examples in the README are among the failures.** The stray
`saving_name` column on the US and German assets is enough on its own:

```python
# README, "You can specify multiple countries to load_ecd like this"
load_ecd(country=['United States of America', 'Turkey', 'France'])
# polars.exceptions.InvalidOperationError

load_ecd(country=['United States of America', 'United Kingdom'])
# polars.exceptions.InvalidOperationError
```

So does `load_ecd(language='Portuguese')`, `load_ecd(language='Spanish')` and
`load_ecd(language='English')` — the English case pulls in the US asset.

**Expected:** every asset conforms to one published schema.

**Suggested fix:** two parts — (a) normalise the assets at build time by selecting the
canonical column list and casting `date` to `Datetime(us, UTC)`; (b) as a defensive
measure in the package, switch to `how='diagonal_relaxed'` so a schema slip degrades
to nulls instead of an exception. (a) is the real fix; (b) stops it being a hard
failure for users. Adding a schema assertion to the release pipeline would prevent
recurrence.

---

## 5. ~82% of all rows are exact duplicates

**Severity:** blocker for any count-based analysis.

Counting duplicates on `(url, text, date)` within each file: **13,745,026 of
16,845,134 rows (81.6%) are exact duplicates**; roughly 3.1M rows are distinct.

| file | rows | distinct URLs | duplicate rows |
|---|---:|---:|---:|
| `india` | 7,970,491 | 3,029 | **99.0%** |
| `denmark` | 4,801,705 | 2,658 | **99.0%** |
| `france` | 139,666 | 922 | 88.3% |
| `turkey` | 299,628 | 1,677 | 78.2% |
| `mexico` | 933,412 | 2,253 | 63.7% |
| `austria` | 34,579 | 490 | 59.8% |
| `republic_of_korea` | 16,420 | 301 | 44.0% |
| `hong_kong` | 2,900 | 217 | 36.6% |
| `czechia` / `germany` / `colombia` | | | 25.5% / 24.4% / 22.5% |

India alone is 47% of the dataset and has only 82,682 distinct `(url, text, date)`
combinations behind its 7.97M rows. India and Denmark together are 75% of all rows and
both are ~99% duplicated.

This is a many-to-many join, not repetition in the sources. The rows-per-distinct-
paragraph ratio within a single document comes out as a clean whole number:

```python
import duckdb
duckdb.sql("""
  SELECT url, count(*) AS rows, count(DISTINCT text) AS paragraphs,
         count(*)*1.0/count(DISTINCT text) AS ratio
  FROM read_parquet('republic_of_korea.parquet')
  GROUP BY url ORDER BY rows DESC LIMIT 5
""")
# every URL: ratio = 4.000
```

Worst individual cases: one `elysee.fr` URL holds 42,834 rows for 20 distinct
paragraphs (2,142×); one `pmindia.gov.in` URL holds 158,472 rows for 149 paragraphs
(1,064×); one `stm.dk` URL holds 157,990 rows for 370 paragraphs (427×). Austria and
Mexico show exact 6.0× and 3.0× ratios; Korea a uniform 4.0×.

**Likely cause:** the paragraph table is joined to an executive/term table (or a date
table) on a non-unique key, so each paragraph is multiplied by the number of matching
rows on the right-hand side.

**Suggested fix:** make the join key unique on the right-hand side before joining, and
add a post-join assertion that row count is unchanged. A `.unique()` on
`(url, text, date)` at build time would also cap the damage.

---

## 6. The unit of observation is inconsistent across countries

**Severity:** high — undocumented, and it silently distorts cross-country comparison.

Some assets are document-level, others are paragraph- or line-level:

| country | median `text` length |
|---|---:|
| Colombia | 10,201 chars |
| Brazil | 9,213 |
| Argentina | 7,624 |
| Russia | 3,131 |
| … | |
| Denmark | 117 |
| Canada | 99 |
| Hong Kong | 94 |
| Czechia | 45 |
| Republic of Korea | **26** |

The most frequent `text` values are salutations and boilerplate, not statements:
`साथियों,` (408,836×), `Friends,` (193,141×), `Det talte ord gælder`
("check against delivery", 20,356×), `(INICIA VIDEO)`, `---\r\r\n`, `Thank you.`,
`RONALD REAGAN`. Rows under 20 characters: Denmark 1,077,951; USA 72,066;
Mexico 33,117; Turkey 26,354; Czechia 16,203.

Anyone treating a row as "a statement" — the natural reading of the README — will get
wildly different counts per country for reasons that have nothing to do with how much
those executives spoke.

**Suggested fix:** either normalise to one document per row (aggregating paragraphs on
`url`), or keep paragraph-level rows but add an explicit `paragraph_index` /
`document_id` and document the grain prominently in the README and data dictionary.

---

## 7. Executive attribution errors

**Severity:** high — these corrupt the main covariate.

Checked by comparing each executive's observed date span against actual tenure.

**7a. The Obama → Trump handover is off by a full year.** Obama's rows end
`2016-01-19` and Trump's begin `2016-01-20`; the correct handover is 2017-01-20. About
a year of Obama's documents are attributed to Trump.

**7b. Gerald R. Ford's rows run to `1996-08-12`.** He left office 1977-01-20.

**7c. Biden is split across two spellings.** `Joseph R. Biden, Jr.` (475 rows, all on
2021-01-20) and `Jooseph R. Biden, Jr.` (115,871 rows). Any `group_by('executive')`
silently splits the presidency.

**7d. Netanyahu's span (2009-04-01 → 2024-01-24) swallows the Bennett and Lapid
governments**, which are also present as separate executives. The same period is
credited to two people.

**7e. Denmark: Lars Løkke Rasmussen spans 2009-04-07 → 2019-06-27**, overlapping Helle
Thorning-Schmidt's entire term (2011-10-04 → 2015-06-28), during which he was not PM.

**7f. Greece contains a person who did not exist:** `Ioannis Samaras`, 24 rows,
2023-05-25 → 2023-06-26. The caretaker PM in that window was Ioannis **Sarmas**; the
surname appears to have been contaminated by Antonis Samaras.

**7g. Russia:** `Vladimir Putin` spans 2000–2023, fully overlapping
`Dmitry Medvedec` (2008–2012). Whichever convention is intended, it should be
documented.

Reproduction:

```python
import duckdb
duckdb.sql("""
  SELECT executive, count(*) AS n, min(date) AS first, max(date) AS last
  FROM read_parquet('united_states_of_america.parquet')
  GROUP BY executive ORDER BY first
""")
```

**Suggested fix:** drive `executive` from a single reviewed term table keyed on
`(country, start_date, end_date)`, assert the intervals are non-overlapping and
contiguous per country, and assert every document's date falls inside exactly one
interval. Add a test that fails on any overlap.

---

## 8. Misspelled executive names

**Severity:** medium — breaks joins to external leader datasets.

| file | value | should be |
|---|---|---|
| `united_states_of_america` | `Jooseph R. Biden, Jr.` | Joseph R. Biden, Jr. |
| `russia` | `Dmitry Medvedec` | Dmitry Medvedev |
| `greece` | `Kyriakos Misotakis` | Kyriakos Mitsotakis |
| `greece` | `Ioannis Samaras` | Ioannis Sarmas |
| `denmark` | `Poul Nyrup Rasumussen` | Poul Nyrup Rasmussen |
| `argentina` | `Christina Fernandez de Kirchner` | Cristina Fernández de Kirchner |
| `georgia` | `Iralki Garibashvili` | Irakli Garibashvili |
| `spain` | `Jose Luis Rodriquez Zapatero` | José Luis Rodríguez Zapatero |
| `mexico` | `Andrew Manuel Lopez Obrador` | Andrés Manuel López Obrador |

The Mexico entry has had the given name *translated* into English rather than
transliterated.

Related: diacritic handling is inconsistent between countries. Portugal uses full
legal names with diacritics (`António Luís Santos da Costa`), Chile and Venezuela keep
them (`Sebastián Piñera`, `Nicolás Maduro`), while Austria, Spain, Turkey, Czechia and
Denmark are stripped (`Wolfgang Schussel`, `Recep Tayyip Erdogan`, `Andrej Babis`).
Italy uses composite values — `Romano Prodi/Massimo D'Alema`,
`Massimo D'Alema/Giuliano Amato` — which will not group or join.

**Suggested fix:** one canonical leader table with a documented normalisation rule
(pick either full diacritics or a consistent ASCII fold, and add the other as a second
column), one row per person, no composite values.

---

## 9. Venezuela is mojibake in 99.9% of rows

**Severity:** high — the text is unusable as-is.

```python
pl.read_parquet('venezuela.parquet').select('text').row(0)
# 'Prensa Mppdpsgg (...).- El presidente de la RepÃºblica Bolivariana de Venezuela,
#  NicolÃ¡s Maduro, felicitÃ³ este domingo ...'
```

UTF-8 bytes were decoded as latin-1/cp1252 at ingest: `RepÃºblica` for `República`,
`NicolÃ¡s` for `Nicolás`, `Â¡Feliz DÃ­a` for `¡Feliz Día`. 17,784 of 17,804 rows are
affected.

Smaller counts elsewhere: Brazil 97, Turkey 216, Portugal 24, USA 17, UK 7.

**Suggested fix:** re-decode at source (`response.encoding = 'utf-8'` / read bytes and
decode explicitly rather than relying on the requests/rvest charset guess). Existing
rows can be repaired with `text.encode('latin-1').decode('utf-8')` where that
round-trips cleanly.

---

## 10. `file` and `office` carry no information; several columns are entirely null

**Severity:** medium.

- **`file`** is 100% null in 40 of 42 assets (populated only in `brazil`, 57%, and
  `italy`, 90%) and absent from 2.
- **`office`** is 100% null everywhere it exists, absent from 2.
- **`language` is 100% null in `united_states_of_america`** — the largest Western
  case — even though the country dictionary and the README both show `English`. So
  `load_ecd(language='English')` returns US rows whose own `language` column is null.
- **`url` is 100% null in `russia`** (9,335 rows): no document is traceable to a
  source.
- **`ecuador`** has `isonumber`, `gwc`, `cowcodes`, `polity_v`, `polity_iv`, `vdem`
  and `year_of_statement` 100% null.
- **`hong_kong`** is missing all four regime-code columns and **`iceland`** is missing
  `polity_v` / `polity_iv`. These two are defensible (Hong Kong is not a sovereign
  state; Iceland is absent from Polity) but should be stated in the data dictionary
  rather than left for users to discover.

**Suggested fix:** drop `file` and `office`, or populate them; backfill the US
`language` and the Ecuador metadata from the country dictionary; document the
legitimately-missing regime codes.

---

## 11. All Jamaica URLs are malformed

**Severity:** medium.

All 6,481 rows have the base URL concatenated onto an already-absolute link:

```
https://opm.gov.jm/https://opm.gov.jm/...
```

None resolve. This is a `urljoin` that should have been a passthrough — the scraper is
prefixing the host to hrefs that were already absolute.

---

## 11b. Colombia's entire corpus is sourced from YouTube, not a government site

**Severity:** medium — provenance and reproducibility.

Every one of Colombia's 2,603 rows carries a YouTube watch URL as its `url`:

```python
import polars as pl
c = pl.read_parquet('colombia.parquet', columns=['url'])
c['url'].str.extract(r'https?://([^/]+)').unique().to_list()
# ['www.youtube.com']
c['url'].head(2).to_list()
# ['https://www.youtube.com/watch?v=CVf-yjptspU', ...]
```

Colombia is the only country in the release whose provenance is a third-party video
platform. Practical consequences:

- The `url` is not a citable official record, and the links are prone to rot — a
  deleted or unlisted video takes the provenance with it.
- The text is presumably a transcript. Whether it is an official transcript or an
  auto-generated caption track is not stated anywhere, and the two have very different
  error profiles. Colombia's median `text` length of 10,201 characters suggests one
  whole transcript per row, which also makes it one of the few document-level assets
  (see #6).
- 22.5% of Colombia's rows are exact duplicates, consistent with the same video being
  ingested more than once.

**Suggested fix:** document the sourcing in the data dictionary at minimum, and record
the transcript provenance (official vs. auto-caption) in a column. If an official
`presidencia.gov.co` record exists for these speeches, prefer it and keep the video
link as a secondary field.

---

## 12. `type` is not a controlled vocabulary, and in the US file it holds president names

**Severity:** medium — `type` cannot currently be used as a filter.

**12a.** `type` in `united_states_of_america.parquet` mixes genuine document
categories (`Proclamations`, `Executive Orders`, `Messages`, `Letters`,
`Spoken Addresses and Remarks`) with executive names: `John F. Kennedy`,
`Lyndon B. Johnson`, `Richard Nixon`, `Ronald Reagan`, `Barack Obama`,
`Donald J. Trump (1st Term)`, `Joseph R. Biden, Jr.`. Two fields have been crossed.

**12b.** Across the release there is no shared scheme: `Speech` / `speech` (the
Dominican Republic file uses both casings), `Press Statement`, `Press Release`,
`Pronouncement`, `Declaration`, `Communication`, `News`, `Events`, `Gov_decisions`,
`Announcements`, `Article`, `Other`. Jamaica has `Presidential Proclamtion` — a typo,
and conceptually odd for a country whose head of government is a prime minister.

**12c.** `type` is 100% null for 14 countries and 96% null for Denmark.

**Suggested fix:** publish a small controlled vocabulary, map each source's native
categories onto it, and keep the raw label in a separate `type_raw` column.

---

---

## Suggested triage order

1. **#1, #2, #3** -- wrong or missing data. Everything downstream is affected.
2. **#4** -- the packages' advertised multi-country load raised until it was worked
   around; the assets still do not share a schema.
3. **#5, #6** -- row counts are not usable until these are settled.
4. **#7, #8, #9** -- corrupted covariates and text.
5. **#10 - #12** -- field hygiene.

Items 1-5 would all have been caught before publication by the checks in
`ecd_validate.py`. See [README.md](README.md) for how to run it against a release
candidate.
