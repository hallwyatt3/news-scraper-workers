# News Scraper Workers

Two scheduled workers that scrape energy/business news and process it into a database.

## Services

### 1. news-scraper-worker (main.py)
- Runs every 15 minutes
- Scrapes news from: Reuters, Hart Energy, Marcellus Drilling News, Jefferies
- Stores articles in `news` table with `teamsd = 0`

### 2. news-processor-worker (processor.py)
- Runs every 30 minutes
- Processes unread news from `news` table
- Inserts into `app_post` table
- Marks items as processed by setting `teamsd = 1`

## Setup

Set `DATABASE_URL` environment variable pointing to your PostgreSQL instance.

Both workers will automatically create their required tables on first run.
