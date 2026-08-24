library(tidyverse)
library(rvest)
library(httr)

raw_links = read_csv("scraped_links_df.csv")



clean_links = raw_links |>
  distinct(links_scraped) |>
mutate(extract_links = gsub("javascript:move_page\\('[0-9]+'{1,2},'(.+)'\\)", "\\1", links_scraped),
fix_links = paste0("https://www.president.go.kr", extract_links),
fix_links = str_remove_all(fix_links, ";"))



clean_links = links_dat |>
mutate(extract_links = gsub("javascript:move_page\\('[0-9]+'{1,2},'(.+)'\\)", "\\1", links_scraped),
fix_links = paste0("https://www.president.go.kr", extract_links),
fix_links = str_remove_all(fix_links, ";"))

write_csv(clean_links, 'scraped_links.df')


statement_scrapper = function(links){
  check_links = httr::GET(links)
  introduce = polite::bow(links, user_agent = "If you have any questions please contact Ryan Carlin at rcarlin@gsu.edu")
  sleepy_time = sample(5:8, 1)
 status_link = status_code(check_links )

cat("Scraping:", links, "going to sleep for",
sleepy_time, "\n")

Sys.sleep(sleepy_time)

if(status_link != 200){
  bad_links = links 
  bad_link_df = tibble(link = NA)
  error_link_df = rbind(bad_link_df, bad_links)

  return(error_link_df)

} else{



get_title = read_html(links) |>
html_elements('.txtL') |>
html_text() |>
as_tibble() |>
rename(statement_title = value)

link_df = bind_cols(get_title, url = links)

return(link_df)


}


}

korean_statements = map(links_to_scrape, statement_scrapper)


korean_statements_df = korean_statements |>
list_rbind() |>
filter(nchar(text) > 1)

glimpse(korean_statements_df)

write_csv(korean_statements_df, "korean_statements.csv")


raw_dat = read_csv('korean_statements.csv')

links_dat = read_csv('scraped_links_df.csv')
## we should just do this for unique titles 
get_bring_in = map(clean_links$fix_links, \(x) statement_scrapper(x))


rescrape_these = which(lengths(get_bring_in) == 0)

## scraped_links.df holds 377 rows for 301 distinct urls: 76 appear twice. The
## duplicates land on BOTH sides of the join below, multiplying every paragraph
## by 2 x 2 = 4. distinct() on each side is what the note above meant.
bound_titles = get_bring_in |>
  list_rbind() |>
  mutate(clean_titles = str_squish(statement_title)) |>
  select(clean_titles, url) |>
  distinct(clean_titles, url)


joining_data = raw_dat |>
  mutate(statement_title = str_squish(statement_title)) 


joining_data = distinct(joining_data)

joined_data = joining_data |>
  left_join(bound_titles, join_by(statement_title == clean_titles)) |>
  mutate(date = ymd(date))

stopifnot(nrow(joined_data) == nrow(joining_data))


write_csv(joined_data, 'cleaned_korean_statements.csv')


