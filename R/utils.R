#' Build our links 
#' 
#' @keywords internal
#' 
#' @export
#' 


link_builder = \(country = NULL, language = NULL, ecd_version){

  if(!isTRUE(is.null(country)) && isTRUE(is.null(language))){
  
    countries = country_dictionary()

    countries = countries |>
      within({
        name_in_dataset = tolower(name_in_dataset)
      })
    
    country_lower = tolower(country)
  
    country_names = countries[countries$name_in_dataset %in% country_lower,]


  
    country_names = country_names |>
      within({
        
        file_names = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/{file_name}.parquet')
      })
      country_names = country_names$file_names
  
  }
    
  if(isTRUE(is.null(country)) && !isTRUE(is.null(language))){
  
    countries = country_dictionary()

    countries = countries |>
      within({
        language = tolower(language)
      })
    
    lang_lower = tolower(language)
  
    country_names = countries[countries$language %in% lang_lower,]

  
    country_names = country_names |>
      within({
        file_names = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/{file_name}.parquet')
      })
    
      country_names = country_names$file_names
  
  }
    
    if(!isTRUE(is.null(country)) && !isTRUE(is.null(language))){
  
      countries = country_dictionary()

      countries = countries |>
        within({
          name_in_dataset = tolower(name_in_dataset)
          language = tolower(language)
        })
      
        lang_lower = tolower(language)
      
        country_lower = tolower(country)
  
      country_names = countries[countries$language %in% lang_lower | countries$name_in_dataset %in% country_lower,]
        
      

      country_names = country_names |>
        within({
          file_names = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/{file_name}.parquet')
        })
      
      
        country_names = country_names$file_names
  
    }
    
   
  
    return(country_names)
  
  }
