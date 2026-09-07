import os
import sys
import html
import smtplib
import psycopg2
from email.message import EmailMessage
from datetime import datetime as dt

# --- Config from environment -------------------------------------------------
# Same Postgres the scraper writes to (Railway: reference the Postgres service's
# DATABASE_URL on this service too).
DATABASE_URL = os.getenv('DATABASE_URL')

# Gmail account used to SEND. Requires an App Password (2-Step Verification must
# be on for the account). Generate at https://myaccount.google.com/apppasswords
GMAIL_ADDRESS = os.getenv('GMAIL_ADDRESS')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')

# Where the digest goes. Defaults to sending to yourself.
DIGEST_TO = os.getenv('DIGEST_TO', GMAIL_ADDRESS)

# How many hours back to include.
WINDOW_HOURS = int(os.getenv('DIGEST_WINDOW_HOURS', '24'))

TABLE_NAME = 'news'
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 465  # implicit SSL
# -----------------------------------------------------------------------------


def fetch_headlines():
    """Return list of (title, link, source, created_at) from the last WINDOW_HOURS."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        # created_at is stored in UTC (Railway Postgres runs UTC), so a plain
        # NOW() - INTERVAL window gives a clean rolling 24-hour range.
        cur.execute(
            f"""
            SELECT title, link, source, created_at
            FROM {TABLE_NAME}
            WHERE created_at >= NOW() - (%s * INTERVAL '1 hour')
            ORDER BY source ASC, created_at DESC
            """,
            (WINDOW_HOURS,),
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()


def build_email_bodies(rows):
    """Return (plain_text, html_text) for the digest email."""
    total = len(rows)

    # Group by source, preserving the query's ordering.
    grouped = {}
    for title, link, source, created_at in rows:
        grouped.setdefault(source or 'Other', []).append((title, link))

    # --- Plain text ---
    plain_lines = [f"Energy news digest - {total} headline(s) in the last {WINDOW_HOURS}h", ""]
    if total == 0:
        plain_lines.append("No new headlines in the last 24 hours.")
    else:
        for source, items in grouped.items():
            plain_lines.append(f"== {source} ({len(items)}) ==")
            for title, link in items:
                plain_lines.append(f"- {title}")
                if link:
                    plain_lines.append(f"  {link}")
            plain_lines.append("")
    plain_text = "\n".join(plain_lines)

    # --- HTML ---
    html_parts = [
        '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        'max-width:640px;margin:0 auto;color:#1a1a1a;">',
        f'<h2 style="margin:0 0 4px;">Energy News Digest</h2>',
        f'<p style="color:#666;margin:0 0 20px;font-size:13px;">'
        f'{total} headline(s) from the last {WINDOW_HOURS} hours</p>',
    ]
    if total == 0:
        html_parts.append('<p>No new headlines in the last 24 hours.</p>')
    else:
        for source, items in grouped.items():
            html_parts.append(
                f'<h3 style="margin:20px 0 8px;border-bottom:1px solid #eee;'
                f'padding-bottom:4px;">{html.escape(source)} '
                f'<span style="color:#999;font-weight:normal;font-size:13px;">'
                f'({len(items)})</span></h3>'
            )
            html_parts.append('<ul style="margin:0;padding-left:18px;line-height:1.5;">')
            for title, link in items:
                safe_title = html.escape(title or '(untitled)')
                if link:
                    safe_link = html.escape(link, quote=True)
                    html_parts.append(
                        f'<li><a href="{safe_link}" '
                        f'style="color:#1155cc;text-decoration:none;">{safe_title}</a></li>'
                    )
                else:
                    html_parts.append(f'<li>{safe_title}</li>')
            html_parts.append('</ul>')
    html_parts.append('</div>')
    html_text = "\n".join(html_parts)

    return plain_text, html_text


def send_email(subject, plain_text, html_text):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = DIGEST_TO
    msg.set_content(plain_text)
    msg.add_alternative(html_text, subtype='html')

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)


def main():
    missing = [name for name, val in [
        ('DATABASE_URL', DATABASE_URL),
        ('GMAIL_ADDRESS', GMAIL_ADDRESS),
        ('GMAIL_APP_PASSWORD', GMAIL_APP_PASSWORD),
    ] if not val]
    if missing:
        print(f"{dt.now()} - Missing required env vars: {', '.join(missing)}")
        sys.exit(1)

    rows = fetch_headlines()
    plain_text, html_text = build_email_bodies(rows)
    subject = f"Energy News Digest - {dt.now().strftime('%b %d')} ({len(rows)} headlines)"

    send_email(subject, plain_text, html_text)
    print(f"{dt.now()} - Digest sent to {DIGEST_TO} with {len(rows)} headline(s)")


if __name__ == '__main__':
    main()
