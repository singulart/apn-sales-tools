from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
from celery import Celery

app = Celery(broker='redis://localhost:6379/0')

options = Options()
options.add_argument("--headless")

driver = webdriver.Chrome(options=options)

def crawl_pages(start_url):
    url = start_url
    do_fetch = True
                
    while url:
        print(f"\nProcessing page: {url}")
        if do_fetch: 
            driver.get(url)
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Step 1 and 2: Extract URLs from h2.m-headline > a
        headlines = soup.select('h2.m-headline a[href]')
        if len(headlines) == 0 : 
            print(f"\nWaiting for page to load fully: {url}")
            time.sleep(2)
            do_fetch = False
            continue
            
        for a_tag in headlines:
            href = a_tag.get('href')
            if not href:
                continue
            # Step 3: Check if the URL does not start with aws.amazon.com
            if not href.startswith("https://aws.amazon.com"):
                print(f"Non-AWS link found: {href}")
            else:
                app.send_task(name='dummy.task', args=[href], queue='apn_success_stories')

        # Step 4: Find next page link
        next_page_tag = soup.select_one('a.m-icon-angle-right[href]')
        if next_page_tag:
            url = next_page_tag.get('href') # because it's an absolute URL 
            do_fetch = True
        else:
            print("No next page found.")
            break

crawl_pages("https://aws.amazon.com/solutions/case-studies/browse-customer-success-stories/")

