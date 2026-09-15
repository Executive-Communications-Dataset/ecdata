#' Reading Executive Communications Dataset lazily
#'
#' This function imports data from the ECD lazily meaning the data is out loaded out of memory
#' @param country a character vector  with a country or countries in our dataset to download.
#' @param language a character vector with a lanaguage or languages in our dataset to download.
#' @param full_ecd to download the full Executive Communications Dataset set full_ecd to TRUE
#' @param ecd_version a character of ecd versions.
#' @param unit the unit of observation. "document", the default, is the release as published, where a row is whatever the scraper produced for that country -- a whole document, a paragraph, a sentence or an HTML block. "sentence" loads the sentence-level view of the same release, one row per sentence, with document_id, block_index and sentence_index added so a sentence can be put back in its document. Colombia is not segmented in that view; its rows carry no punctuation to split on.
#' @returns An arrow Dataset with the specified country/countries or language/languages. Call `dplyr::collect()` to bring it into memory.
#' @importFrom curl multi_download
#' @export
#' @examplesIf interactive() && curl::has_internet()
#' \dontrun{
#' library(ecdata)
#'
#' ## load one country
#'
#' lazy_load_ecd(country = 'Greece')
#'
#' ## load multiple countries
#'
#' lazy_load_ecd(country = c('Turkey', 'Republic of Korea'))
#'
#' ## displays data from Turkey and South Korea
#'
#'
#'
#'
#' }
#'


lazy_load_ecd = function(country=NULL, language=NULL, full_ecd=FALSE, ecd_version = '1.0.5',
                         unit = c('document', 'sentence')){
  if (!curl::has_internet()) {
    rlang::abort("Internet is required to use this function")
  }

  unit = match.arg(unit)

  if(identical(unit, 'sentence') && isTRUE(full_ecd)){

    cli::cli_abort('There is no pooled file for the sentence view. Ask for countries or languages instead.')

  }

  ecd_release = ecd_release_tag(ecd_version, unit)

  validate_inputs(country = country, language = language, full_ecd = full_ecd, version = ecd_release)
  cache_message()
  tmp = tempdir()

  download_full_ecd = full_ecd == TRUE && isTRUE(is.null(country)) && isTRUE(is.null(language))

  if(download_full_ecd){

    links_to_read = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_release}/full_ecd.parquet')

  } else {

    if('English' %in% language){
      cli::cli_alert_info('One of the languages in language is set to English. Note due to data availability Azerbaijan and Russian will be included in this data')
    }

    links_to_read = link_builder(country = country, language = language, ecd_version = ecd_release)

  }

  warn_known_issues(links = links_to_read, ecd_version = ecd_version, full_ecd = download_full_ecd)

  dest_files = file.path(tmp, basename(links_to_read))

  multi_download(links_to_read, dest_files)

  ## the country files do not all carry the same columns, and `date` is a Date in
  ## two of them and a UTC timestamp in the rest. Without unify_schemas opening
  ## more than one of them at a time fails.
  ecd_data = arrow::open_dataset(sources = dest_files, unify_schemas = TRUE)

  if(nrow(ecd_data) > 0){

    if(download_full_ecd){

      cli::cli_alert_success('Successfully downloaded the full ECD. To bring data into memory call dplyr::collect()')

    } else {

      cli::cli_alert_success('Note: Data for: {c(country, language)} was successfully downloaded. To bring data into memory call dplyr::collect()')

    }

  } else {

    cli::cli_alert_danger('Download of the ECD returned no rows')

  }

  return(ecd_data)
}
