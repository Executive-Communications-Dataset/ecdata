#' @title Reading Executive Communications Dataset
#'  
#' @description This function imports data from the ECD 
#'  
#' @param country a character vector  with a country or countries in our dataset to download. 
#' @param language a character vector with a lanaguage or languages in our dataset to download. 
#' @param full_ecd to download the full Executive Communications Dataset set full_ecd to TRUE
#' @param ecd_version a character of ecd versions. 
#' @importFrom vctrs list_unchop
#' @returns A tibble with the specified country/countries or language/languages
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


load_ecd <- \(country=NULL, language=NULL , full_ecd=FALSE, ecd_version = '1.0.0'){

  validate_inputs(country = country ,language = language, full_ecd = full_ecd,version = ecd_version)


  if(full_ecd == TRUE && isTRUE(is.null(country)) && isTRUE(is.null(language))){
  
      cache_messge()
  
  url <- glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/full_ecd.parquet')
  
  ecd_data <- arrow::read_parquet(url)
    
  if(nrow(ecd_data) > 0){
    cli::cli_alert_success('Successfully downloaded the full ECD')

  }
  else{

    cli::cli_alert_danger('Download of ECD  failed')
  }
    
  }
  

if(full_ecd == FALSE && !isTRUE(is.null(country)) && isTRUE(is.null(language))){
  
  cache_messge()

      links_to_read <- link_builder(country = country, ecd_version = ecd_version)

      ecd_data <- lapply(links_to_read, \(x) arrow::read_parquet(x))

      ecd_data <- ecd_data |>
        list_unchop()


      if(nrow(ecd_data) != 0){
          
        ecd_country = ecd_data$country

        ecd_country =  unique(ecd_country)


        cli::cli_alert_success('Successfully downloaded data for {ecd_country}')
      }
   

    }

if(full_ecd == FALSE && isTRUE(is.null(country)) && !isTRUE(is.null(language))){

  cache_messge()
     
    if('English' %in% language){
      cli::cli_alert_info('One of the languages in language is set to English. Note due to data availability Azerbaijan and Russian will be included in this data')
    }

    links_to_read = link_builder(language = language, ecd_version = ecd_version)
    
    ecd_data = lapply(links_to_read, \(x) arrow::read_parquet(x)) |> 
      list_unchop()

    if(nrow(ecd_data) > 0){

      cli::cli_alert_success('Successfully downloaded data for {language}')
    }


  }
    
if(full_ecd == FALSE && !isTRUE(is.null(country)) && !isTRUE(is.null(language))){

  cache_messge()

     links_to_read = link_builder(country = country, language = language)
    
    ecd_data = lapply(links_to_read, \(x) arrow::read_parquet(x)) |>
      list_unchop()

    if(nrow(ecd_data) > 0){

      cli::cli_alert_success("Successfully downloaded {country} and {language}")
    }
    

  }

    
  return(ecd_data)

  }


