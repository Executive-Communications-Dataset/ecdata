#' clear cache 
#' 
#' This function clears the moised cache 
#' 
#' @rdname clear
#' @export
#' @return a success message after clearing the cache 
#' @examples
#' clear_cache()


clear_cache = \(){

  memoise::forget(load_ecd)
  
  cli::cli_alert_success('ecdata function cache cleared')


  invisible(TRUE)


}


#' @rdname clear_cache
#' @export

.clear_cache <- clear_cache



