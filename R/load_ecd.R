#' Reading Executive Communications Dataset
#'
#' This function imports data from the ECD
#' @param country a character vector  with a country or countries in our dataset to download.
#' @param language a character vector with a lanaguage or languages in our dataset to download.
#' @param full_ecd to download the full Executive Communications Dataset set full_ecd to TRUE
#' @param ecd_version a character of ecd versions.
#' @param unit the unit of observation. "document", the default, is the release as published, where a row is whatever the scraper produced for that country -- a whole document, a paragraph, a sentence or an HTML block. "sentence" loads the sentence-level view of the same release, one row per sentence, with document_id, block_index and sentence_index added so a sentence can be put back in its document. Colombia is not segmented in that view; its rows carry no punctuation to split on.
#' @param normalize_schema the country files do not all share a schema. When TRUE, the default, each file is put on the 17 documented columns before the files are combined. Set to FALSE to get the columns exactly as they are published.
#' @param deduplicate several country files contain the same statement many times over. When TRUE rows that are duplicated on url, text and date are dropped. Defaults to FALSE so that row counts match the published files.
#' @returns A tibble with the specified country/countries or language/languages
#' @importFrom vctrs vec_rbind
#' @export
#' @examplesIf interactive() && curl::has_internet()
#' \dontrun{
#' library(ecdata)
#'
#' ## load one country
#'
#' load_ecd(country = 'Greece')
#'
#'
#'
#' ## load multiple countries
#'
#' load_ecd(country = c('Turkey', 'Republic of Korea'))
#'
#' ## drop the duplicated rows in the country files that have them
#'
#' load_ecd(country = 'India', deduplicate = TRUE)
#'
#' ## one row per sentence instead of per paragraph
#'
#' load_ecd(country = 'Chile', unit = 'sentence')
#'
#'
#'
#' }
#'


load_ecd = function(country=NULL, language=NULL , full_ecd=FALSE, ecd_version = '1.0.5',
                    unit = c('document', 'sentence'),
                    normalize_schema = TRUE, deduplicate = FALSE){
  if (!curl::has_internet()) {
  rlang::abort("Internet is required to use this function")
}

  unit = match.arg(unit)

  if(identical(unit, 'sentence') && isTRUE(full_ecd)){

    cli::cli_abort('There is no pooled file for the sentence view. Ask for countries or languages instead.')

  }

  ## the sentence view of a release is published under its own tag
  ecd_release = ecd_release_tag(ecd_version, unit)

  validate_inputs(country = country ,language = language, full_ecd = full_ecd,version = ecd_release)

  cache_message()

  download_full_ecd = full_ecd == TRUE && isTRUE(is.null(country)) && isTRUE(is.null(language))

  if(download_full_ecd){

    links_to_read = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_release}/full_ecd.parquet')

  } else {

    if('English' %in% language){

      cli::cli_alert_info('One of the languages in language is set to English. Note due to data availability Azerbaijan and Russian will be included in this data')

    }

    links_to_read = link_builder(country = country, language = language, ecd_version = ecd_release)

  }

  ## the known issue warnings and the download are deliberately kept apart.
  ## load_ecd_impl is memoised, so anything said inside it is said once per
  ## session at most, and a data quality caveat you see once and never again is
  ## barely better than no caveat at all.
  warn_known_issues(links = links_to_read, ecd_version = ecd_version, full_ecd = download_full_ecd)

  ecd_data = load_ecd_impl(links = links_to_read,
                           normalize_schema = normalize_schema,
                           deduplicate = deduplicate)

  if(nrow(ecd_data) == 0){

    cli::cli_alert_danger('Download of the ECD returned no rows')

    return(ecd_data)

  }

  if(download_full_ecd){

    cli::cli_alert_success('Successfully downloaded the full ECD')

  } else {

    ecd_country = unique(ecd_data$country)

    cli::cli_alert_success('Successfully downloaded {ecd_country}.')

  }

  return(ecd_data)

}


#' Download and combine the requested files
#'
#' The memoised half of `load_ecd`. It takes links rather than countries so that
#' everything that is not a download stays out of the cache.
#'
#' keywords @internal
#' @returns A data frame of the requested country files
#' @noRd

load_ecd_impl = function(links, normalize_schema = TRUE, deduplicate = FALSE){

  read_ecd_files(links = links,
                 normalize_schema = normalize_schema,
                 deduplicate = deduplicate)

}
