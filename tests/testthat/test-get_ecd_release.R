test_that("Testing whether load_ecd fails nicely",


  {
     expect_error(

      load_ecd()

     )

    expect_error(
      load_ecd(country = 2.0)
    )

    expect_error(load_ecd(country = 'Narnia'))

    expect_error(load_ecd(language = 'Klingon'))

}



)


test_that('the release list is reachable', {

  skip_on_cran()

  skip_if_offline()

  releases = get_ecd_release()

  expect_type(releases, 'character')

  expect_true('1.0.0' %in% releases)

})


test_that('an unpublished version is rejected', {

  skip_on_cran()

  skip_if_offline()

  expect_error(load_ecd(country = 'Greece', ecd_version = '99.9.9'))

})
