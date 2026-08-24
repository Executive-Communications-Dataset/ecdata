pacman::p_load(arrow, rvest, tidyverse)

links_dat = read_parquet('rescraped_links.parquet')

exploded = links_dat |>
  unnest(cols = everything())

table(exploded$cat)



scraping_links = exploded |>
  filter(cat %in% c('Article', 'Communiqué de presse', 'Discours', 'Conseil des ministres'))




speech_scrapper = \(links, user_agent ='for questions please contact Ryan Carlin at rcarlin@gsu.edu'){

 intro = polite::bow(links, paste(user_agent))
  
  text = read_html_live(links) |>
    html_elements('#main .container p') |>
    html_text()  |>
    as_tibble() |>
    rename(text = value)

  pdf_link = read_html_live(links) |>
    html_elements('#main .cta-module__link a') |>
    html_attr('href') 
  
  if (length(pdf_link) != 0 ) {
    pdf_dat = pdf_link |>
      as_tibble() |>
      rename(pdf_link = value)
     
    bound_dat = bind_cols(text, pdf_dat, url = links)

  }
  else{
    bound_dat = bind_cols(text, url = links)
  }

cat('Done Scraping:', links, '\n')
  
Sys.sleep(sample(5:8, 1))

return(bound_dat)

}
 


make_sure_unique = scraping_links |>
  distinct(link) 



french_statements = map(make_sure_unique$link, \(x) speech_scrapper(x))

## umm this is really just a bastille day celebration thing 
make_sure_unique$link[43]
## lets make this a possibly issue 

poss_scrape = possibly(speech_scrapper)

french_statements = map(make_sure_unique$link, \(x) poss_scrape(x))

rescrape = which(lengths(french_statements) == 0)


bound_statements = french_statements |>
  list_rbind()

pdf_scrape = bound_statements |>
  filter(!is.na(pdf_link)) |>
  distinct(pdf_link, .keep_all = TRUE)


scraped_pdfs_data = map(pdf_scrape$pdf_link, \(x) poss_scrape(x))

bound_pdfs = scraped_pdfs_data |>
  list_rbind() |>
  rename(pdf_file = pdf_link)

write_csv(bound_pdfs, 'pdfs_links.csv')


join_data = pdf_scrape |>
  select(-text) |>
  left_join(bound_pdfs, join_by(pdf_link == url))


## bound_statements is one row per HTML paragraph and join_data one row per PDF
## paragraph, so joining them on (url, pdf_link) paired every HTML paragraph with
## every PDF paragraph: N x M rows per document. Stack them instead and mark
## which source each row came from.
joined_statements_pdf = bind_rows(
    bound_statements |> mutate(source = 'html'),
    join_data        |> mutate(source = 'pdf')
  ) |>
  mutate(text = str_squish(text))

stopifnot(nrow(joined_statements_pdf) == nrow(bound_statements) + nrow(join_data))


scraping_links_small = scraping_links |>
  select(subject, date, link) |>
  mutate(subject = str_squish(subject))

combined_dat = joined_statements_pdf |>
  left_join(scraping_links_small, join_by(url == link)) |>
  mutate(fix_date = dmy(date, locale = 'fr_FR'),
         fix_two = mdy(date), 
        date = coalesce(fix_date, fix_two)) 

cleanup = combined_dat |>
  select(date, subject, text, url)


write_csv(cleanup, 'french_statements.csv')


make_sure_unique_rescrape = make_sure_unique |>
  mutate(id = row_number()) |>
  filter(id %in% rescrape) 


text = read_html_live(make_sure_unique_rescrape$link[3]) |>
  html_elements('#moduleAnchor-228330 p') |>
  html_text()  |>
  as_tibble() |>
  rename(text = value)


pdf_link = read_html_live(make_sure_unique_rescrape$link[3]) |>
     html_element('#moduleAnchor-228330 .cta-module__link a') |>
     html_attr('href') 
   


     speech_scrapper_two = \(links, user_agent ='for questions please contact Ryan Carlin at rcarlin@gsu.edu'){

      intro = polite::bow(links, paste(user_agent))
       
       text = read_html_live(links) |>
        html_elements('#moduleAnchor-228330 p') |>
         html_text()  |>
         as_tibble() |>
         rename(text = value)
     
       pdf_link = read_html_live(links) |>
        html_element('#moduleAnchor-228330 .cta-module__link a') |>
         html_attr('href') 
       
       if (length(pdf_link) != 0 ) {
         pdf_dat = pdf_link |>
           as_tibble() |>
           rename(pdf_link = value)
          
         bound_dat = bind_cols(text, pdf_dat, url = links)
     
       }
       else{
         bound_dat = bind_cols(text, url = links)
       }
     
     cat('Done Scraping:', links, '\n')
       
     Sys.sleep(sample(5:8, 1))
     
     return(bound_dat)
     
     }

rescrape_dat = map(make_sure_unique_rescrape$link, \(x) speech_scrapper_two(x))

bound_data_two = rescrape_dat |>
  list_rbind()

joined_rescrape = bound_data_two |>
  left_join(scraping_links_small, join_by(url == link)) |>
  mutate(date = mdy(date))


all_together = bind_rows(cleanup, joined_rescrape)


write_csv(all_together, 'french_statements.csv')

raw_data = read_csv('french_statements.csv')

joinin_links = exploded |>
  select(link, cat)

add_meta_data = raw_data |>
  left_join(joinin_links, join_by(url == link), multiple = 'first') |>
  mutate(type = case_match(cat,
           'Communiqué de presse' ~ 'Press Release',
          'Conseil des ministres' ~ 'Council of Ministers',
        'Discours' ~ 'Speech',
      .default = cat)) |>
    select(-pdf_link, -cat) 

table(add_meta_data$type)

glimpse(add_meta_data)

write_csv(add_meta_data, 'french_statements_add_meta.csv')
