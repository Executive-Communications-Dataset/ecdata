# ecdata 1.3.0

* `load_ecd()` and `lazy_load_ecd()` now default to release `1.0.5`, the first
  release that validates with no CRITICAL and no ERROR findings. Since `1.0.3`
  it rebuilt `type` in the United States file -- 486,000 rows held a president's
  name rather than a document category, and 468,321 of them were recovered from
  the source url -- and corrected three mis-dated documents.

* Known-issue warnings for `1.0.5` no longer mention Brazil or Chile, whose rows
  dated before their executive took office turned out to be mis-dated rather
  than mis-attributed. Colombia and Russia still warn, but as provenance rather
  than as faults: Colombia is transcripts of YouTube videos the presidency
  published, and Russia comes from a pre-existing dataset rather than a scrape,
  which is why its `url` and `type` are empty.

# ecdata 1.2.0

* `load_ecd()` and `lazy_load_ecd()` now default to release `1.0.3`, a repair of
  `1.0.0` built from the published assets themselves. **Row counts fall by 82.8%,
  from 16,845,134 to 2,891,622**, because that is how many rows were exact
  duplicates: India goes from 7,970,491 rows to 82,682, Denmark from 4,801,705 to
  49,595. Ecuador and the Dominican Republic shrink further, because `1.0.0`
  published one pooled corpus under two country labels. If you have results from
  `1.0.0`, expect them to change. Pass `ecd_version = '1.0.0'` for the original
  assets, which are still published and unchanged. `1.0.2` additionally fills
  `language` for Portugal and the United States, 1,423,119 rows that previously
  carried none, so `load_ecd(language = 'English')` no longer omits the United
  States, and `1.0.3` corrects `executive`: the Obama/Trump handover moves from
  2016-01-20 to 2017-01-20, returning 23,255 rows to Obama, and Italy's
  composite values are split, so no `executive` value packs two people.

* Known-issue warnings for `1.0.3` no longer mention Austria, Denmark, Greece,
  Israel or Italy. Those files were reported as having overlapping executive
  terms by a validator check that compared each executive's first and last date
  rather than counting documents; a leader with two non-contiguous terms
  appeared to overlap a successor they never overlapped. None of them holds a
  double-attributed row.

* Known-issue warnings are keyed to the release you ask for. Loading `1.0.1` warns
  only about what the repair could not fix -- Colombia's YouTube provenance,
  Russia's English translations, the United States' `executive`, `type` and
  `language` columns, and the countries whose executive terms still overlap. The
  `full_ecd.parquet` warning is version-keyed too: `1.0.1` rebuilds that file from
  the country assets, so it no longer warns there.

* `load_ecd()` no longer fails when you ask for more than one country. The
  published country files do not share a schema: two are missing documented
  columns and carry scraper columns instead, two carry an extra column, and
  `date` is a plain date in two files and a UTC timestamp in the other forty.
  Every file is now put onto the 17 documented columns before the files are
  combined. Pass `normalize_schema = FALSE` for the columns exactly as published.

* Columns that were being dropped are recovered while normalizing. Portugal's
  document link lives in `urls` and the Dominican Republic's headline lives in
  `subject`; both now come back as `url` and `title`.

* `lazy_load_ecd()` opens the country files with `unify_schemas = TRUE` for the
  same reason, and no longer errors when both `country` and `language` are given.

* New `deduplicate` argument to `load_ecd()`. Several country files repeat the
  same statement many times over -- about 99% of the rows in `india.parquet` and
  `denmark.parquet` are exact duplicates. Defaults to `FALSE`, so row counts still
  match the published files unless you ask.

* `load_ecd()` and `lazy_load_ecd()` now warn about known problems in the release
  you are loading. The warnings are raised outside the memoised path, so they are
  not swallowed by the cache after the first call of a session.

* Removed the duplicate Azerbaijan and Russia rows from the country dictionary,
  and corrected `Portugese` to `Portuguese`. The old spelling is still accepted as
  an input to the `language` argument.

* `get_ecd_release()` is exported, so the available data versions can be listed
  from the package.

* `clear_cache()` now clears the cache the package actually uses, and the caching
  message points at `ecdata::clear_cache()` and `options(ecdata.verbose = FALSE)`
  rather than at names that do not exist.

* Added `data-validation/`: an audit of release 1.0.0, the script that reproduces
  it, and a workflow that runs the same checks against a release.

# ecdata 1.1.3

* Fixes issues with CRAN testing 

# ecdata 1.1.1

* Addresses CRAN note one by removing spaces in between url

* Addresses CRAN note two by adding notes about return values in documentation for all functions

* Addresses CRAN note three by wrapping load_ecd functions with don't test insteado of don't run

* Addresses CRAN note four by changing how the cache dir.

# ecdata 1.0.0

* Initial Release 