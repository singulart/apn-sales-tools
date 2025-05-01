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

def extract_names(person_ent):
    
    if len(person_ent) == 0:
        return "", ""
    
    elif len(person_ent) >= 2:
        # Multi-token name: all but last as first name, last as last name
        first_name = " ".join(t.text for t in person_ent[:-1])
        last_name = person_ent[-1].text
    else: 
        first_name = person_ent[0].text
        last_name = ""
    
    return first_name, last_name

def spacy_extract(text):

    doc = nlp(text)
    extracted = []
    
    # Iterate over sentences
    for sent in doc.sents:
        # Check if the sentence matches the user's pattern
        if 'says' in sent.text:
            # Process the sentence
            sent_doc = nlp(sent.text)
            
            for ent in sent_doc.ents:
                
                # Extracting company (naïvely)
                parts = sent_doc.text.rsplit(" at ", 1)
                if len(parts) == 2:
                    company = parts[1].strip()
                else:
                    company = None
                # Find PERSON entities
                if ent.label_ == "PERSON":
                    # Extract first name and last name
                    first_name, last_name = extract_names(ent)
                    
                    # Find appositional modifiers (for title and company)
                    for token in sent_doc:
                        if token.dep_ == "appos" and token.head in ent:
                            # Extract role text
                            role_tokens = [t for t in token.subtree if t.pos_ != "PUNCT"]
                            role_text = " ".join(t.text for t in role_tokens)
                            # Extracting title
                            parts = role_text.rsplit(" at ", 1)
                            if len(parts) == 2:
                                title = parts[0].strip()
                            else:
                                title = role_text.strip()
                            # Print extracted information
                            print(f"First Name: {first_name}, Last Name: {last_name}, Title: {title}, Company: {company}")
                            extracted.append([company, first_name, last_name, title])
    return extracted                   

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
    attempts = 5
    while True:
        if attempts <= 0:
            logger.info(f"\nGiving up waiting: non-standard page structure")
            break
            
        logger.info(f"\nProcessing page: {story_url}")
        if do_fetch: 
            driver.get(story_url)
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Extracting info on used AWS Services
        aws_services = soup.select('div.lb-border-p-feature')
        if len(aws_services) == 0: 
            attempts -= 1
            logger.info(f"\nWaiting for page to load fully")
            time.sleep(2)
            do_fetch = False
            continue
        
        services_to_save  = [service.find('h3').get_text(strip = True) for service in aws_services]
        logger.info(services_to_save)

        # Extracting info on PoC
        text_blocks = soup.select('.lb-rtxt')
        content = '\n'.join([block.get_text(strip=True) for block in text_blocks])
        # logger.info(content[:200])
        extracted = spacy_extract(content)
        for item in extracted:
            item.append(",".join(services_to_save))
        
        try: 
            conn.executemany('INSERT INTO apn_sales_data (company, firstname, lastname, role, aws_services) VALUES (?, ?, ?, ?, ?)', extracted)
            conn.commit()
            break
        except sqlite3.ProgrammingError as er:
            logger.error(er.sqlite_errorname)            
        finally:
            conn.close()        
