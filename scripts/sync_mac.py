#!/usr/bin/env python3
"""
Sync Mac screen time data from knowledgeC.db into data/mac_usage.csv.

Reads app usage history from macOS Knowledge Store and writes one row
per app per day. Run anytime — it only appends finished days (never today)
that aren't already in the CSV. macOS keeps only ~30 days.

Usage:
    python3 scripts/sync_mac.py             # append new finished days
    python3 scripts/sync_mac.py --full      # DESTRUCTIVE: rebuild CSV from the ~30 days macOS still has

Requires: Full Disk Access for Terminal/VSCode
  System Settings > Privacy & Security > Full Disk Access
"""

import argparse
import csv
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_DIR.parent / "data" / "mac_usage.csv"
SESSIONS_CSV_PATH = SCRIPT_DIR.parent / "data" / "mac_sessions.csv"
KNOWLEDGE_DB = Path.home() / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db"

# Core Data epoch
EPOCH = datetime(2001, 1, 1)

CSV_HEADER = ["date", "app_name", "bundle_id", "mins", "sessions", "first_use", "last_use"]
SESSIONS_HEADER = ["date", "hour", "app_name", "bundle_id", "session_mins"]

# Bundle ID -> friendly name
BUNDLE_TO_NAME = {
    "com.google.Chrome": "Chrome",
    "com.microsoft.VSCode": "VS Code",
    "md.obsidian": "Obsidian",
    "net.whatsapp.WhatsApp": "WhatsApp",
    "com.anthropic.claudefordesktop": "Claude",
    "com.apple.finder": "Finder",
    "com.tinyspeck.slackmacgap": "Slack",
    "us.zoom.xos": "Zoom",
    "com.apple.Preview": "Preview",
    "com.apple.MobileSMS": "Messages",
    "com.apple.Notes": "Notes",
    "com.apple.mail": "Mail",
    "com.apple.Safari": "Safari",
    "com.apple.Terminal": "Terminal",
    "com.apple.systempreferences": "System Settings",
    "com.apple.archiveutility": "Archive Utility",
    "com.apple.clock": "Clock",
    "com.apple.Music": "Music",
    "com.apple.podcasts": "Podcasts",
    "com.apple.iCal": "Calendar",
    "com.apple.reminders": "Reminders",
    "com.apple.Photos": "Photos",
    "com.apple.QuickTimePlayerX": "QuickTime",
    "com.apple.printcenter": "Print Center",
    "com.jetbrains.pycharm": "PyCharm",
    "com.superduper.superwhisper": "SuperWhisper",
    "ru.keepcoder.Telegram": "Telegram",
    "com.apple.ActivityMonitor": "Activity Monitor",
    "com.apple.dt.Xcode": "Xcode",
    "com.figma.Desktop": "Figma",
    "com.spotify.client": "Spotify",
    "com.linear": "Linear",
    "com.notion.Notion": "Notion",
    "com.1password.1password": "1Password",
    "com.openai.chat": "ChatGPT",
    "com.apple.FaceTime": "FaceTime",
    "com.hnc.Discord": "Discord",
}

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def friendly_name(bundle_id):
    if bundle_id in BUNDLE_TO_NAME:
        return BUNDLE_TO_NAME[bundle_id]
    # Fallback: last component, capitalized
    parts = bundle_id.rsplit(".", 1)
    return parts[-1].replace("-", " ").title() if parts else bundle_id


def existing_dates(path=None):
    """Read dates already in a CSV file."""
    if path is None:
        path = CSV_PATH
    dates = set()
    if path.exists():
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "date" in row and row["date"]:
                    dates.add(row["date"])
    return dates


def fetch_usage(conn, since_date=None):
    """Fetch app usage data from knowledgeC.db, optionally filtered by date."""
    query = """
        SELECT
            date(ZSTARTDATE + 978307200, 'unixepoch', 'localtime') as day,
            ZVALUESTRING as bundle_id,
            ROUND(SUM(ZENDDATE - ZSTARTDATE) / 60.0, 1) as total_mins,
            COUNT(*) as sessions,
            MIN(time(ZSTARTDATE + 978307200, 'unixepoch', 'localtime')) as first_use,
            MAX(time(ZENDDATE + 978307200, 'unixepoch', 'localtime')) as last_use
        FROM ZOBJECT
        WHERE ZSTREAMNAME = '/app/usage'
          AND ZENDDATE > ZSTARTDATE
    """
    params = ()

    if since_date:
        ts = (datetime.strptime(since_date, "%Y-%m-%d") - EPOCH).total_seconds()
        query += " AND ZSTARTDATE >= ?"
        params = (ts,)

    query += """
        GROUP BY day, bundle_id
        ORDER BY day, total_mins DESC
    """

    return conn.execute(query, params).fetchall()


