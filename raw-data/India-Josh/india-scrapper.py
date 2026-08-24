import time 
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys 
from selenium import webdriver
from selenium.webdriver.support.ui import Select
import polars as pl 
import polars.selectors as cs
from lxml import html
from selenium.webdriver.common.alert import Alert 
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


dates = []

refs = []

pause_scroll_time = 15

driver = webdriver.Firefox()

base_url  = "https://www.pmindia.gov.in/hi/tag/pmspeechhindi/"

driver.get(base_url)

driver.maximize_window()


last_height = driver.execute_script("return document.body.scrollHeight")

start_time = time.perf_counter()



def get_dates(driver):
    get_dates = driver.find_elements(By.CSS_SELECTOR, ".date") 
    get_all_dates = [get_dates.get_attribute("textContent") for get_dates in get_dates]
    return get_all_dates

def get_refs(driver):
    get_refs = driver.find_elements(By.CSS_SELECTOR, ".news-description a")
    get_all_refs = [get_refs.get_attribute("href") for get_refs in get_refs]
    return get_all_refs


while True:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    
    try:
        WebDriverWait(driver, 10).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "#inifiniteLoader"))
        )
    except TimeoutException:
        print("Loading icon took too long to disappear.")
    
    time.sleep(pause_scroll_time)
    
    refs_page = get_refs(driver)
    dates_page = get_dates(driver)
    refs.append(refs_page)
    dates.append(dates_page)
    
    new_height = driver.execute_script("return document.body.scrollHeight")
    
    if new_height == last_height:
        end_time = time.perf_counter()
        print("This took", end_time - start_time)
        break





hindi_links  = pl.read_parquet('hindi_links.parquet')

check_dates = hindi_links.select(pl.col('date')).explode('date').unique(subset='date')

## 

driver = webdriver.Firefox()

driver.maximize_window()


links = hindi_links.unique(subset='links')

driver.get(links['links'][0])

def get_text(driver):
    text_page = WebDriverWait(driver, 10).until(
        EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "#printable > div.news-bg p")))
    all_text = [text_page.get_attribute('textContent') for text_page in text_page]
    return all_text


def get_date(driver):
    date_page = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".share_date .date")))
    date = date_page.get_attribute('textContent')
    return date

def get_subject(driver):
    subject_page = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, '#printable > h2:nth-child(1)')))
    subject = subject_page.get_attribute('textContent')
    return subject


get_text(driver)

get_date(driver)

get_subject(driver)


hindi_data = {
    'text': [],
    'date': [],
    'title': [],
    'url': []
}

english_data = {
    'text': [],
    'date': [],
    'title': [],
    'url': []
}



links_vec = links['links']



for link in links_vec:
    try:
        driver.get(link)
        hindi_text_page = get_text(driver)
        hindi_subject_page = get_subject(driver)
        hindi_date_page = get_date(driver)
        for paragraph in hindi_text_page:
            hindi_data['date'].append(hindi_date_page)
            hindi_data['title'].append(hindi_subject_page)
            hindi_data['text'].append(paragraph)
            hindi_data['url'].append(link)
        
    except TimeoutException:
        print(f'Timeout waiting for page to load {link}')
        continue

    try:
        lang_button = Select(driver.find_element(By.CSS_SELECTOR, '#lang_choice_polylang-2'))
        lang_button.select_by_visible_text('English')
    except NoSuchElementException: 
        print(f'Element not found on page: {link}')
    
    try:
        alert = Alert(driver)
        alert.accept()
        wait = WebDriverWait(driver, 30)
    except Exception:
        pass

    try:
        wait.until(lambda d: d.current_url != link)
    except TimeoutException:
        print(f'Timeout waiting for current URL change: {link}')
        continue

    try:
        english_link = driver.current_url
        english_text = get_text(driver)
        english_subject = get_subject(driver)

        for paragraph in english_text:
            english_data['url'].append(english_link)
            english_data['text'].append(paragraph)
            english_data['date'].append(hindi_date_page)  # Assuming date is the same for both
            english_data['title'].append(english_subject)
        
    except TimeoutException:
        print(f'Timeout exception waiting for {link}')

    print('Done scraping', link)

data_one_hindi = pl.DataFrame(hindi_data)

links_scraped = data_one_hindi.unique(subset='url')

links_scraped.glimpse()



links_scraped = links_scraped['url']

rescrape = links.filter(pl.col('links').is_in(links_scraped).not_())

rescrape = rescrape['links']

driver = webdriver.Firefox()

driver.maximize_window()


for link in rescrape:
    try:
        driver.get(link)
        hindi_text_page = get_text(driver)
        hindi_subject_page = get_subject(driver)
        hindi_date_page = get_date(driver)
        for paragraph in hindi_text_page:
            hindi_data['date'].append(hindi_date_page)
            hindi_data['title'].append(hindi_subject_page)
            hindi_data['text'].append(paragraph)
            hindi_data['url'].append(link)
        
    except TimeoutException:
        print(f'Timeout waiting for page to load {link}')
        continue

    try:
        lang_button = Select(driver.find_element(By.CSS_SELECTOR, '#lang_choice_polylang-2'))
        lang_button.select_by_visible_text('English')
    except NoSuchElementException: 
        print(f'Element not found on page: {link}')
    
    try:
        alert = Alert(driver)
        alert.accept()
        wait = WebDriverWait(driver, 30)
    except Exception:
        pass

    try:
        wait.until(lambda d: d.current_url != link)
    except TimeoutException:
        print(f'Timeout waiting for current URL change: {link}')
        continue

    try:
        english_link = driver.current_url
        english_text = get_text(driver)
        english_subject = get_subject(driver)

        for paragraph in english_text:
            english_data['url'].append(english_link)
            english_data['text'].append(paragraph)
            english_data['date'].append(hindi_date_page)  # Assuming date is the same for both
            english_data['title'].append(english_subject)
        
    except TimeoutException:
        print(f'Timeout exception waiting for {link}')

    print('Done scraping', link)



hindi_dat = pl.DataFrame(hindi_data)

check_hindi_links = hindi_dat.unique(subset = 'url')

english_dat = pl.DataFrame(english_data)

check_english_links = english_dat.unique(subset = 'url')

## okay we generally have the same thinks

links_scraped = check_hindi_links['url']

links = hindi_links.unique(subset='links')


rescrape_thes = links.filter(pl.col('links').is_in(links_scraped).not_())

rescrape_vec = rescrape_thes['links']

bind_data = pl.concat([hindi_dat, english_dat], how='vertical')

exploded = bind_data



exploded.write_parquet('indian_statements.parquet')


