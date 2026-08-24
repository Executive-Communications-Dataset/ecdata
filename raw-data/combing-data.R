pacman::p_load(
  arrow,
  countrycode,
  piggyback,
  tidyverse
)



files = fs::dir_info(recurse = TRUE, glob = '*.csv')

add_country_names = files |>
   filter(str_detect(path, 'statements')) |>
   mutate(country_name = str_extract(path, '^[^/]+'))


get_latest_files = add_country_names |>
   mutate(latest_file = max(modification_time), .by = country_name) |>
   filter(modification_time == latest_file) |>
   mutate(country_name = str_extract(path, '^[^/]+'), 
          country_name = str_remove(country_name, "-.*"),
          country_name = str_to_title(country_name), 
        country_name = case_when(country_name == 'Usa' ~ "United States of America",
                                 country_name == 'Uk' ~ 'United Kingdom',
                                 country_name == 'Hong' ~ 'Hong Kong',
                                 country_name == 'South' ~ 'Republic of South Korea',
                                country_name == 'Czech' ~ 'Czechia',
                                country_name == 'Phillipines' ~ 'Philippines',
                                country_name == 'Venzuela' ~ 'Venezuela',
                                 .default = country_name))





names_vec = get_latest_files$country_name

readin_data = map(get_latest_files$path, \(x) read_csv(x)) 

names(readin_data) = names_vec

bind_data = readin_data |>
  list_rbind(names_to = 'country')



clean_up = bind_data |>
  mutate(title = coalesce(title, subject, statement_title),
         text = coalesce(text, texts), 
        executive = coalesce(executive, exec_one, president),
        country = str_squish(country), 
        url = coalesce(url,links),
        file = coalesce(file, files)) 


