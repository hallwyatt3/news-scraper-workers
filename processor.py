import psycopg2
from urllib.parse import urlparse
import logging
import os
from datetime import datetime as dt

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Source database (aware-adaptation) - where news is scraped
SOURCE_DATABASE_URL = os.getenv('DATABASE_URL')
# Target database (awake-victory) - where processed news goes
TARGET_DATABASE_URL = os.getenv('TARGET_DATABASE_URL')

SOURCE_TABLE = 'news'
TARGET_TABLE = 'app_post'

def init_target_db(conn):
    """Ensure app_post table exists in target database."""
    try:
        cur = conn.cursor()
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
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
        logger.info("app_post table initialized in target database")
    except Exception as e:
        logger.error(f"Target table initialization error: {e}")
        conn.rollback()

def check_db_update_and_post():
    """Check news table (source DB) for unprocessed items and insert into app_post (target DB)."""
    try:
        # Connect to source database (aware-adaptation)
        source_conn = psycopg2.connect(SOURCE_DATABASE_URL)
        source_cur = source_conn.cursor()
        
        # Connect to target database (awake-victory)
        target_conn = psycopg2.connect(TARGET_DATABASE_URL)
        
        # Initialize tables in target database
        init_target_db(target_conn)
        
        target_cur = target_conn.cursor()
        
        # Get unprocessed news from source database
        logger.info("Querying unprocessed news from source database...")
        source_cur.execute(f"SELECT id, title, link FROM {SOURCE_TABLE} WHERE teamsd = 0 ORDER BY created_at DESC LIMIT 100")
        news = source_cur.fetchall()
        
        if not news:
            logger.info("No new news to process")
            source_cur.close()
            source_conn.close()
            target_cur.close()
            target_conn.close()
            return
        
        logger.info(f"Found {len(news)} unprocessed articles")
        updated_rows = []
        
        for row_id, title, link in news:
            try:
                site = urlparse(link).netloc
                
                # Insert into app_post in target database with explicit insert_date
                target_cur.execute(f"""
                INSERT INTO {TARGET_TABLE} (title, url, votes, site, user_id, insert_date)
                VALUES (%s, %s, 1, %s, 2, CURRENT_TIMESTAMP)
                """, (title[:140], link[:500], site))
                
                logger.info(f"Inserted to awake-victory: {title[:80]}")
                updated_rows.append(row_id)
                
            except Exception as e:
                logger.error(f"Error processing row {row_id}: {e}")
                # Rollback the failed transaction and continue with next row
                target_conn.rollback()
                continue
        
        # Commit to target database
        target_conn.commit()
        
        # Mark as processed in source database
        if updated_rows:
            source_cur.execute(f"UPDATE {SOURCE_TABLE} SET teamsd = 1 WHERE id = ANY(%s)", (updated_rows,))
            source_conn.commit()
            logger.info(f"Marked {len(updated_rows)} articles as processed in source database")
        
        source_cur.close()
        source_conn.close()
        target_cur.close()
        target_conn.close()
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        if 'source_conn' in locals():
            source_conn.close()
        if 'target_conn' in locals():
            target_conn.close()

def main():
    """Main entry point."""
    logger.info("Starting news processor worker")
    logger.info(f"Source DB: {SOURCE_DATABASE_URL[:50] if SOURCE_DATABASE_URL else 'NOT SET'}...")
    logger.info(f"Target DB: {TARGET_DATABASE_URL[:50] if TARGET_DATABASE_URL else 'NOT SET'}...")
    check_db_update_and_post()

if __name__ == '__main__':
    main()
