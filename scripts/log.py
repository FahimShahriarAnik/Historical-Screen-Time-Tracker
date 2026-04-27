#!/usr/bin/env python3
"""
Interactive weekly screen time logger.
Run every Sunday to log Mon-Sun screen time data.

Usage:
    python3 scripts/log.py                    # current week (Mon of this week)
    python3 scripts/log.py --week 2026-04-06  # specific week starting date
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- Constants ---

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_DIR.parent / "data" / "screentime.csv"

HOUR_LABELS = [
    "12 AM", " 1 AM", " 2 AM", " 3 AM", " 4 AM", " 5 AM",
    " 6 AM", " 7 AM", " 8 AM", " 9 AM", "10 AM", "11 AM",
    "12 PM", " 1 PM", " 2 PM", " 3 PM", " 4 PM", " 5 PM",
    " 6 PM", " 7 PM", " 8 PM", " 9 PM", "10 PM", "11 PM",
]

PICKUP_COLS = [
    "pick_12am", "pick_1am", "pick_2am", "pick_3am", "pick_4am", "pick_5am",
    "pick_6am", "pick_7am", "pick_8am", "pick_9am", "pick_10am", "pick_11am",
    "pick_12pm", "pick_1pm", "pick_2pm", "pick_3pm", "pick_4pm", "pick_5pm",
    "pick_6pm", "pick_7pm", "pick_8pm", "pick_9pm", "pick_10pm", "pick_11pm",
]

CSV_HEADER = [
    "date", "week_start", "total_mins",
    *PICKUP_COLS,
    "app1_name", "app1_mins", "app2_name", "app2_mins",
    "app3_name", "app3_mins", "app4_name", "app4_mins",
    "app5_name", "app5_mins",
    "cat_social", "cat_entertainment", "cat_productivity", "cat_other",
    "first_app", "exercise_yn", "notes",
]

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


# --- Input helpers ---

def input_int(prompt, default=None):
    """Prompt for an integer. Enter accepts default (or 0 if no default)."""
    if default is not None:
        full_prompt = f"  {prompt} [{default}]: "
    else:
        full_prompt = f"  {prompt}: "

    while True:
        raw = input(full_prompt).strip()
        if raw == "":
            return default if default is not None else 0
        try:
            return int(raw)
        except ValueError:
            print(f"    {DIM}Enter a number{RESET}")


def input_str(prompt, default=None):
    """Prompt for a string. Enter accepts default (or empty)."""
    if default:
        full_prompt = f"  {prompt} [{default}]: "
    else:
        full_prompt = f"  {prompt}: "
    raw = input(full_prompt).strip()
    return raw if raw else (default or "")


def input_yn(prompt, default="N"):
    """Prompt for Y/N."""
    hint = "Y/n" if default.upper() == "Y" else "y/N"
    raw = input(f"  {prompt} [{hint}]: ").strip()
    if raw == "":
        return default.upper()
    return raw.upper()[0] if raw else default.upper()


def threshold_color(mins):
    """Return ANSI color code based on screen time thresholds."""
    if mins < 120:
        return GREEN
    elif mins <= 240:
        return YELLOW
    else:
        return RED


# --- Main logging flow ---

def log_day(day, week_start_str):
    """Interactive logging for a single day. Returns a dict of CSV values."""
    day_str = day.strftime("%Y-%m-%d")
    day_label = day.strftime("%A, %b %d")

    print(f"\n{BOLD}{'━' * 40}")
    print(f"  {day_label}")
    print(f"{'━' * 40}{RESET}\n")

    # --- Total mins ---
    total_mins = input_int("Total screen time (mins)")

    # --- Top 5 apps ---
    print(f"\n  {BOLD}Top 5 apps:{RESET}")
    apps = []
    for i in range(1, 6):
        name = input_str(f"  App {i} name (Enter to skip)")
        if not name:
            break
        mins = input_int(f"  App {i} mins")
        apps.append((name, mins))

    # Pad to 5
    while len(apps) < 5:
        apps.append(("", ""))

    # --- Pickups ---
    print(f"\n  {BOLD}Pickups:{RESET}")

    pickups = [0] * 24

    # Late night block (12am-5am)
    skip_late = input_yn("  Late night (12-5 AM) all zeros?", default="Y")
    if skip_late != "Y":
        for h in range(0, 6):
            pickups[h] = input_int(f"    {HOUR_LABELS[h]}")

    # Morning block (6am-11am)
    print(f"  {DIM}Morning (6-11 AM):{RESET}")
    for h in range(6, 12):
        pickups[h] = input_int(f"    {HOUR_LABELS[h]}")

    # Afternoon block (12pm-5pm)
    print(f"  {DIM}Afternoon (12-5 PM):{RESET}")
    for h in range(12, 18):
        pickups[h] = input_int(f"    {HOUR_LABELS[h]}")

    # Evening block (6pm-11pm)
    print(f"  {DIM}Evening (6-11 PM):{RESET}")
    for h in range(18, 24):
        pickups[h] = input_int(f"    {HOUR_LABELS[h]}")

    # --- Categories ---
    print(f"\n  {BOLD}Categories (mins):{RESET}")
    cat_social = input_int("Social")
    cat_ent = input_int("Entertainment")
    cat_prod = input_int("Productivity")
    cat_other = input_int("Other")

    # --- Behavioral ---
    first_app = input_str("First app opened")
    exercise = input_yn("Exercise?", default="N")
    notes = input_str("Notes (Enter to skip)")

    # --- Summary ---
    color = threshold_color(total_mins)
    print(f"\n  {color}✓ {day_label} — {total_mins} min{RESET}")

    return {
        "date": day_str,
        "week_start": week_start_str,
        "total_mins": total_mins,
        **{PICKUP_COLS[h]: pickups[h] for h in range(24)},
        "app1_name": apps[0][0], "app1_mins": apps[0][1],
        "app2_name": apps[1][0], "app2_mins": apps[1][1],
        "app3_name": apps[2][0], "app3_mins": apps[2][1],
        "app4_name": apps[3][0], "app4_mins": apps[3][1],
        "app5_name": apps[4][0], "app5_mins": apps[4][1],
        "cat_social": cat_social,
        "cat_entertainment": cat_ent,
        "cat_productivity": cat_prod,
        "cat_other": cat_other,
        "first_app": first_app,
        "exercise_yn": exercise,
        "notes": notes,
    }


def get_monday(ref_date=None):
    """Get the Monday of the week containing ref_date."""
    if ref_date is None:
        ref_date = datetime.now()
    return ref_date - timedelta(days=ref_date.weekday())


def existing_dates():
    """Read existing dates from CSV to avoid duplicates."""
    dates = set()
    if CSV_PATH.exists():
        with open(CSV_PATH, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "date" in row and row["date"]:
                    dates.add(row["date"])
    return dates


def write_rows(rows):
    """Append rows to the CSV file."""
    file_exists = CSV_PATH.exists()
    has_content = False
    if file_exists:
        with open(CSV_PATH, "r") as f:
            has_content = bool(f.read().strip())

    mode = "a" if has_content else "w"
    with open(CSV_PATH, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if not has_content:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive weekly screen time logger"
    )
    parser.add_argument(
        "--week",
        type=str,
        help="Week start date (Monday), e.g. 2026-04-06. Defaults to current week.",
    )
    args = parser.parse_args()

    if args.week:
        try:
            week_start = datetime.strptime(args.week, "%Y-%m-%d")
        except ValueError:
            print(f"Invalid date format: {args.week}. Use YYYY-MM-DD.")
            sys.exit(1)
        # Snap to Monday
        week_start = week_start - timedelta(days=week_start.weekday())
    else:
        week_start = get_monday()

    week_start_str = week_start.strftime("%Y-%m-%d")
    week_end = week_start + timedelta(days=6)

    print(f"\n{BOLD}Screen Time Logger{RESET}")
    print(f"Week: {week_start.strftime('%b %d')} (Mon) → {week_end.strftime('%b %d')} (Sun)")

    # Check for duplicates
    existing = existing_dates()
    week_dates = [(week_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    dupes = [d for d in week_dates if d in existing]
    if dupes:
        print(f"\n{YELLOW}Warning: these dates already exist in the CSV:{RESET}")
        for d in dupes:
            print(f"  - {d}")
        cont = input(f"\n  Skip existing dates and log the rest? [Y/n]: ").strip()
        if cont.upper() == "N":
            print("Aborted.")
            sys.exit(0)

    # Log each day
    rows = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")

        if day_str in dupes:
            print(f"\n  {DIM}Skipping {day.strftime('%A, %b %d')} (already logged){RESET}")
            continue

        row = log_day(day, week_start_str)
        rows.append(row)

    if not rows:
        print(f"\n{DIM}No new days to log.{RESET}")
        return

    # Write
    write_rows(rows)

    # Summary
    print(f"\n{BOLD}{'━' * 40}")
    print(f"  Week Summary")
    print(f"{'━' * 40}{RESET}")

    total_week = 0
    for row in rows:
        mins = int(row["total_mins"]) if row["total_mins"] else 0
        total_week += mins
        color = threshold_color(mins)
        day_dt = datetime.strptime(row["date"], "%Y-%m-%d")
        print(f"  {day_dt.strftime('%a %b %d')}  {color}{mins:>4} min{RESET}")

    avg = total_week // len(rows) if rows else 0
    avg_color = threshold_color(avg)
    print(f"\n  Daily avg: {avg_color}{BOLD}{avg} min{RESET}")
    print(f"\n  {GREEN}✓ {len(rows)} rows written to {CSV_PATH.name}{RESET}\n")


if __name__ == "__main__":
    main()
