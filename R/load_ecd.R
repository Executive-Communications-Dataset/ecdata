#' Reading Executive Communications Dataset
#'
#' This function imports data from the ECD
#' @param country a character vector  with a country or countries in our dataset to download.
#' @param language a character vector with a lanaguage or languages in our dataset to download.
#' @param full_ecd to download the full Executive Communications Dataset set full_ecd to TRUE
#' @param ecd_version a character of ecd versions.
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
#'
#'
#' }
#'


load_ecd = function(country=NULL, language=NULL , full_ecd=FALSE, ecd_version = '1.0.2',
                    normalize_schema = TRUE, deduplicate = FALSE){
  if (!curl::has_internet()) {
  rlang::abort("Internet is required to use this function")
}

  validate_inputs(country = country ,language = language, full_ecd = full_ecd,version = ecd_version)

  cache_message()

  download_full_ecd = full_ecd == TRUE && isTRUE(is.null(country)) && isTRUE(is.null(language))

  if(download_full_ecd){

    links_to_read = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/full_ecd.parquet')

  } else {

    if('English' %in% language){

      cli::cli_alert_info('One of the languages in language is set to English. Note due to data availability Azerbaijan and Russian will be included in this data')

    }

    links_to_read = link_builder(country = country, language = language, ecd_version = ecd_version)

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
