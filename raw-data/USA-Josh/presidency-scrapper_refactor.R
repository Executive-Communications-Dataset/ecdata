library(ecdata)
library(rvest)
library(tidyverse)

# so an interesting quirk of the us presidency site is we can actually see what the last page is 

landing_page = tibble(
    first_pages = paste0('https://www.presidency.ucsb.edu/documents/app-categories/presidential?items_per_page=60&field_docs_start_date_time_value%5Bvalue%5D%5Bdate%5D=', seq(1963, 2024, by = 1)
))


examp = 'https://www.presidency.ucsb.edu/documents/app-categories/presidential?items_per_page=60&field_docs_start_date_time_value%5Bvalue%5D%5Bdate%5D=2020&page=0'

read_html(examp) |>
    html_element('li.pager-last > a') |>
    html_attr('href') |>
    basename() -> check


str_extract(check, '\\d+$')

get_page_numbers = \(link, base = 'https://www.presidency.ucsb.edu/documents/app-categories/presidential?items_per_page=60&field_docs_start_date_time_value%5Bvalue%5D%5Bdate%5D='){

   end_page = read_html(link) |>
        html_element('li.pager-last > a') |>
        html_attr('href') |>
        basename() |>
        str_extract('\\d+$') 

    out = tibble(year = str_extract(link, '\\d{4}'),
                 links = paste0(base,year,'&page=',seq(0, as.numeric(end_page))),
                )

    cat('Done scraping', unique(out$year), sep = '\n')
    Sys.sleep(10)

    return(out)

}



get_links = map(landing_page$first_pages, \(x) get_page_numbers(x))

page_links = get_links |>
  list_rbind() |>
  rowwise() |>
  mutate(year = as.integer(year),
        links = ifelse(year != 2020, gsub("(?<=%5Bdate%5D=)\\d{4}", as.character(year), links, perl = TRUE), links)) |>
  ungroup()

write_csv(page_links, 'raw_data/landing_pages.csv')

page_check = page_links$links[1]

href = read_html(page_check) |>
  html_elements('.field-title a') |>
  html_attr('href')


date = read_html(page_check) |>
  html_elements('.date-display-single') |>
  html_text()

title = read_html(page_check) |>
  html_elements('.field-title a') |>
  html_text()


get_links = \(links){


  href = read_html(links) |>
  html_elements('.field-title a') |>
  html_attr('href')


date = read_html(links) |>
  html_elements('.date-display-single') |>
  html_text()

title = read_html(links) |>
  html_elements('.field-title a') |>
  html_text()
  
out = tibble(link = paste0('https://www.presidency.ucsb.edu/', href),
             date = date,
            title = title)
  
  cat('Done Scraping', links, sep = '\n')

  Sys.sleep(10)

  return(out)
  
}

pos_links = possibly(get_links)

page_links = read_csv('raw_data/landing_pages.csv')


test = page_links |>
  slice_sample(n = 5)


check = map(test$links, \(x) get_links(x))

table(page_links$year)

get_links = map(page_links$links, \(x) pos_links(x)) 

# problems = which(lengths(get_links) == 0)



links_to_scrape$link[1]

test = links_to_scrape |>
  slice_sample(n = 3)

text = read_html(test$link[1]) |>
  html_elements('.field-docs-content p') |>
  html_text()



get_type = \(link){
  out = read_html(link) |>
    html_element(xpath = '/html/body/div[2]/div[4]/div/section/div/section/div/div/div[2]/div[1]/div[3]/a') |>
    html_text()

   Sys.sleep(5)
  return(out)
}

get_text = \(link){
  out = read_html(link) |>
    html_elements('.field-docs-content p') |>
    html_text()

  Sys.sleep(5)
  return(out)
}

get_president =  \(link){
  out = read_html(link) |>
  html_elements('.diet-title a') |>
  html_text()

Sys.sleep(1)
return(out)
}


links_to_scrape = read_csv('raw_data/links_data.csv') |>
  mutate(link = str_remove(link, 'documents/'))

pos_pres = possibly(get_president)
pos_type = possibly(get_type)
pos_text = possibly(get_text)

raw_data = tibble(
  date = NA,
  title = NA, 
  url = NA,
  type = NA,
  executive = NA,
  text = NA
)

write_csv(raw_data, 'raw_data/usa_statements.csv')

pres_dat = pmap(list(
  links_to_scrape$date,
  links_to_scrape$title,
  links_to_scrape$link
), \(date, title, link){
  cat('Scraping', link, sep = '\n')
  out = tibble(
    date = date,
    title = title,
    url = link, 
    executive = pos_pres(link),
    type = pos_type(link),
    text = pos_text(link)
  )
  write_csv(out, 'raw_data/usa_statements.csv', append = TRUE)
  out
})

check = bring_together$url


rescrape_two = landings |>
  filter(!link %in% check) 

rescrapes_two =  pmap(list(
  rescrape_two$date,
  rescrape_two$title,
  rescrape_two$link
), \(date, title, link){
  cat('Scraping', link, sep = '\n')
  out = tibble(
    date = date,
    title = title,
    url = link, 
    executive = pos_pres(link),
    type = pos_type(link),
    text = pos_text(link)
  )
  write_csv(out, 'raw_data/rescrapes.csv', append = TRUE)
  out
})




check_these = rescrape_two |>
  slice(1:7)

check = read_html(check_these$link[1]) |>
  html_elements('#block-system-main .field-docs-content > ol') |>
  html_text()


get_text_two = \(link){
    out = read_html(link) |>
      html_elements('#block-system-main .field-docs-content > ol') |>
      html_text()
  
    Sys.sleep(1)
    return(out)
  }
  
rescrapes_two =  pmap(list(
    check_these$date,
    check_these$title,
    check_these$link
  ), \(date, title, link){
    cat('Scraping', link, sep = '\n')
    out = tibble(
      date = date,
      title = title,
      url = link, 
      executive = pos_pres(link),
      type = pos_type(link),
      text = get_text_two(link)
    )
    write_csv(out, 'raw_data/rescrapes.csv', append = TRUE)
    out
  }) |>
  list_rbind()
  


us_data_scraped = rescrapes_two |>
  list_rbind() |>
  bind_rows(bring_together) |>
  mutate(date = mdy(date),
         country = 'United States of America',
         isonumber = countrycode(sourcevar = country,
          origin = 'country.name',
         destination = 'iso3n'),
gwc = countrycode(sourcevar = isonumber,
   origin = 'iso3n',
   ## gledistch ward country codes for hong kong are na 
   ## because well ..
   destination = 'gwc'),
cowcodes = countrycode(sourcevar = country,
       origin = 'country.name',
       destination = 'cowc'),
polity_v = countrycode(sourcevar = country,
        origin = 'country.name',
       destination = 'p5c'),
polity_iv = countrycode(sourcevar = country,
        origin = 'country.name',
       destination = 'p4c'),
vdem = countrycode(sourcevar = country,
  origin = 'country.name',
  destination = 'vdem'),
year_of_statement = year(date),
saving_name = 'united_states_of_america') |>
  arrange(date)



full_ecd = ecdata::load_ecd(full_ecd = TRUE)




sans_us = full_ecd |>
  filter(country != 'United States of America') |>
  bind_rows(us_data_scraped) |>
  group_by(country) |>
  arrange(date, .by_group = TRUE)