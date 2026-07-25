#' ECD country dictionary
#' A data dictionary with the countries in our dataset and their corresponding file names on Github
#'
#' a data frame with 43 rows and 7 columns
#' \describe{
#'   \item{name_in_dataset}{Name of the country in the dataset}
#'    \item{file_name}{Name of the parquet files on GitHub}
#'    \item{language}{Language the country publishes in}
#'    \item{abbr_three_letter}{Three letter abbreviation for the country}
#'    \item{abbr_two_letter}{Two letter abbreviation for the country}
#'    \item{other_valid_inputs}{Other country names load_ecd accepts}
#'    \item{common_abr}{Other abbreviations load_ecd accepts}}
#'
#' @source The Executive Communications Dataset 
#' 


"ecd_country_dictionary"


#' ECD data dictionary
#' a data dictionary of the columns in our dataset 
#' 
#' \describe{
#'   \item{country}{name of a country in our dataset}
#'   \item{date}{date of statement}
#'   \item{title}{title of the statement}
#'   \item{text}{text of the statement}
#'   \item{url}{url of the statement}
#'   \item{file}{name of the file in the replication repo}}
#' 
#' @source The Executive Communications Dataset
 

"ecd_data_dictionary"