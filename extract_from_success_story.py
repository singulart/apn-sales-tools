import sqlite3
from celery import Celery
from celery.utils.log import get_task_logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import spacy

app = Celery(config_source='celeryconfig')
logger = get_task_logger(__name__)
nlp = spacy.load("en_core_web_sm")

def extract_persons_and_roles(text):
    doc = nlp(text)
    results = []

    for ent in doc.ents:
        if ent.label_ == "PERSON":
            # Search for a title or role nearby using token dependency
            person = ent.text
            role = None

            # Look to the right for appositional phrase or prepositional phrase
            for token in ent.root.rights:
                if token.dep_ in ("appos", "attr", "conj", "prep"):
                    role_span = [token]
                    role_span.extend([child for child in token.subtree])
                    role = " ".join(sorted({t.text for t in role_span}, key=lambda x: text.find(x)))
                    break

            # Look to the left for roles in patterns like "CEO John Smith"
            if not role:
                for token in ent.root.head.lefts:
                    if token.dep_ in ("compound", "amod", "nmod") and token.pos_ in ("NOUN", "PROPN"):
                        role = token.text
                        break

            results.append((person, role))

    return results

# Process a Success Story from AWS APN portal and extract data for further sales automation
@app.task(queue = 'apn_success_stories', name='dummy.task')
def process_success_story(story_url):

    conn = sqlite3.connect('apn_sales.db')
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS apn_sales_data (company VARCHAR(128), firstname VARCHAR(128), lastname VARCHAR(128), role VARCHAR(128), aws_services VARCHAR(256))')

    options = Options()
    options.add_argument("--headless")

    driver = webdriver.Chrome(options=options)
    do_fetch = True
    while True:
        logger.info(f"\nProcessing page: {story_url}")
        if do_fetch: 
            driver.get(story_url)
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Extracting info on used AWS Services
        aws_services = soup.select('div.lb-border-p-feature')
        if len(aws_services) == 0 : 
            logger.info(f"\nWaiting for page to load fully")
            time.sleep(2)
            do_fetch = False
            continue
        services_to_save  = [service.find('h3').get_text(strip = True) for service in aws_services]
        logger.info(services_to_save) 

        # Extracting info on PoC
        text_blocks = soup.select('.lb-rtxt')
        logger.info(len(text_blocks))
        content = '\n'.join([block.get_text(strip=True) for block in text_blocks])
        logger.info(content[:100])
        for name, role in extract_persons_and_roles(content):
            logger.info(f"Name: {name}, Role: {role}")
        
        
