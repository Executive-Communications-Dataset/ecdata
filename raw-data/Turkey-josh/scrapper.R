library(rvest)
library(tidyverse)

url = 'https://www.tccb.gov.tr/receptayyiperdogan/konusmalar/?&page='

polite::bow(url_df$urls[1], user_agent = 'hi')


url_df = tibble(urls = paste0(url, seq(1,41,1)))


polite::bow('https://www.tccb.gov.tr/receptayyiperdogan/konusmalar/?&page=1')



links = session |>
  html_elements('#divContentList a') |>
  html_attr('href')


links_scrapper = \(links){


  
session = read_html_live(links)

links_dat = session |>
  html_elements('#divContentList a') |>
  html_attr('href') |>
  as_tibble() |>
  rename(links = value)

Sys.sleep(5)
  
cat("Done Scraping", links, '\n')
  
return(links_dat)
  
  
}

scrape_links = map(url_df$urls, \(x) links_scrapper(x))

links_scrape = list_rbind(scrape_links) |>
  mutate(links = paste0('https://www.tccb.gov.tr', links))



write_csv(links_scrape, 'speeches/links.csv')


speeches_tibble = tibble(links = paste0('https://www.tccb.gov.tr/receptayyiperdogan/mulakatlar/?&page=', seq(1,2,1)))


page_one = read_html_live(speeches_tibble$links[1]) |>
  html_elements('#divContentList a') |>
  html_attr('href') |>
  as_tibble() |>
  mutate(links = paste0('https://www.tccb.gov.tr', value)) |>
  select(-value)

page_two = read_html_live(speeches_tibble$links[2]) |>
  html_elements('#divContentList a') |>
  html_attr('href') |>
  as_tibble() |>
  mutate(links = paste0('https://www.tccb.gov.tr', value)) |>
  select(-value)


all_links = bind_rows(page_one, page_two) 

write_csv(all_links, 'interviews/interview_links.csv')


session  = read_html_live(links_scrape$links[1])

subject = session |>
  html_elements(xpath = '//*[@id="resDetay"]/h1/span') |>
  html_text()

subject

date = session |>
  html_elements(xpath = '//*[@id="resDetay"]/h6') |>
  html_text()

date

text =  session |>
  html_elements('#divContentArea p') |>
  html_text() |>
  str_squish()


speech_scrapper = \(links){

cat('scraping', links, '\n')

session  = read_html_live(links)

subject = session |>
  html_elements(xpath = '//*[@id="resDetay"]/h1/span') |>
  html_text() |>
  as_tibble() |>
  rename(subject = value)



date = session |>
  html_elements(xpath = '//*[@id="resDetay"]/h6') |>
  html_text() |>
  as_tibble() |>
  rename(date = value)


text =  session |>
  html_elements('#divContentArea p') |>
  html_text() |>
  str_squish() |>
  as_tibble() |>
  rename(text = value)
  
bound_dat = bind_cols(date, subject, text, url = links) 

Sys.sleep(5)
  
return(bound_dat)
  


}


poss_scrapper = possibly(speech_scrapper)

speech_dat = map(links_scrape$links, \(x) poss_scrapper(x))


bound_speeches = speech_dat |>
  list_rbind() |>
  mutate(date = dmy(date))

write_csv(bound_speeches, 'speeches/turkish_speeches.csv')


## lets go and grab the null 
nulls_rescrape = which(lengths(speech_dat) == 0)

links_scrape_index = links_scrape |>
  mutate(id = row_number()) |>
  filter(id %in% nulls_rescrape)

links_scrape_index$links[1]

rescrape = map(links_scrape_index$links, speech_scrapper)


rescrape_dat = rescrape |>
  list_rbind() |>
  mutate(date = dmy(date))

bound_speeches = bind_rows(bound_speeches, rescrape_dat) |>
  distinct() |>
  group_by(url) |>
  arrange(date, .by_group = TRUE) |>
  ungroup() |>
  mutate(type = 'speech')


write_csv(bound_speeches, 'speeches/turkish_speeches.csv')


session = read_html_live(all_links$links[1])


subject = session |>
  html_elements(xpath = '//*[@id="resDetay"]/h1/span') |>
  html_text()

date = session |>
  html_elements(xpath = '//*[@id="resDetay"]/h6') |>
  html_text()

text = session |>
  html_elements('#divContentArea p') |>
  html_text()


### cool it looks like we can jsut rerea

interview = map(all_links$links, \(x) poss_scrapper(x))


### lol the last one errored but we should just make sure that there arent more hiding 

session = speech_scrapper(all_links$links[94])

lone_dat = session |>
  mutate(date = dmy(date))

interview_dat = interview |>
  list_rbind() |>
  mutate(date = dmy(date),
        type = 'interview') |>
  bind_rows(lone_dat)

## the speech and interview link lists overlap, and the rescrape above appends
## rather than replaces, so documents were appearing up to four times.
all_together = bind_rows(bound_speeches, interview_dat) |>
  distinct()

write_csv(all_together, 'turkish_statements.csv')