def fetch_sessions(conn, since_date=None):
    """Fetch individual app sessions for hourly breakdown."""
    query = """
        SELECT
            date(ZSTARTDATE + 978307200, 'unixepoch', 'localtime') as day,
            CAST(strftime('%H', ZSTARTDATE + 978307200, 'unixepoch', 'localtime') AS INTEGER) as hour,
            ZVALUESTRING as bundle_id,
            ROUND((ZENDDATE - ZSTARTDATE) / 60.0, 2) as session_mins
        FROM ZOBJECT
        WHERE ZSTREAMNAME = '/app/usage'
          AND ZENDDATE > ZSTARTDATE
    """
    params = ()

    if since_date:
        ts = (datetime.strptime(since_date, "%Y-%m-%d") - EPOCH).total_seconds()
        query += " AND ZSTARTDATE >= ?"
        params = (ts,)

    query += " ORDER BY day, hour, bundle_id"

    return conn.execute(query, params).fetchall()


def threshold_color(mins):
    if mins < 120:
        return GREEN
    elif mins <= 240:
        return YELLOW
    else:
        return RED


def main():
    parser = argparse.ArgumentParser(description="Sync Mac screen time from knowledgeC.db")
    parser.add_argument("--full", action="store_true", help="Overwrite CSV with full history")
    args = parser.parse_args()

    if not KNOWLEDGE_DB.exists():
        print(f"{RED}knowledgeC.db not found{RESET}")
        sys.exit(1)

    try:
        conn = sqlite3.connect(f"file:{KNOWLEDGE_DB}?mode=ro", uri=True)
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
        print(f"{RED}Cannot open knowledgeC.db: {e}{RESET}")
        print(f"{DIM}Grant Full Disk Access: System Settings > Privacy & Security > Full Disk Access{RESET}")
        sys.exit(1)

    # Determine what to sync
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

    rows = fetch_usage(conn, since_date=since)
    session_rows = fetch_sessions(conn, since_date=since)
    conn.close()

    if not rows and not session_rows:
        print(f"{DIM}No new data to sync.{RESET}")
        return

    # Only finished days — a day synced mid-day would stay partial forever
    today = date.today().isoformat()
    rows = [r for r in rows if r[0] < today]
    session_rows = [r for r in session_rows if r[0] < today]

    # Filter out dates we already have (for incremental)
    if mode == "a":
        known = existing_dates()
        rows = [r for r in rows if r[0] not in known]
        known_sessions = existing_dates(SESSIONS_CSV_PATH)
        session_rows = [r for r in session_rows if r[0] not in known_sessions]

    if not rows:
        print(f"{DIM}No new data to sync.{RESET}")
        return

    # Write
    write_header = (mode == "w") or not CSV_PATH.exists()
    with open(CSV_PATH, mode, newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_HEADER)
        for day, bundle_id, mins, sessions, first_use, last_use in rows:
            name = friendly_name(bundle_id)
            writer.writerow([day, name, bundle_id, mins, sessions, first_use, last_use])

    # Summary
    days = sorted(set(r[0] for r in rows))
    print(f"\n{GREEN}✓ Synced {len(rows)} rows across {len(days)} days{RESET}\n")

    # Daily totals
    day_totals = {}
    for day, bundle_id, mins, sessions, _, _ in rows:
        day_totals[day] = day_totals.get(day, 0) + mins

    for day in days:
        total = day_totals[day]
        color = threshold_color(total)
        bar = "█" * int(total / 30)
        print(f"  {day}  {color}{total:>6.0f} min{RESET}  {DIM}{bar}{RESET}")

    avg = sum(day_totals.values()) / len(day_totals)
    avg_color = threshold_color(avg)
    print(f"\n  Daily avg: {avg_color}{BOLD}{avg:.0f} min{RESET}")
    print(f"  Saved to: {CSV_PATH}\n")

    # Write sessions CSV
    if session_rows:
        sessions_write_header = (mode == "w") or not SESSIONS_CSV_PATH.exists()
        with open(SESSIONS_CSV_PATH, mode, newline="") as f:
            writer = csv.writer(f)
            if sessions_write_header:
                writer.writerow(SESSIONS_HEADER)
            for day, hour, bundle_id, session_mins in session_rows:
                name = friendly_name(bundle_id)
                writer.writerow([day, hour, name, bundle_id, session_mins])
        print(f"  {GREEN}✓ {len(session_rows)} session rows → {SESSIONS_CSV_PATH.name}{RESET}\n")


if __name__ == "__main__":
    main()
