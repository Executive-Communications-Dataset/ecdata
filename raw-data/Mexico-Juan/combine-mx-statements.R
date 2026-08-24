library(tidyverse)

files = list.files(pattern = '*.csv')

files_list = map(files, \(x) read_csv(x))

names_vec = c('mex_2019', 'mex_2023', 'mex_2017')

names(files_list) = names_vec

list2env(files_list, envir = .GlobalEnv)

## it looks like the we have a spare 
## it loks like we just have a spare one in the mexico 2017 file 
## the problem is that it is the type of statement is in the 2017 file 

## the three yearly exports overlap, so a document covered by all of them
## appeared three times. distinct() after the bind, not before.
all_together = bind_rows(mex_2023, mex_2019, mex_2017) |>
  distinct() |>
  select(-...1) |>
  mutate(url = coalesce(url, summary_url)) |>
  select(-summary_url)

all_together$url[6] -> check

make_paragraphs_for_some = all_together |>
  separate_longer_delim(text, delim = '\r\r\n\r\r\n')





write_csv(all_together, 'mexico_statements.csv')


