#' Build our links 
#' 
#' @keywords internal
#' @returns A glue string with the correct links to the Github data.
#' @export
#' 


link_builder = \(country = NULL, language = NULL, ecd_version = '1.0.1'){

  if(!isTRUE(is.null(country)) && isTRUE(is.null(language))){
  
    countries = country_dictionary()

    countries = countries |>
      within({
        name_in_dataset = tolower(name_in_dataset)
        abbr = tolower(abbr)
      })
    
    country_lower = tolower(country)
  
    country_names = countries[countries$name_in_dataset %in% country_lower | countries$abbr %in% country_lower,]


  
    country_names = country_names |>
      within({
        
        file_names = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/{file_name}.parquet')
      }) 
       
    
      country_names = country_names$file_names
    
      country_names = unique(country_names)
  
  }
    
  if(isTRUE(is.null(country)) && !isTRUE(is.null(language))){
  
    countries = country_dictionary()

    countries = countries |>
      within({
        language = fold_language(language)
      })
    
    lang_lower = fold_language(language)
  
    country_names = countries[countries$language %in% lang_lower,]

  
    country_names = country_names |>
      within({
        file_names = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/{file_name}.parquet')
      })
    
      country_names = country_names$file_names
      country_names = unique(country_names)
  
  }
    
    if(!isTRUE(is.null(country)) && !isTRUE(is.null(language))){
  
      countries = country_dictionary()

      countries = countries |>
        within({
          name_in_dataset = tolower(name_in_dataset)
          language = fold_language(language)
          abbr = tolower(abbr)
        })
      
        lang_lower = fold_language(language)
      
        country_lower = tolower(country)
        
  
       country_names = countries[countries$language %in% lang_lower | countries$name_in_dataset %in% country_lower |
                                 countries$abbr %in% country_lower,]
        
      

      country_names = country_names |>
        within({
          file_names = glue::glue('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/{ecd_version}/{file_name}.parquet')
        })
      
      
        country_names = country_names$file_names
       
        country_names = unique(country_names)
  
    }
    
   
  
    return(country_names)
  
  }

#' keywords @internal 
#' @returns A cache message
#' @noRd
#' 

  cache_message = function(){
    do_it <- getOption("ecdata.verbose", default = interactive()) && getOption("ecdata.cache_warning", default = interactive())
     
     if(isTRUE(do_it)){
     rlang::inform(
       message = c(
         "Note: ecdata cache (i.e., stores a saved version) data by default. \n If you expect different outputs try one of the following:",
         i  = 'Restart your R session or',
         i = "Run ecdata::clear_cache()",
         "To disable this warning, run `options(ecdata.verbose = FALSE)` or add it to your .Rprofile"
       ),
       .frequency = "regularly",
       .frequency_id = "cache_messages"
     )
   
     }
   
   
   }
    

#' Fold a language name for matching
#'
#' Lower cases a language and maps historical misspellings onto the spelling the
#' dictionary uses, so `language = 'Portugese'` keeps working now that the
#' dictionary says `Portuguese`.
#'
#' keywords @internal
#' @returns A lower case character vector of language names
#' @noRd

fold_language = function(language){

  if(is.null(language)) return(language)

  folded = tolower(language)

  aliases = c(portugese = 'portuguese')

  matched = match(folded, names(aliases))

  folded[!is.na(matched)] = unname(aliases[matched[!is.na(matched)]])

  folded

}


#' The columns the ECD documents
#'
#' keywords @internal
#' @returns A character vector of the 17 documented column names
#' @noRd

ecd_canonical_columns = function(){

  c('country', 'url', 'text', 'date', 'title', 'executive', 'type', 'language',
    'file', 'isonumber', 'gwc', 'cowcodes', 'polity_v', 'polity_iv', 'vdem',
    'year_of_statement', 'office')

}


#' Columns that hold canonical data under another name
#'
#' Verified against release 1.0.0: portugal.parquet has no `url` but its `urls`
#' column is fully populated, and dominican_republic.parquet has no `title` but
#' `subject` holds the headline. Both used to be dropped on load.
#'
#' keywords @internal
#' @returns A named character vector mapping the column found to its canonical name
#' @noRd

ecd_column_aliases = function(){

  c(urls = 'url', subject = 'title')

}


#' Put one country file onto the documented schema
#'
#' keywords @internal
#' @returns A data frame with the documented columns, in the documented order
#' @noRd

normalize_ecd_schema = function(ecd_data){

  aliases = ecd_column_aliases()

  for (alias in names(aliases)) {

    canonical = unname(aliases[alias])

    if(alias %in% names(ecd_data) && !canonical %in% names(ecd_data)){

      names(ecd_data)[names(ecd_data) == alias] = canonical

    }

  }

  canonical_columns = ecd_canonical_columns()

  missing_columns = setdiff(canonical_columns, names(ecd_data))

  for (missing in missing_columns) {

    ecd_data[[missing]] = NA

  }

  ecd_data[canonical_columns]

}


#' Make `date` comparable across country files
#'
#' `date` is a Date in two of the country files and a UTC timestamp in the other
#' forty, which is enough on its own to make binding them fail.
#'
#' keywords @internal
#' @returns A data frame whose date column is a UTC timestamp
#' @noRd

harmonize_ecd_date = function(ecd_data){

  if(!'date' %in% names(ecd_data)) return(ecd_data)

  if(inherits(ecd_data$date, 'POSIXct')) return(ecd_data)

  if(inherits(ecd_data$date, 'Date')){

    ecd_data$date = as.POSIXct(as.character(ecd_data$date), tz = 'UTC')

  }

  ecd_data

}


#' Drop rows that are exact duplicates
#'
#' keywords @internal
#' @returns A data frame with duplicate statements removed
#' @noRd

