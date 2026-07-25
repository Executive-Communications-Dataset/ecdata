test_that('the country dictionary has no duplicate rows', {

  dictionary = country_dictionary()

  expect_equal(anyDuplicated(dictionary), 0L)

  ## Azerbaijan and Russia used to appear twice under every alias
  azerbaijan = dictionary[dictionary$file_name == 'azerbaijan', ]

  expect_equal(nrow(azerbaijan), 2L)

  russia = dictionary[dictionary$file_name == 'russia', ]

  expect_equal(nrow(russia), 2L)

})


test_that('every country in the release is in the dictionary exactly once per alias', {

  dictionary = country_dictionary()

  expect_equal(length(unique(dictionary$file_name)), 42L)

  ## India publishes in two languages, everyone else in one
  languages_per_country = tapply(dictionary$language, dictionary$file_name,
                                 \(x) length(unique(x)))

  expect_equal(unname(languages_per_country[['india']]), 2L)

  expect_true(all(languages_per_country[names(languages_per_country) != 'india'] == 1L))

})


test_that('Portuguese is spelled correctly and the old spelling still works', {

  dictionary = country_dictionary()

  expect_true('Portuguese' %in% dictionary$language)

  expect_false('Portugese' %in% dictionary$language)

  expect_equal(fold_language('Portugese'), 'portuguese')

  expect_equal(
    link_builder(language = 'Portugese', ecd_version = '1.0.0'),
    link_builder(language = 'Portuguese', ecd_version = '1.0.0')
  )

})


test_that('the exported country dictionary matches the internal one', {

  expect_equal(anyDuplicated(ecd_country_dictionary), 0L)

  expect_false('Portugese' %in% ecd_country_dictionary$language)

  expect_setequal(
    ecd_country_dictionary$file_name,
    country_dictionary()$file_name
  )

})
