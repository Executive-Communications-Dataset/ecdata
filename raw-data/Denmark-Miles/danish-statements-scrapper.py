%pip install polars
%pip install selenium

import polars as pl 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import time

press_releases_url = 'https://www.stm.dk/presse/pressemeddelelser/'
speeches_url = 'https://www.stm.dk/statsministeren/taler/'

driver = webdriver.Firefox()

driver.maximize_window()


driver.get(press_releases_url)



def get_links(driver):
    page_links = driver.find_elements(By.CSS_SELECTOR, '#js-column-list article a')
    links = [page_links.get_attribute('href') for page_links in page_links]
    return links

def collect_links(driver, max_pages=87):
    links = []
    for counter in range(max_pages):
        try:
            links_page = get_links(driver)
            links.extend(links_page)
            
            
            next_page = driver.find_element(By.CSS_SELECTOR, '#js-section-content > section:nth-child(5) > dir-pagination-controls > ul > li:nth-child(7) > a')
            next_page.click()
            
           
            time.sleep(5)
        except Exception as e:
            print(f"An error occurred on page {counter + 1}: {e}")
            break
    return links


all_links = collect_links(driver)

links_dat = pl.DataFrame(all_links, schema=['url'])

links_85 = get_links(driver)



next_page = driver.find_element(By.CSS_SELECTOR, '#js-section-content > section:nth-child(5) > dir-pagination-controls > ul > li:nth-child(7) > a')

next_page.click()


links_86 = get_links(driver)


links_87 = get_links(driver)

links_two = []

links_two.extend(links_85)
links_two.extend(links_86)
links_two.extend(links_87)

links_data_two = pl.DataFrame(links_two, schema=['url'])

all_links = pl.concat([links_dat, links_data_two], how = 'vertical')

all_links.write_csv('danish-press-releases.csv')


driver.get(speeches_url)


get_links(driver)

def collect_links(driver, max_clicks=28):
    links = []
    counter = 0

    while counter < max_clicks:
        try:
            
            links_page = get_links(driver)
            links.extend(links_page)
            
            
            next_page = driver.find_element(By.CSS_SELECTOR, '#js-section-content > section:nth-child(5) > dir-pagination-controls > ul > li:nth-child(7) > a')
            next_page.click()
            
            
            time.sleep(5)
            
            
            counter += 1
        except Exception as e:
            print(f"An error occurred after {counter + 1} clicks: {e}")
            break
    
    return links



speech_urls = collect_links(driver, max_clicks= 25)


speeches_url_dat = pl.DataFrame(speech_urls, schema=["url"])


speeches_url_dat.write_csv('speeches_links.csv')





driver.get(all_links_vec[0])

date = driver.find_element(By.CLASS_NAME, 'small-label') 

date.get_attribute('textContent')


title = driver.find_element(By.CSS_SELECTOR, '.article-top h1')


title.get_attribute('textContent')


text = driver.find_elements(By.CSS_SELECTOR, '.article-components p')

[text.get_attribute('textContent') for text in text]



data = {
    'links': [],
    'date' : [],
    'text' : [],
    'subject' : []
    
}



def get_date(driver):
    date = driver.find_element(By.CLASS_NAME, 'small-label') 
    date = date.get_attribute('textContent')
    return date 

def get_subject(driver):
    subject = driver.find_element(By.CSS_SELECTOR, '.article-top h1')
    subject = subject.get_attribute('textContent')
    return subject

def get_text(driver):
    text = driver.find_elements(By.CSS_SELECTOR, '.article-components p')
    text = [text.get_attribute('textContent') for text in text]
    return text

data = {
    'links': [],
    'date' : [],
    'text' : [],
    'subject' : []
    
}

all_link_vec = pl.read_csv('danish-press-releases.csv')

all_links_vec = all_link_vec['url']

missing_element_links = []

data_frame = pl.DataFrame()

for link in all_links_vec:
    time.sleep(5)
    print(f'Scraping {link}')
    driver.get(link)
    try:
        text_page = get_text(driver)
        subject_page = get_subject(driver)
        date_page = get_date(driver)
        for paragraph in text_page:
            data['date'].append(date_page)
            data['subject'].append(subject_page)
            data['text'].append(paragraph)
            data['links'].append(link)
            data_frame_page = pl.DataFrame(data)
            data_frame.vstack(data_frame_page)
    except NoSuchElementException:
        missing_element_links.append(link)

scraped_data_one = pl.DataFrame(data)

## umm thats interesting 
## the date is actually the selenium element 

expand_text = scraped_data_one


expand_text.write_csv('danish_press_releases_danish.csv')

speeches_links = pl.read_csv('speeches_links.csv')

links_vec = speeches_links['url']



data = {
    'links': [],
    'date' : [],
    'text' : [],
    'subject' : []
    
}


data_frame = pl.DataFrame()

for link in links_vec:
    time.sleep(5)
    print(f'Scraping {link}')
    driver.get(link)
    try:
        text_page = get_text(driver)
        subject_page = get_subject(driver)
        date_page = get_date(driver)
        for paragraph in text_page:
            data['date'].append(date_page)
            data['subject'].append(subject_page)
            data['text'].append(paragraph)
            data['links'].append(link)
            data_frame_page = pl.DataFrame(data)
            data_frame.vstack(data_frame_page)
    except NoSuchElementException:
        missing_element_links.append(link)


danish_speeches = pl.DataFrame(data)

danish_speeches.head()

danish_speeches.write_csv('danish_speeches.csv')