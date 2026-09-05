import time
import psycopg2
from psycopg2.extras import execute_values
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import datetime
import json
import os
from datetime import datetime as dt

# Database connection from Railway environment variable
DATABASE_URL = os.getenv('DATABASE_URL')

TABLE_NAME = 'news'

urls = {
    'reuters': 'https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com/business/energy&ceid=US:en&hl=en-US&gl=US',
    'hart': 'https://www.hartenergy.com/pf/api/v3/content/fetch/story-feed-sections?query=%7B%22excludeSections%22%3A%22%2Fother-media%2C%20%2Fvideo%22%2C%22feature%22%3A%22section-results-list%22%2C%22feedOffset%22%3A0%2C%22feedSize%22%3A11%2C%22includeSections%22%3A%22%2Fupstream%22%7D',
    'mdn': 'https://news.google.com/rss/search?q=when:24h+allinurl:marcellusdrilling.com&ceid=US:en&hl=en-US&gl=US',
    'jefferies': 'https://www.tickertech.com/jefferies/news-listings.html/?newslist=XOM,CVX,SHEL,TTE,BP,EQNR,REPYY,COP,OXY,EOG,FANG,DVN,OVV,PR,APA,MTDR,CIVI,CHRD,CRGY,SM,CRC,NOG,MGY,MUR,EQT,EXE,CTRA,AR,RRC,CNX,DEC,GPOR,INR,TPL,VNOM,BSM,KRP,DMLP,VTS,TBN,BKV,TALO,MNR,SOC,KOS,DEC,REPX,HPK,GRNT,TXO,SD,WTI,REI,FTW,AMPY,PED,EPM,PROP,EP,BATL'
}

date_format = '%Y-%m-%d'

def init_db():
    """Initialize database table if it doesn't exist."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id SERIAL PRIMARY KEY,
        title VARCHAR(500) NOT NULL UNIQUE,
        link TEXT,
        summary TEXT,
        source VARCHAR(100),
        teamsd INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print(f"{dt.now()} - Database initialized")
    except Exception as e:
        print(f"Database initialization error: {e}")

def push_to_db(data):
    """Push news to database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {TABLE_NAME} WHERE title = %s", (data['title'],))
        if cur.fetchone():
            cur.close()
            conn.close()
            return
        
        cur.execute(
            f"INSERT INTO {TABLE_NAME} (title, link, summary, source, teamsd) VALUES (%s, %s, %s, %s, %s)",
            (data['title'], data['link'], data['summary'], data['source'], 0)
        )
        conn.commit()
        print(f'{dt.now()} - pushed - {data["source"]}: {data["title"]}')
        cur.close()
        conn.close()
    except psycopg2.IntegrityError:
        # Duplicate key, ignore
        pass
    except Exception as e:
        print(f"Database push error: {e}")

def check_reuters(url):
    try:
        xml_data = requests.get(url, timeout=10).text
        root = ET.fromstring(xml_data)
        titles = root.findall("./channel/item")
        for i in titles:
            data = {}
            data['title'] = i[0].text
            data['link'] = i[1].text
            data['summary'] = i[0].text
            data['source'] = 'Reuters'
            push_to_db(data)
    except Exception as e:
        print(f"Reuters check error: {e}")

def check_hart(url):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        hart_data = response.json()
        
        articles = []
        for item in hart_data.get("content_elements", []):
            if item.get("type") != "story":
                continue
            canonical = item.get("canonical_url")
            headline = item.get("headlines", {}).get("basic")
            if canonical and headline:
                articles.append({
                    "canonical_url": "https://www.hartenergy.com" + canonical,
                    "headline": headline
                })
        
        for i in articles:
            data = {}
            data['title'] = i['headline']
            data['link'] = i['canonical_url']
            data['summary'] = i['headline']
            data['source'] = 'Hart Energy'
            push_to_db(data)
    except Exception as e:
        print(f'Failed fetching Hart data: {e}')

def check_mdn(url):
    try:
        xml_data = requests.get(url, timeout=10).text
        root = ET.fromstring(xml_data)
        titles = root.findall("./channel/item")
        for i in titles:
            data = {}
            data['title'] = i[0].text
            data['link'] = i[1].text
            data['summary'] = i[0].text
            data['source'] = 'Marcellus Drilling News'
            push_to_db(data)
    except Exception as e:
        print(f"MDN check error: {e}")

def check_jefferies(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        news_article_divs = soup.find_all('a', href=True)
        for i in news_article_divs:
            data = {}
            data['title'] = i.text[:140]
            data['link'] = "https://www.tickertech.com/jefferies/news-listings.html/" + i['href'][:100]
            data['summary'] = i.text[:140]
            data['source'] = 'Jefferies'
            push_to_db(data)
    except Exception as e:
        print(f"Jefferies check error: {e}")

def run_scrape():
    """Run all scraping functions."""
    print(f"{dt.now()} - Starting scrape cycle")
    try:
        check_reuters(urls['reuters'])
        check_hart(urls['hart'])
        check_mdn(urls['mdn'])
        check_jefferies(urls['jefferies'])
        print(f"{dt.now()} - Scrape cycle complete")
    except Exception as e:
        print(f"Scrape cycle error: {e}")

if __name__ == '__main__':
    init_db()
    run_scrape()