add_identifiers = clean_up |>
  select(country:title, executive, type, language, file) |>
  mutate(isonumber = countrycode(sourcevar = country,
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
      year_of_statement = year(date)) |>
      group_by(country) |>
  arrange(desc(date), .by_group = TRUE) |>
  ungroup()




write_csv(small, 'files_used_for_merging.csv')


if(!dir.exists('executive_statement_data')){
dir.create('executive_statement_data')}else{
  print('already created')
}




add_identifiers |>
  mutate(saving_name = str_replace_all(country, ' ', '_'),
         saving_name = str_squish(saving_name),
         saving_name = str_to_lower(saving_name)) |>
  group_by(saving_name) |>
  write_dataset('partioned-exec-data', existing_data_behavior = 'overwrite')



exec_data = open_dataset('partioned-exec-data') 

add_types = exec_data |>
  to_duckdb() |>
  ## there is only a limited amount of stringr support unfortunately
  ## there is probably a more databasy way to do that 
  ## at present that is a skill issue for me 
  mutate(fix_types = case_when(
    str_detect(url, 'proclamation') ~ 'Presidential Proclamation',
    str_detect(url, 'statement') ~ 'Press Statement',
    str_detect(url, 'speech|remarks|address|message|speeches|rede-') ~ 'Speech',
    str_detect(url, 'interview') ~ 'Interview',
    str_detect(url, 'executive') ~ 'Executive Order',
      .default = NA),
 type = str_squish(type),
 type = case_when(type == 'Gov_decisions' ~ 'Government Decisions',
  type == 'Comunicado' ~ 'Communication' ,
  type %in% c('Pressemelding', 'press release') ~ 'Press Release',
  type %in% c('Nyhet', 'Nyheit') ~ 'News',
  type %in% c('Discurso del Presidente', 'Discurso') ~ 'Speech',
  type == 'Entrevista' ~ 'Interview',
  type == 'Gov_decisions' ~ 'Government Decisions',
  country == 'Venezuela' ~ 'News',
 .default = type),
 language = case_when(
  country %in% c('Australia', 'Azerbaijan', 'Canada', 'Jamaica',  'Nigeria', 'New Zealand', 'United Kingdom', 'United States of America', 'Russia') ~ 'English',
  country %in% c('Argentina', 'Chile', 'Bolivia', 'Colombia', 'Ecuador', 'Mexico', 'Spain', 'Uruguay', 'Costa Rica',
                  'Venezuela') ~ 'Spanish',
  country %in% c('Portugal', 'Brazil') ~ 'Portuguese',
  country %in% c('Austria', 'Germany') ~ 'German',
  country == 'Hong Kong' ~ 'Chinese',
  country %in% c('Republic of Korea', 'Republic of South Korea') ~ 'Korean',
  country == 'Georgia' ~ 'Georgian',
  country == 'Denmark' ~ 'Danish', 
  country == 'France' ~ 'French',
  country == 'Greece' ~ 'Greek',
  country == 'Hungary' ~ 'Hungarian',
  country == 'Iceland' ~ 'Icelandic', 
  country == 'Indonesia' ~ 'Indonesian',
  country == 'Israel' ~ 'Hebrew', 
  country == 'Italy' ~ 'Italian',
  country == 'Japan' ~ 'Japanese',
  country == 'Norway' ~ 'Norwegian',
  country == 'Philippines' ~ 'Filipino',
  country == 'Poland' ~ 'Polish',
  country == 'Turkey' ~ 'Turkish',
  country == 'Czechia' ~ 'Czech',
  .default = language
)) |>
  collect()




fix_types = add_types |>
  mutate(
    type = str_to_title(type),
    fix_types = str_to_title(fix_types),
  type = data.table::fcoalesce(type, fix_types),
     language = str_to_title(language)) |>
  select(-fix_types)




write_parquet(fix_types, 'handofftopolars/exec_small.parquet')



exec_data = read_parquet('executive_statement_data/full_executive_statement_data_v2.parquet')

fix_up = exec_data |>
  group_by(country) |>
  arrange(date, .by_group = TRUE) |>
  ungroup() |>
  filter(!is.na(text))


  

write_parquet(fix_up, 'executive_statement_data/full_executive_statement_data_v2.parquet')

fix_up |>
  mutate(saving_name = str_replace_all(country, ' ', '_'),
         saving_name = str_squish(saving_name),
         saving_name = str_to_lower(saving_name)) |>
  group_by(saving_name) |>
  write_dataset('partioned-exec-data', existing_data_behavior = 'overwrite')







## this is just for the manuscript. Set ECD_MANUSCRIPT_DIR to write it; the
## build no longer depends on one person's Dropbox path existing.
manuscript_dir = Sys.getenv('ECD_MANUSCRIPT_DIR', unset = NA)

if (!is.na(manuscript_dir) && dir.exists(manuscript_dir)) {
  write_parquet(fix_up, file.path(manuscript_dir, 'full_ecd.parquet'))
}


if(!dir.exists('piggyback-release-data')){
  dir.create('piggyback-release-data')
}

## Derive the filename from the country inside the split rather than pairing two
## separately-ordered vectors by position. split() orders by factor level and
## distinct() by row order; walk2() paired them element by element, so if those
## orders ever disagreed a country's documents were written to another country's
## file -- silently, because the only guard was a length comparison that was
## printed rather than asserted.
slugify = \(x) str_to_lower(str_squish(str_replace_all(x, ' ', '_')))

make_splits = split(fix_up, fix_up$country)

stopifnot(length(make_splits) == n_distinct(fix_up$country))

iwalk(make_splits, \(data, country) {
  write_parquet(data, file.path('piggyback-release-data', paste0(slugify(country), '.parquet')))
})

write_parquet(fix_up, 'piggyback-release-data/full_ecd.parquet')




## Releases live on the organisation's repository, not a personal one. Override
## with ECD_RELEASE_REPO / ECD_RELEASE_TAG rather than editing this line.
release_repo = Sys.getenv('ECD_RELEASE_REPO', unset = 'Executive-Communications-Dataset/ecdata')
release_tag  = Sys.getenv('ECD_RELEASE_TAG',  unset = '1.0.0')

piggyback::pb_release_create(release_repo, tag = release_tag)



country_files = list.files('piggyback-release-data', pattern = '*.parquet', full.names = TRUE)

walk(country_files, \(x) pb_upload(x, repo = release_repo, tag = release_tag))





