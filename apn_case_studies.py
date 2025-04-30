import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin

def crawl_pages(start_url):
    url = start_url
    session = requests.Session()

    while url:
        print(f"\nProcessing page: {url}")
        try:
            response = session.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')

        # Step 1 and 2: Extract URLs from h2.m-headline > a
        headlines = soup.select('h2.m-headline a[href]')
        for a_tag in headlines:
            href = a_tag.get('href')
            if not href:
                continue
            full_url = urljoin(url, href)
            # Step 3: Check if the URL does not start with aws.amazon.com
            if not full_url.startswith("https://aws.amazon.com"):
                print(f"Non-AWS link found: {full_url}")

        # Step 4: Find next page link
        next_page_tag = soup.select_one('a.m-icon-angle-right[href]')
        if next_page_tag:
            next_href = next_page_tag.get('href')
            url = urljoin(url, next_href)
            time.sleep(1)  # Be polite to the server
        else:
            print("No next page found.")
            break

# Example usage:
crawl_pages("https://aws.amazon.com/blogs/")