deduplicate_ecd = function(ecd_data){

  keys = intersect(c('url', 'text', 'date'), names(ecd_data))

  if(length(keys) == 0) return(ecd_data)

  ecd_data[!duplicated(ecd_data[keys]), , drop = FALSE]

}


#' Read and bind the country files
#'
#' The country files do not share a schema, so they are aligned by column name
#' before they are bound rather than assuming they line up.
#'
#' keywords @internal
#' @returns A data frame of every requested country file
#' @noRd

read_ecd_files = function(links, normalize_schema = TRUE, deduplicate = FALSE){

  ecd_files = lapply(links, \(x){

    one_file = arrow::read_parquet(x)

    one_file = harmonize_ecd_date(one_file)

    if(isTRUE(normalize_schema)) one_file = normalize_ecd_schema(one_file)

    one_file

  })

  ecd_data = vctrs::vec_rbind(!!!ecd_files)

  if(isTRUE(deduplicate)) ecd_data = deduplicate_ecd(ecd_data)

  ecd_data

}


#' Known problems with a published release
#'
#' Keyed by release version and then by the file name of the country asset. These
#' are defects in the published data rather than in this package, so they are
#' reported to the user on load and removed here as the data is corrected.
#'
#' keywords @internal
#' @returns A named list of known issues for a release
#' @noRd

ecd_known_issues = function(ecd_version = '1.0.1'){

  issues = list(
    `1.0.0` = list(
      ecuador = 'ecuador.parquet and dominican_republic.parquet hold the same pooled corpus. Roughly 90% of the rows labelled Ecuador come from Dominican government sites.',
      dominican_republic = 'dominican_republic.parquet shares its corpus with ecuador.parquet. Roughly 21,000 rows attributed to Luis Abinader come from Ecuadorian government sites.',
      venezuela = 'venezuela.parquet text is mis-decoded (UTF-8 read as latin-1) in nearly every row, e.g. "Rep\u00c3\u00bablica" for "Rep\u00fablica".',
      jamaica = 'Every url in jamaica.parquet has the host concatenated onto an already absolute link, so none of them resolve.',
      india = 'india.parquet holds 7.97 million rows from 3,029 distinct urls. About 99% are exact duplicates. Consider deduplicate = TRUE.',
      denmark = 'denmark.parquet holds 4.8 million rows from 2,658 distinct urls. About 99% are exact duplicates. Consider deduplicate = TRUE.'
    ),
    `1.0.1` = list(
      colombia = 'Every url in colombia.parquet is a YouTube link rather than an official record, and it is not stated whether the text is an official transcript or an auto-generated caption track.',
      russia = 'url is 100% null in russia.parquet, and the text is the English-language kremlin.ru edition rather than the Russian original.',
      united_states_of_america = 'executive in united_states_of_america.parquet is unreliable: the Obama/Trump handover is dated 2016-01-20 rather than 2017-01-20 and Gerald R. Ford\'s rows run to 1996. type also holds president names, and language is 100% null.',
      venezuela = '100 rows of venezuela.parquet could not be repaired: a byte was lost at ingest, so the mis-decoded text does not round-trip.',
      ecuador = 'ecuador.parquet covers 2023-11-23 to 2024-03-19 only (2,236 documents, Daniel Noboa). The wider span in 1.0.0 was an artefact of a corpus pooled with the Dominican Republic.',
      dominican_republic = 'dominican_republic.parquet ends 2020-08-16 and is almost entirely Danilo Medina. There is no Luis Abinader corpus.',
      austria = 'Executive terms overlap in austria.parquet: some documents are credited to the wrong leader.',
      brazil = 'Executive terms overlap in brazil.parquet: some documents are credited to the wrong leader.',
      chile = 'Executive terms overlap in chile.parquet: some documents are credited to the wrong leader.',
      denmark = 'Executive terms overlap in denmark.parquet: some documents are credited to the wrong leader.',
      greece = 'Executive terms overlap in greece.parquet: some documents are credited to the wrong leader.',
      israel = 'Executive terms overlap in israel.parquet: some documents are credited to the wrong leader.',
      italy = 'Executive terms overlap in italy.parquet, and some values are composite (\'Romano Prodi/Massimo D\'Alema\'), so they will not group or join.'
    )
  )

  issues[[ecd_version]]

}


#' Releases whose full_ecd.parquet does not reconcile against the country assets
#'
#' keywords @internal
#' @returns A named list of messages, keyed by release version
#' @noRd

ecd_full_ecd_issues = function(){

  list(
    `1.0.0` = 'full_ecd.parquet in 1.0.0 contains Ecuador twice and a single empty row in place of Portugal\'s 64,522 documents. Load those two countries individually.'
  )

}


#' Tell the user about known problems with what they just asked for
#'
#' Called outside the memoised path so the warning is not swallowed by the cache
#' after the first call in a session.
#'
#' keywords @internal
#' @returns No return value, called for the message it prints
#' @noRd

warn_known_issues = function(links = NULL, ecd_version = '1.0.1', full_ecd = FALSE){

  if(isTRUE(full_ecd)){

    ## keyed by version: 1.0.1 rebuilt full_ecd.parquet from the country assets,
    ## so warning about it there would be wrong.
    full_issue = ecd_full_ecd_issues()[[ecd_version]]

    if(!is.null(full_issue)) cli::cli_alert_warning(full_issue)

    return(invisible(NULL))

  }

  issues = ecd_known_issues(ecd_version)

  if(is.null(issues)) return(invisible(NULL))

  file_names = tools::file_path_sans_ext(basename(links))

  for (file_name in intersect(file_names, names(issues))) {

    cli::cli_alert_warning('Known issue in {ecd_version}: {issues[[file_name]]}')

  }

  invisible(NULL)

}
