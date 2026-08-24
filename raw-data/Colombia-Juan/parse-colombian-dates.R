library(tidyverse)

raw_dat = read_csv('ColombiaSpeeches.csv')

parsed_dates = raw_dat |>
  mutate(date_fix = mdy(date))




fix_dates = parsed_dates |>
  filter(is.na(date_fix)) |>
  mutate(date_fix = dmy(date, locale = 'es_ES.UTF-8'),
         months_time_frame = ifelse(str_detect(date, 'month'), str_extract(date, '\\d+'), NA),
         years_time_frame = ifelse(str_detect(date, 'year'), str_extract(date, '\\d+'), NA),
         across(ends_with('time_frame'), \(x) as.numeric(x)), 
         date_manual = case_when(
          !is.na(months_time_frame) ~ as_date(Sys.Date()) %m-% months(months_time_frame),
          !is.na(years_time_frame) ~ as_date(Sys.Date()) - years(years_time_frame)),
        date_fix_two = coalesce(date_fix, date_manual)) |>
       select(url, date_fix_two) |>
       ## one row per url, or the join below multiplies every row of that url
       distinct(url, .keep_all = TRUE)

completed_dates = parsed_dates |>
  left_join(fix_dates, join_by(url)) |>
  mutate(date = coalesce(date_fix, date_fix_two)) |>
  select(-c(date_fix, date_fix_two))

stopifnot(nrow(completed_dates) == nrow(parsed_dates))

completed_dates |>
  filter(is.na(date))

glimpse(completed_dates)


write_csv(completed_dates, 'colombian_statements.csv')


