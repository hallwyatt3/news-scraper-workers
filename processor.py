import psycopg2
from urllib.parse import urlparse
import logging
import os
from datetime import datetime as dt

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
TABLE_NAME = 'news'
WAIT_TIME = 30  # minutes

def init_db(conn):
    """Ensure app_post table exists."""
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS app_post (
        id SERIAL PRIMARY KEY,
        title VARCHAR(500),
        url VARCHAR(500),
        votes INTEGER DEFAULT 1,
        insert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        site VARCHAR(255),
        show_dt BOOLEAN DEFAULT false,
        ask_dt BOOLEAN DEFAULT false,
        tweeted BOOLEAN DEFAULT false,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        cur.close()
        logger.info("app_post table initialized")
    except Exception as e:
        logger.error(f"Table initialization error: {e}")
        conn.rollback()

def check_db_update_and_post():
    """Check news table for unprocessed items and insert into app_post."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        
        # Initialize tables
        init_db(conn)
        
        cur = conn.cursor()
        
        # Get unprocessed news
        cur.execute(f"SELECT id, title, link FROM {TABLE_NAME} WHERE teamsd = 0 ORDER BY created_at DESC LIMIT 100")
        news = cur.fetchall()
        
        if not news:
            logger.info("No new news to process")
            cur.close()
            conn.close()
            return
        
        updated_rows = []
        
        for row_id, title, link in news:
            try:
                site = urlparse(link).netloc
                
                # Insert into app_post
                cur.execute("""
                INSERT INTO app_post (title, url, votes, site, user_id)
                VALUES (%s, %s, 1, %s, 2)
                """, (title[:140], link[:500], site))
                
                logger.info(f"Inserted: {title[:80]}")
                updated_rows.append(row_id)
                
            except Exception as e:
                logger.error(f"Error processing row {row_id}: {e}")
                continue
        
        # Mark as processed
        if updated_rows:
            cur.execute(f"UPDATE {TABLE_NAME} SET teamsd = 1 WHERE id = ANY(%s)", (updated_rows,))
            conn.commit()
            logger.info(f"Sent {len(updated_rows)} updates to app_post. Sleeping for {WAIT_TIME} minutes...")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()

def main():
    """Main entry point."""
    logger.info("Starting news processor worker")
    check_db_update_and_post()

if __name__ == '__main__':
    main()
