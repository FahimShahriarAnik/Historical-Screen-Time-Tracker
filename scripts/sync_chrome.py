#!/usr/bin/env python3
"""
Sync Chrome browsing history into data/chrome_history.csv.

Reads from Chrome's SQLite history database and writes one row
per domain per day.

Usage:
    python3 scripts/sync_chrome.py             # incremental sync
    python3 scripts/sync_chrome.py --full      # overwrite with full history

Notes:
    - Close Chrome before running for most accurate data (WAL journal)
    - Script copies the DB to /tmp first to avoid lock conflicts
"""

import argparse
import csv
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_DIR.parent / "data" / "chrome_history.csv"
CHROME_DB = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Google"
    / "Chrome"
    / "Default"
    / "History"
)
TMP_DB = Path("/tmp/chrome_history_tmp.db")

# Seconds between WebKit epoch (1601-01-01) and Unix epoch (1970-01-01)
WEBKIT_EPOCH_OFFSET = 11_644_473_600

# Cap per-visit duration at 10 min to exclude background/idle tabs.
# Chrome's visit_duration is wall-clock time a tab stays open, not active
# attention. A tab left open overnight → one navigation event capped at 10 min
# instead of accumulating hours. Multiple real navigations on the same site
# still accumulate normally (e.g. 20 clicks on github.com = up to 200 min).
# If you change this, always re-run with --full to regenerate historical data.
MAX_VISIT_DURATION_US = 10 * 60 * 1_000_000

CSV_HEADER = ["date", "domain", "visits", "total_mins"]

GREEN = "\033[92m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
RESET = "\033[0m"


def webkit_to_date(webkit_us):
    """Convert WebKit microsecond timestamp to local date string YYYY-MM-DD."""
    unix_ts = webkit_us / 1_000_000 - WEBKIT_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_ts).strftime("%Y-%m-%d")


def extract_domain(url):
    """Return bare domain from URL, stripping www."""
    try:
        netloc = urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def existing_dates():
    """Read dates already in the CSV."""
    dates = set()
    if CSV_PATH.exists():
        with open(CSV_PATH, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "date" in row and row["date"]:
                    dates.add(row["date"])
    return dates


def fetch_history(db_path, since_date=None):
    """Query Chrome history and return (date, domain, visits, total_mins) rows."""
    since_webkit = None
    if since_date:
        # Local midnight → Unix ts → WebKit microseconds
        unix_ts = datetime.strptime(since_date, "%Y-%m-%d").timestamp()
        since_webkit = int((unix_ts + WEBKIT_EPOCH_OFFSET) * 1_000_000)

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
        print(f"{RED}Cannot open Chrome history DB: {e}{RESET}")
        sys.exit(1)

    query = """
        SELECT v.visit_time, u.url, v.visit_duration
        FROM visits v
        JOIN urls u ON v.url = u.id
        WHERE v.visit_duration > 0
    """
    params = ()
    if since_webkit:
        query += " AND v.visit_time >= ?"
        params = (since_webkit,)

    raw = conn.execute(query, params).fetchall()
    conn.close()

    # Aggregate: (date, domain) → [visit_count, total_duration_us]
    agg = {}
    for visit_time, url, duration_us in raw:
        date = webkit_to_date(visit_time)
        domain = extract_domain(url)
        if not domain:
            continue
        key = (date, domain)
        entry = agg.setdefault(key, [0, 0])
        entry[0] += 1
        entry[1] += min(duration_us, MAX_VISIT_DURATION_US)

    result = [
        (date, domain, visits, round(total_us / 60_000_000, 2))
        for (date, domain), (visits, total_us) in agg.items()
    ]
    return sorted(result, key=lambda r: (r[0], -r[2]))


def copy_db():
    """Copy Chrome DB (+ WAL/SHM if present) to /tmp to avoid lock conflicts."""
    try:
        shutil.copy2(CHROME_DB, TMP_DB)
        for ext in ("-wal", "-shm"):
            src = Path(str(CHROME_DB) + ext)
            if src.exists():
                shutil.copy2(src, Path(str(TMP_DB) + ext))
    except OSError as e:
        print(f"{RED}Could not copy Chrome history: {e}{RESET}")
        print(f"{DIM}Try closing Chrome first.{RESET}")
        sys.exit(1)


def cleanup_tmp():
    for ext in ("", "-wal", "-shm"):
        Path(str(TMP_DB) + ext).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Sync Chrome history into chrome_history.csv")
    parser.add_argument("--full", action="store_true", help="Overwrite CSV with full history")
    args = parser.parse_args()

    if not CHROME_DB.exists():
        print(f"{RED}Chrome history not found:{RESET} {CHROME_DB}")
        print(f"{DIM}Make sure Google Chrome is installed and has been opened at least once.{RESET}")
        sys.exit(1)

    copy_db()

    if args.full:
        print(f"{BOLD}Full sync — overwriting {CSV_PATH.name}{RESET}")
        since = None
        mode = "w"
    else:
        known = existing_dates()
        if known:
            latest = max(known)
            since = latest
            print(f"{BOLD}Incremental sync — fetching since {latest}{RESET}")
        else:
            since = None
            print(f"{BOLD}First sync — fetching all available data{RESET}")
        mode = "w" if not known else "a"

    rows = fetch_history(TMP_DB, since_date=since)
    cleanup_tmp()

    if not rows:
        print(f"{DIM}No new data to sync.{RESET}")
        return

    if mode == "a":
        known = existing_dates()
        rows = [r for r in rows if r[0] not in known]

    if not rows:
        print(f"{DIM}No new data to sync.{RESET}")
        return

    write_header = (mode == "w") or not CSV_PATH.exists()
    with open(CSV_PATH, mode, newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(row)

    days = sorted(set(r[0] for r in rows))
    print(f"\n{GREEN}✓ Synced {len(rows)} rows across {len(days)} days{RESET}")
    print(f"  Saved to: {CSV_PATH}\n")

    # Top 10 domains summary
    domain_totals = {}
    for _, domain, visits, total_mins in rows:
        entry = domain_totals.setdefault(domain, [0, 0.0])
        entry[0] += visits
        entry[1] += total_mins

    top = sorted(domain_totals.items(), key=lambda x: -x[1][1])[:10]
    print(f"  Top domains (by time):")
    for domain, (visits, total_mins) in top:
        bar = "█" * max(1, int(total_mins / 10))
        print(f"    {domain:<35} {total_mins:>6.0f} min  {DIM}{bar}{RESET}")
    print()


if __name__ == "__main__":
    main()
