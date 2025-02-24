#' Reading Executive Communications Dataset lazily
#'  
#' This function imports data from the ECD lazily meaning the data is out loaded out of memory
#' @param country a character vector  with a country or countries in our dataset to download. 
#' @param language a character vector with a lanaguage or languages in our dataset to download. 
#' @param full_ecd to download the full Executive Communications Dataset set full_ecd to TRUE
#' @param ecd_version a character of ecd versions. 
#' @returns A tibble with the specified country/countries or language/languages
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
#' lazy_load_ecd(country = c('Turkey', 'Republic of South Korea'))
#'
#' ## displays data from Turkey, South Korea, and India
#' 
#' 
#' 
#' 
#' }
#' 


lazy_load_ecd = function(country=NULL, language=NULL, full_ecd=FALSE, ecd_version = '1.0.0'){
  if (!curl::has_internet()) {
    rlang::abort("Internet is required to use this function")
  }

  validate_inputs(country = country, language = language, full_ecd = full_ecd, version = ecd_version)
  cache_message()
  tmp = tempdir()

  if(full_ecd == TRUE && isTRUE(is.null(country)) && isTRUE(is.null(language))){
    url <- glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/full_ecd.parquet')
    dest_file <- file.path(tmp, basename(url))
    multi_download(url, dest_file)
    
    ecd_data <- arrow::open_dataset(dest_file)
    
    if(nrow(ecd_data) > 0){
      cli::cli_alert_success('Successfully downloaded the full ECD. To bring data into memory call dplyr::collect')
    } else {
      cli::cli_alert_danger('Download of ECD failed')
    }
  }

  if(full_ecd == FALSE && !isTRUE(is.null(country)) && isTRUE(is.null(language))){
    links_to_read <- link_builder(country = country, ecd_version = ecd_version)
    dest_files <- file.path(tmp, basename(links_to_read))
    multi_download(links_to_read, dest_files)

    # Create dataset from downloaded parquet files
    ecd_data <- arrow::open_dataset(sources = dest_files)
   
    if(nrow(ecd_data) > 0){
      cli::cli_alert_success('Note: Data for: {country} was successfully downloaded. To bring data into memory call dplyr::collect()')
    }
  }

  if(full_ecd == FALSE && isTRUE(is.null(country)) && !isTRUE(is.null(language))){
    if('English' %in% language){
      cli::cli_alert_info('One of the languages in language is set to English. Note due to data availability Azerbaijan and Russian will be included in this data')
    }

    links_to_read <- link_builder(language = language, ecd_version = ecd_version)
    dest_files <- file.path(tmp, basename(links_to_read))
    multi_download(links_to_read, dest_files)

    # Create dataset from downloaded parquet files
    ecd_data <- arrow::open_dataset(sources = dest_files)
   
    if(nrow(ecd_data) > 0){
      cli::cli_alert_success('Note: Data for: {language} was successfully downloaded. To bring data into memory call dplyr::collect()')
    }
  }
    
  if(full_ecd == FALSE && !isTRUE(is.null(country)) && !isTRUE(is.null(language))){
    links_to_read <- link_builder(country = country, language = language)
    dest_files <- file.path(tmp, basename(links_to_read))
    multi_download(links_to_read, dest_files)

    # Create dataset from downloaded parquet files
    ecd_data <- arrow::open_dataset(sources = dest_files)

    if(nrow(ecd_data) > 0){
      cli::cli_alert_success('Note: Data for: {language} and {country} were successfully downloaded. To bring data into memory call dplyr::collect')
    }
  }

  return(ecd_data)
}