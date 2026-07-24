## The published country files do not share a schema: two are missing documented
## columns and carry scraper columns instead, and `date` is a Date in two files
## and a UTC timestamp in the other forty. These tests use small stand ins with
## the same shape.

portugal_like = function(){

  data.frame(
    country = 'Portugal',
    urls = 'https://www.portugal.gov.pt/statement',
    text = 'um discurso',
    date = as.Date('2020-01-01'),
    tags = 'politica',
    stringsAsFactors = FALSE
  )

}

france_like = function(){

  data.frame(
    country = 'France',
    url = 'https://www.elysee.fr/statement',
    text = 'un discours',
    date = as.POSIXct('2020-01-02', tz = 'UTC'),
    title = 'Discours',
    stringsAsFactors = FALSE
  )

}


test_that('normalizing puts a country file on the documented columns', {

  normalized = normalize_ecd_schema(portugal_like())

  expect_equal(names(normalized), ecd_canonical_columns())

  expect_equal(ncol(normalized), 17L)

})


test_that('columns published under another name are recovered rather than dropped', {

  ## portugal.parquet has no `url`, its document link lives in `urls`
  portugal = normalize_ecd_schema(portugal_like())

  expect_equal(portugal$url, 'https://www.portugal.gov.pt/statement')

  ## dominican_republic.parquet has no `title`, the headline lives in `subject`
  dominican = normalize_ecd_schema(
    data.frame(country = 'Dominican Republic', subject = 'Discurso',
               stringsAsFactors = FALSE)
  )

  expect_equal(dominican$title, 'Discurso')

})


test_that('an existing canonical column is never overwritten by its alias', {

  both = normalize_ecd_schema(
    data.frame(url = 'https://kept', urls = 'https://ignored',
               stringsAsFactors = FALSE)
  )

  expect_equal(both$url, 'https://kept')

})


test_that('date is harmonized to a UTC timestamp', {

  harmonized = harmonize_ecd_date(portugal_like())

  expect_s3_class(harmonized$date, 'POSIXct')

  expect_equal(format(harmonized$date, '%Y-%m-%d', tz = 'UTC'), '2020-01-01')

  ## files that already carry a timestamp are left alone
  untouched = harmonize_ecd_date(france_like())

  expect_equal(untouched$date, france_like()$date)

})


test_that('country files with different schemas can be combined', {

  files = lapply(list(portugal_like(), france_like()),
                 \(x) normalize_ecd_schema(harmonize_ecd_date(x)))

  combined = vctrs::vec_rbind(!!!files)

  expect_equal(nrow(combined), 2L)

  expect_equal(names(combined), ecd_canonical_columns())

  expect_equal(combined$country, c('Portugal', 'France'))

  expect_true(is.na(combined$title[1]))

  expect_equal(combined$title[2], 'Discours')

})


test_that('deduplicating drops repeated statements only', {

  repeated = do.call(rbind, replicate(4, france_like(), simplify = FALSE))

  expect_equal(nrow(deduplicate_ecd(repeated)), 1L)

  distinct = vctrs::vec_rbind(france_like(), normalize_ecd_schema(portugal_like()))

  expect_equal(nrow(deduplicate_ecd(distinct)), 2L)

})


test_that('known issues are reported for the files that have them', {

  links = link_builder(country = c('India', 'Greece'), ecd_version = '1.0.0')

  expect_message(warn_known_issues(links, ecd_version = '1.0.0'), 'india')

  ## a release we know nothing about should not warn about anything
  expect_silent(warn_known_issues(links, ecd_version = '9.9.9'))

  ## and neither should a country with no known problems
  greece = link_builder(country = 'Greece', ecd_version = '1.0.0')

  expect_silent(warn_known_issues(greece, ecd_version = '1.0.0'))

})
