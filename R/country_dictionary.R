#' Country lookup table used to build download links
#'
#' keywords @internal
#' @returns a data frame with the country names, languages, and abbreviations for building links.
#' @noRd


## One row per country in the release. `abbrs` and `names` hold the accepted
## aliases for a country and `languages` the languages that country publishes
## in. The table `country_dictionary()` returns is the expansion of this spec:
## one row per language/abbreviation/name combination. Adding a country means
## adding a row here rather than editing four parallel run length encoded
## vectors, which is how the duplicate Azerbaijan and Russia rows crept in.

ecd_country_spec = \(){

  data.frame(
    file_name = c(
      "argentina", "australia", "austria", "azerbaijan", "bolivia", "brazil",
      "canada", "chile", "colombia", "costa_rica", "czechia", "denmark",
      "dominican_republic", "ecuador", "france", "georgia", "germany", "greece",
      "hong_kong", "hungary", "iceland", "india", "indonesia", "israel", "italy",
      "jamaica", "japan", "mexico", "new_zealand", "nigeria", "norway",
      "philippines", "poland", "portugal", "russia", "spain", "turkey",
      "united_kingdom", "uruguay", "venezuela", "united_states_of_america",
      "republic_of_korea"
    ),
    languages = c(
      "Spanish", "English", "German", "English", "Spanish", "Portuguese",
      "English", "Spanish", "Spanish", "Spanish", "Czech", "Danish",
      "Spanish", "Spanish", "French", "Georgian", "German", "Greek",
      "Chinese", "Hungarian", "Icelandic", "English;Hindi", "Indonesian",
      "Hebrew", "Italian",
      "English", "Japanese", "Spanish", "English", "English", "Norwegian",
      "Filipino", "Polish", "Portuguese", "English", "Spanish", "Turkish",
      "English", "Spanish", "Spanish", "English",
      "Korean"
    ),
    abbrs = c(
      "ARG;AR", "AUS;AU", "AUT;AT", "AZE;AZ", "BOL;BO", "BRA;BR",
      "CAN;CA", "CHL;CL", "COL;CO", "CRI;CR", "CZE;CZ", "DNK;DK",
      "DOM;DO", "ECU;EC", "FRA;FR", "GEO;GE", "DEU;DE", "GRC;GR",
      "HKG;HK", "HUN;HU", "ISL;IS", "IND;IN", "IDN;ID", "ISR;IL", "ITA;IT",
      "JAM;JM", "JPN;JP", "MEX;MX", "NZL;NZ", "NGA;NG", "NOR;NO",
      "PHL;PH", "POL;PL", "PRT;PT", "RUS;RU", "ESP;ES", "TUR;TR",
      "GBR;GB;UK", "URY;UY", "VEN;VE", "USA;US",
      "KOR;KR"
    ),
    names = c(
      "Argentina", "Australia", "Austria", "Azerbaijan", "Bolivia", "Brazil",
      "Canada", "Chile", "Colombia", "Costa Rica", "Czechia", "Denmark",
      "Dominican Republic", "Ecuador", "France", "Georgia", "Germany", "Greece",
      "Hong Kong", "Hungary", "Iceland", "India", "Indonesia", "Israel", "Italy",
      "Jamaica", "Japan", "Mexico", "New Zealand", "Nigeria", "Norway",
      "Philippines", "Poland", "Portugal", "Russia", "Spain", "Turkey",
      "United Kingdom;Great Britain", "Uruguay", "Venezuela",
      "United States of America;United States",
      "Republic of Korea;South Korea"
    ),
    stringsAsFactors = FALSE
  )

}


  country_dictionary = \(){

    spec = ecd_country_spec()

    split_aliases = \(x) strsplit(x, ";", fixed = TRUE)[[1]]

    rows = lapply(seq_len(nrow(spec)), \(i){

      combos = expand.grid(
        name_in_dataset = split_aliases(spec$names[i]),
        abbr = split_aliases(spec$abbrs[i]),
        language = split_aliases(spec$languages[i]),
        stringsAsFactors = FALSE
      )

      data.frame(
        file_name = spec$file_name[i],
        language = combos$language,
        abbr = combos$abbr,
        name_in_dataset = combos$name_in_dataset,
        stringsAsFactors = FALSE
      )

    })

    country_names = do.call(rbind, rows)

    for (i in 2:4) {

      country_names[[i]] = trimws(country_names[[i]])

    }

    ## a country should never appear twice under the same language, abbreviation
    ## and name. Azerbaijan and Russia used to, and those rows were visible to
    ## anyone who called this function.
    country_names = country_names[!duplicated(country_names), ]

    rownames(country_names) = NULL

    return(country_names)

  }
