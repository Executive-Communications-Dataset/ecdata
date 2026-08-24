pacman::p_load(tidyverse, rvest, polite)

austrian_links = read_csv("austrian_links.csv")


statement_scrapper = function(links){

  introduce = bow(links, user_agent = "For any questions contact Ryan Carlin at rcarlin@gsu.edu")
  
  
  
  get_text = read_html(links) |>
  html_elements('p') |>
  html_text() |>
  as_tibble()  |>
  rename(text = value)
  
  
  getdate = read_html(links) |>
  html_elements('.press_location_time') |>
  html_text() |>
  as_tibble() |>
  rename(date = value)
  
  getsub = read_html(links) |>
  html_elements('h2') |>
  html_text() |>
  as_tibble() |>
  rename(subject = value)
  
  
  text_dat = bind_cols(get_text, getdate, getsub, url = links) 
                    
  
  
  
  sleepy_time = sample(5:8,1)
  
  cat("Done scraping", links, "going to sleep for", sleepy_time,
  "seconds", "\n")
  
  Sys.sleep(sleepy_time)
  
  return(text_dat)
  
    
  }



  austrian_statements = map(austrian_links$url, possibly(statement_scrapper))
  

  austrian_statements_df = austrian_statements |>
    list_rbind() |>
    filter(str_detect(text, "Telefon|Email", negate = TRUE))


  links_scraped_1 = austrian_statements_df |>
    distinct(url) |>
    deframe()
    
    
    rescrape_these = austrian_links |>
    filter(!url %in% links_scraped_1) |>
    distinct(url) |>
    slice(1) |>
    deframe()




  get_subject = read_html(rescrape_these) |>
    html_elements('h2') |>
    html_text() |>
    as_tibble() |>
    slice(1) |>
    rename(subject = value)
    
    get_date = read_html(rescrape_these) |>
    html_elements('.press_location_time') |>
    html_text() |>
    as_tibble() |>
    rename(date = value)
    
    
    get_text = read_html(rescrape_these) |>
    html_elements('p') |>
    html_text() |>
    as_tibble() |>
    rename(text = value)
    
    text_to_bind = bind_cols(get_text, get_date, get_subject) |>
    mutate(url = rescrape_these)
    
    
    
    ## the two passes overlap, so documents in both appeared twice. This
    ## statement was also written out twice, identically; once is enough.
    austrian_statements_bound = bind_rows(austrian_statements_df, text_to_bind) |>
        distinct() |>
        mutate(date = str_squish(date),
              date_fix = dmy(date, locale = 'de_AT'))
    
    
    check = austrian_statements_bound |>
      filter(is.na(date_fix)) |>
      distinct(url, .keep_all = TRUE) |>
      mutate(date_fix = str_replace(date, 'Januar', '01'),
             date_fix_two = dmy(date_fix)) |>
      select(url, date_fix_two)
    
    fixed_dates = austrian_statements_bound |>
        left_join(check, join_by(url)) |>
        mutate(date = coalesce(date_fix, date_fix_two)) |>
        select(-c(date_fix, date_fix_two))
    
    glimpse(fixed_dates)
    
    write_csv(fixed_dates, "austrian_statements.csv")
    