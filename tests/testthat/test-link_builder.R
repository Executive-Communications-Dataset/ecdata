test_that('checking the link building function',
{

## we want to test to see what happens when we feed the linkbuilder 
## a bad link 
  
  
objs = link_builder(country = 'United States of America', ecd_version = '1.0.0')
  
expect_equal(objs, 'https://github.com/Executive-Communications-Dataset/ecdata/releases/download/1.0.0/united_states_of_america.parquet')
  
  
obs_two = link_builder(country = c('Argentina', 'Turkey', 'Czechia'), ecd_version = '1.0.0')
  
link_vec = c('https://github.com/Executive-Communications-Dataset/ecdata/releases/download/1.0.0/argentina.parquet',
             'https://github.com/Executive-Communications-Dataset/ecdata/releases/download/1.0.0/czechia.parquet',
            'https://github.com/Executive-Communications-Dataset/ecdata/releases/download/1.0.0/turkey.parquet')
  
expect_equal(obs_two, link_vec)  


})


test_that('the aliases we document all build the same link', {

  korea = 'https://github.com/Executive-Communications-Dataset/ecdata/releases/download/1.0.0/republic_of_korea.parquet'

  for (alias in c('Republic of Korea', 'South Korea', 'KOR', 'KR', 'south korea')) {

    expect_equal(link_builder(country = alias, ecd_version = '1.0.0'), korea)

  }

  britain = 'https://github.com/Executive-Communications-Dataset/ecdata/releases/download/1.0.0/united_kingdom.parquet'

  for (alias in c('United Kingdom', 'Great Britain', 'GBR', 'GB', 'UK')) {

    expect_equal(link_builder(country = alias, ecd_version = '1.0.0'), britain)

  }

})


test_that('a country is only ever asked for once', {

  ## Azerbaijan and Russia are in the dictionary twice under each alias
  links = link_builder(country = c('Azerbaijan', 'AZE', 'Russia', 'RU'),
                       ecd_version = '1.0.0')

  expect_equal(length(links), 2L)

  expect_equal(anyDuplicated(links), 0L)

})


test_that('a language builds one link per country that publishes in it', {

  links = link_builder(language = 'Portuguese', ecd_version = '1.0.0')

  expect_equal(length(links), 2L)

  expect_true(any(grepl('brazil.parquet', links, fixed = TRUE)))

  expect_true(any(grepl('portugal.parquet', links, fixed = TRUE)))

})
