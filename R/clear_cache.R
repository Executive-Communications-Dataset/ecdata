#' Clear function cache
#'
#' This function clears the memoised cache of all functions memoised by `ecdata`.
#'
#' @return A success message after clearing the cache.
#' @examples
#' \donttest{
#' clear_cache()
#' }
#' 
#' @export

clear_cache = \(){

  memoise::forget(load_ecd)
  
  cli::cli_alert_success('ecdata function cache cleared')


  invisible(TRUE)


}




