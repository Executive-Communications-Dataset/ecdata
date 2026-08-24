%pip install polars 
%pip install selenium

import polars as pl 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
import time 
import os


url = 'https://www.ceo.gov.hk/tc/press.html'

driver = webdriver.Firefox()

driver.maximize_window()

driver.get(url)

## this works 
first_year_click = driver.find_elements(By.XPATH, '/html/body/div[2]/main/div/section/ul/li')

def find_year_tabs(driver):
    tabs = driver.find_elements(By.XPATH, '/html/body/div[2]/main/div/section/ul/li')
    number_of_tabs = len(tabs)
    selectors_to_click = []
    for i in range(number_of_tabs):
        string = f'/html/body/div[2]/main/div/section/ul/li[{i + 1}]'
        selectors_to_click.append(string)
    return selectors_to_click

selectors_to_click = find_year_tabs(driver)


press_statements_2024 = driver.find_elements(By.CLASS_NAME, 'btn-link') 

extract_statements = [press_statements_2024.get_attribute('href') for press_statements_2024 in press_statements_2024]


print(extract_statements)

press_statements_2024_df = pl.DataFrame(extract_statements, schema=['url']).with_columns(year = 2024).filter(pl.col('url').is_not_null())

press_statements_2024_df.head()

##

driver.find_element(By.XPATH, selectors_to_click[1]).click()


press_statements_2023 = driver.find_elements(By.CLASS_NAME, 'btn-link') 

extract_statements = [press_statements_2023.get_attribute('href') for press_statements_2023 in press_statements_2023]

press_statements_2023 = pl.DataFrame(extract_statements, schema=['url']).with_columns(year = 2023).filter(pl.col('url').is_not_null())


driver.find_element(By.XPATH, selectors_to_click[2]).click()

press_statements_2022 = driver.find_elements(By.CLASS_NAME, 'btn-link') 

extract_statements = [press_statements_2022.get_attribute('href') for press_statements_2022 in press_statements_2022]

press_statements_2022 = pl.DataFrame(extract_statements, schema=['url']).with_columns(year = 2022).filter(pl.col('url').is_not_null())

big_press_data = pl.concat([press_statements_2024_df, press_statements_2023, press_statements_2022], how = 'vertical').filter(pl.col('url') != 'https://www.ceo.gov.hk/tc/press.html#')

urls_vec = big_press_data['url']

driver.get(urls_vec[0])

date = driver.find_element(By.XPATH, '//*[@id="pressrelease"]/div[4]')

date.get_attribute('textContent')

subject = driver.find_element(By.ID, 'PRHeadlineSpan')

subject.get_attribute('textContent')

#pressrelease > font:nth-child(1) > font
#pressrelease > font:nth-child(4) > font

texts = driver.find_elements(By.XPATH, '//*[@id="pressrelease"]')

texts = [texts.get_attribute('textContent') for texts in texts]

check = pl.DataFrame(texts, schema=['text'])



def get_text(driver):
    texts = driver.find_elements(By.XPATH, '//*[@id="pressrelease"]')
    texts = [texts.get_attribute('textContent') for texts in texts]
    return texts

data = {
    'date': [],
    'subject': [],
    'text': [],
    'url':[]
}

press_links = pl.read_csv('hong-kong-links.csv')

urls_vec = press_links['url']

for links in urls_vec:
    WebDriverWait(driver,timeout=5 ,poll_frequency= 5)
    driver.get(links)
    date_page = driver.find_element(By.XPATH, '//*[@id="pressrelease"]/div[4]')
    date_page = date_page.get_attribute('textContent')
    subject_page = driver.find_element(By.ID, 'PRHeadlineSpan')
    subject_page = subject_page.get_attribute('textContent')
    text_page = get_text(driver)
    for paragragh in text_page:
        data['date'].append(date_page)
        data['subject'].append(subject_page)
        data['text'].append(paragragh)
        data['url'].append(links)
    print('Done Scraping', links)
    time.sleep(5)

hong_kong_press = pl.DataFrame(data)

hong_kong_press.head()

# import os 
# 
# os.mkdir('data')

hong_kong_press.write_csv('data/press_statements.csv')

speeches_url = 'https://www.ceo.gov.hk/tc/speeches.html'

driver = webdriver.Firefox()

driver.get(speeches_url)


selectors = find_year_tabs(driver)

selectors_to_use = selectors[1:3]

links_to_scrape = []

len(selectors_to_use)




for selector in selectors_to_use:
    speech_statements = driver.find_elements(By.CLASS_NAME, 'btn-link') 
    full_links = [speech_statements.get_attribute('href') for speech_statements in speech_statements]
    links_to_scrape.extend(full_links)
    time.sleep(5)
    driver.find_element(By.XPATH, selector).click()



speeches = pl.DataFrame(links_to_scrape, schema=['url']).filter(pl.col('url') != 'https://www.ceo.gov.hk/tc/speeches.html#')


speeches.write_csv('speeches.csv')

speeches = pl.read_csv('speeches.csv')

urls_vec = speeches['url']

driver = webdriver.Firefox()


date_page = driver.find_element(By.XPATH, '//*[@id="pressrelease"]/div[4]')

data_two = {
    'date': [],
    'subject': [],
    'text': [],
    'url':[]
}



for links in urls_vec:
    driver.get(links)
    date_page = driver.find_element(By.XPATH, '//*[@id="pressrelease"]/div[4]')
    date_page = date_page.get_attribute('textContent')
    subject_page = driver.find_element(By.ID, 'PRHeadlineSpan')
    subject_page = subject_page.get_attribute('textContent')
    text_page = get_text(driver)
    for paragragh in text_page:
        data_two['date'].append(date_page)
        data_two['subject'].append(subject_page)
        data_two['text'].append(paragragh)
        data_two['url'].append(links)
    print('Done Scraping', links)
    time.sleep(5)


speechs_data = pl.DataFrame(data_two)

all_data=  pl.concat([hong_kong_press, speechs_data], how = 'vertical')

speechs_data.write_csv('data/speeches_data.csv')

hong_kong_press.write_csv('data/press_releases.csv')



all_data.write_csv('data/raw_statement_data.csv')
