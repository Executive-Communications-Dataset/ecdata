#' adding this is just to grab the 
#' keywords @internal 
#' @noRd


country_dictionary = \(){
  
  country_names = 'name_in_dataset, file_name, language,
        Argentina,  argentina, Spanish,
        Australia,  australia, English,
        Austria,  austria, English,
        Azerbaijan,  azerbaijan, English,
        Bolivia,  bolivia, Spanish,
        Brazil, brazil, Portugese,
        Canada,  canada, English,
        Chile,  chile, Spanish,
        Colombia,  colombia, Spanish,
        Costa Rica,  costa_rica, Spanish,
        Czechia,  czechia, Czech,
        Denmark,  denmark, Danish,
        Ecuador,  ecuador, Spanish,
        France,  france, French,
        Georgia,  georgia, Georgian,
        Germany,  germany, German,
        Greece,  greece, Greek,
        Hong Kong,  hong_kong, Chinese,
        Hungary,  hungary, Hungarian
        Iceland,  iceland, Icelandic,
        India,  india, English,
        India, india, Hindi,
        Indonesia,  indonesia, Indonesian, 
        Israel,  israel, Hebrew,
        Italy,  italy, Italian
        Jamaica,  jamaica, English,
        Japan,  japan, Japanese,
        Mexico,  mexico, Spanish,
        New Zealand,  new_zealand, English
        Nigeria,  nigeria, English,
        Norway,  norway, Norwegian
        Philippines,  philippines, Filipino
        Poland,  poland, Polish
        Portugal,  portugal, Portugese,
        Republic of Korea,  republic_of_korea, Korean,
        Russia,  russia, English,
        Spain,  spain, Spanish,
        Turkey,  turkey, Turkish, 
        United Kingdom,  united_kingdom, English,
        United States of America,  united_states_of_america, English,
        Uruguay,  uruguay, Spanish,
        Venezuela,  venezuela, Spanish'

out = utils::read.csv(
  text = country_names,
  colClasses = c('character', 'character', 'character')
) 
  
out = out[, c(1:3)]

for (i in 1:3) {

  out[[i]] = trimws(out[[i]])
  
}

return(out)

}

