#' Reading Executive Communications Dataset
#' @aliases load_ecd
#' @param country a string with a country name or a string vector of country names
#' @param language a string with a language or character vector of languages
#' @param full_ecd a boolean when set to true will download the full ECD. Defaults to FALSE
#' @param ecd_version a string with the ecd_version you want to download
#' @returns A tibble with the specified country/countries or language/languages
#' @importFrom vctrs list_unchop
#' @importFrom arrow read_parquet
#' @examples
#' \dontrun{
#' library(ecdata)
#' 
#' ## load one country 
#' 
#' load_ecd(country = 'United States of America')
#' 
#' ## displays data from the USA
#' 
#' 
#' ## load multiple countries 
#' 
#' load_ecd(country = c('Turkey', 'Republic of South Korea', 'India'))
#'
#' ## displays data from Turkey, South Korea, and India
#' 
#' # load full ecd 
#' 
#' 
#' load_ecd(full_ecd = TRUE)
#' }
#' 
#' @export


load_ecd = \(country=NULL, language=NULL , full_ecd=FALSE, ecd_version = '1.0.0'){

  validate_inputs(country, language, full_ecd, version = ecd_version)

  if(full_ecd == TRUE && isTRUE(is.null(country)) && isTRUE(is.null(language))){
 
  cache_messge()
  
  url = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/full_ecd.parquet')
  
  ecd_data = read_parquet(url)
    
  if(nrow(ecd_data) > 0){
    cli::cli_alert_success('Successfully downloaded the full ECD')

  }
  else{

    cli::cli_alert_danger('Download of ECD  failed')
  }
    
  }
  

    if(full_ecd == FALSE && !isTRUE(is.null(country)) && isTRUE(is.null(language))){

      links_to_read = link_builder(country = country, ecd_version = ecd_version)

      cache_messge()

      ecd_data = lapply(links_to_read, \(x) read_parquet(x))

      ecd_data = ecd_data |>
        list_unchop()


      if(nrow(ecd_data) != 0){
          
        ecd_country = ecd_data$country

        ecd_country =  unique(ecd_country)


        cli::cli_alert_success('Successfully downloaded data for {ecd_country}')
      }
   

    }

  if(full_ecd == FALSE && isTRUE(is.null(country)) && !isTRUE(is.null(language))){
     
    if('English' %in% language){
      cli::cli_alert_info('One of the languages in language is set to English. Note due to data availability Azerbaijan and Russian will be included in this data')
    }

    links_to_read = link_builder(language = language, ecd_version = ecd_version)

    cache_messge()
    
    ecd_data = lapply(links_to_read, \(x) read_parquet(x)) |> 
      list_unchop()

    if(nrow(ecd_data) > 0){

      cli::cli_alert_success('Successfully downloaded data for {language}')
    }


  }
    
  if(full_ecd == FALSE && !isTRUE(is.null(country)) && !isTRUE(is.null(language))){

     links_to_read = link_builder(country = country, language = language)
    
    cache_messge()
    
    ecd_data = lapply(links_to_read, \(x) read_parquet(x)) |>
      list_unchop()

    if(nrow(ecd_data) > 0){

      cli::cli_alert_success("Successfully downloaded {country} and {language}")
    }
    

  }

    
  return(ecd_data)

  }


cache_messge = \(){
  do_it <- getOption("ecdata.verbose", default = interactive()) && getOption("ecdata.cache_warning", default = interactive())
   
   if(isTRUE(do_it)){
   rlang::inform(
     message = c(
       "Note: ecdata cache (i.e., stores a sved version) data by default. \n If you expect different outputs try one of the following:",
       i  = 'Restart your R session or',
       i = "Run ecdata::.clear_cache()"
     ),
     .frequency = "regularly",
     .frequency_id = "cache_messages"
   )
 
   }
 
 
 }
  