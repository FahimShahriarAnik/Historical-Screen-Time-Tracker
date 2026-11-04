# CLAUDE.md — Screen Time Tracker

This file is read by Claude Code on every session. Do not delete it.

## Project Purpose
Personal screen time tracking system with two data sources:
- **iPhone** — Screen Time screenshots every 3 weeks → `scripts/import_iphone.py` (manual `scripts/log.py` still works)
- **Mac** — synced from macOS via `scripts/sync_mac.py` + `scripts/sync_chrome.py`
- All of it runs in one command: `python3 scripts/sync_all.py` (see Routine)

Goals differ by device:
- iPhone: reduce to under 120 mins/day (freak out threshold: 240 mins)
- Mac: make usage **purposeful** — understand deep-work share, focus quality, and boundary drift

## Folder Structure
```
screentime/
├── CLAUDE.md
├── README.md                 ← user-facing: routine, setup, column reference
├── future_plan.md            ← the only plan; keep it to ≤3 items
├── decisions.md              ← behaviour decisions + check results
├── data/
│   ├── screentime.csv        ← iPhone data, one row per day (screenshot import or log.py)
│   ├── iphone_categories.csv ← iPhone top-3 categories per day, exact (screenshot import)
│   ├── iphone_hourly.csv     ← iPhone minutes per hour, ESTIMATED from bar heights (screenshot import)
│   ├── mac_usage.csv         ← Mac data, one row per app per day (auto)
│   ├── mac_sessions.csv      ← Mac session-level data, one row per session (auto)
│   ├── chrome_history.csv    ← Chrome domain data, one row per domain per day (auto)
│   └── device_events.csv     ← exact-time events: Mac app/screen + iPhone messages/calls/alarms/Bluetooth (auto, sync_mac.py)
├── mobile time tracker/       ← new iPhone screenshots go here; imported ones move to imported/<date>/ (gitignored)
├── dashboard/
│   └── index.html            ← Overview (default) | Mac | iPhone dashboard
├── analysis/README.md         ← how the Overview + its two actions were chosen (methods only; results in gitignored analysis/out/)
└── scripts/
    ├── sync_all.py           ← the whole routine: iPhone import → Mac → Chrome → dashboard
    ├── log.py                ← interactive weekly iPhone logger (manual alternative)
    ├── import_iphone.py      ← iPhone screenshots → data/ (append-only, --dry-run to preview)
    ├── ocr_helper.swift      ← Apple Vision OCR used by import_iphone.py (compiled to scripts/.bin/)
    ├── sync_mac.py           ← append finished days from knowledgeC.db
    └── sync_chrome.py        ← append finished days from Chrome's history DB
```

## Data Sources

### iPhone (`data/screentime.csv`)
- Rows 2026-04-06 → 2026-04-12 are **sample data** (synthetic) — kept untouched, excluded by the dashboard (`IPHONE_SAMPLE`)
- Real data starts 2026-10-12, imported from screenshots by `scripts/import_iphone.py`
- Never modify or delete existing rows
- All columns documented in `README.md`
- Categories (`cat_*`) are **not required** to sum to `total_mins` — gaps are expected
- Pickup columns use 12-hour AM/PM format: `pick_12am` through `pick_11pm`

### iPhone screenshot import (`scripts/import_iphone.py`)
- Reads Day-view screenshots (exact total + top-3 categories + hourly bar chart) and Week views (checksum only)
- `screentime.csv` gets total_mins + cat_social/entertainment/productivity when in the top 3; pickups/apps stay blank
- `iphone_categories.csv` (date, rank, category, mins) keeps every shown category incl. Travel/Other
- `iphone_hourly.csv` (date, hour, metric, value, estimated) — `screen_mins` measured from bar pixels; accepted only if the day's bars sum within max(5 min, 3%) of the exact total. Long format so pickups/notifications can be added later as new `metric` values
- Skips "Today" (partial day) and dates already present; handles 23/25-hour DST days
- Reads only the top level of `mobile time tracker/` (so `imported/` is ignored); with several shots of one day it keeps the most complete one (has chart + total), then the latest
- iOS shows only the current week + the 3 before it (Mon–Sun weeks; seen on 2026-11-02: oldest day was Mon Oct 12). Since the run day itself is skipped as "Today", a 4-week gap loses that day → the cadence is every 3 weeks

### Mac (`data/mac_usage.csv` + `data/mac_sessions.csv`)
- Auto-populated by `scripts/sync_mac.py` from macOS `knowledgeC.db`
- `mac_usage.csv`: long format, one row per app per day (date, app_name, bundle_id, mins, sessions, first_use, last_use)
- `mac_sessions.csv`: session level, one row per session (date, hour, app_name, bundle_id, session_mins)
- Requires Full Disk Access for Terminal/VSCode
- Appends **finished days only** (never today) that aren't in the CSV yet. A day synced mid-day used to stay partial forever; fixed 2026-11-03 and Nov 2 re-synced

### Chrome (`data/chrome_history.csv`)
- Auto-populated by `scripts/sync_chrome.py` from Chrome's SQLite history DB
- One row per domain per day (date, domain, visits, total_mins)
- Each visit duration capped at 10 min to exclude background/idle tabs
- Appends finished days only (never today). Default Chrome profile only
- Quit Chrome first for the most accurate data (open tabs haven't written their durations yet); the script copies the DB, so it still works with Chrome open

### Exact-time events (`data/device_events.csv`, from `sync_mac.py`)
- Columns `date,start,end,secs,device,stream,app,kind,dir`. `device` = Mac | iPhone | iPad | Watch — the iPhone syncs message/call/alarm/Bluetooth events into the Mac's knowledgeC, so this is free, exact-time iPhone data (no screen minutes though)
- `stream`: app (Mac foreground interval), screen (Mac on/off), media, notification, intent (`kind` Messages/Calls/Timers…, `dir` out/in), bluetooth
- Only timestamps, bundle ids, event types and direction — never message content, contacts or device names. Starts 2026-10-04 (knowledgeC keeps ~30 days, so it must be synced every ≤ 4 weeks)
- Incoming messages (`dir=in`) arrive while asleep (family in Bangladesh, UTC+6) — never treat them as "awake"

## Routine — every 3 weeks (user keeps the calendar reminder; next: Sun 2026-11-29)
Sources roll off: iPhone = current week + 3 before, Mac `knowledgeC.db` ≈ 30 days, Chrome ≈ 90 days.
1. iPhone: Settings → Screen Time → See All App & Website Activity → screenshot each **Day** + each full **Week** → AirDrop → move into `mobile time tracker/`
2. Quit Chrome. In Terminal (has Full Disk Access): `cd ~/"Historical Screen Time Tracker" && python3 scripts/sync_all.py` → check the iPhone table, type `y`
3. Dashboard opens at `http://localhost:8000/dashboard/` (`#iphone` = iPhone tab). Ctrl+C stops it. The script prints the next run date
- Never use `--full` on the sync scripts unless deliberately rebuilding — it deletes every row older than what the source still holds
- Data stays local — `data/*.csv` is gitignored. Back up separately if needed.

### After adding new apps to your Mac
- Edit the `CATS` object near the top of `dashboard/index.html` to assign the new app to a category. No re-sync needed — the dashboard categorises at load time

## Chrome Data — Assumptions & Limitations

**What Chrome tracks:** wall-clock time a tab/page was open — not whether you were actively looking at it. A tab left open overnight accumulates hours even if untouched.

**Cap applied:** each individual page navigation is capped at **10 min** before summing into `total_mins`. This eliminates the "idle open tab" effect (e.g. a tab left open 8 hours → 10 min, not 480 min). Multiple real navigations on the same site still accumulate normally (20 clicks on github.com = up to 200 min).

**Why 10 min:** a single page navigation rarely represents more than 10 min of focused attention. The cap is conservative but fair — it reduces inflation without zeroing out real use.

**Visit count is more reliable than time** for detecting actual usage patterns. If `total_mins / visits` is high (≥ 8 min/visit), the domain likely has idle open tabs. The dashboard flags these with ⚠.

**Cap change:** changing `MAX_VISIT_DURATION_US` only affects new rows. `--full` re-computes the old ones too, but **only for the ~90 days Chrome still has — every older row is deleted**. Back up `chrome_history.csv` first, or just accept that the cap changed on a given date.

## Dashboard
- `dashboard/index.html` — single file, Chart.js 4 via CDN
- Served by `scripts/sync_all.py` (or `python3 -m http.server 8000` from project root) → `http://localhost:8000/dashboard/`
- Each tab = **2 main charts + 4 supporting** (user's rule, 2026-11-04). No hour-by-hour heatmaps — the user found they reveal nothing
- **Overview** (default, `#overview`): phone/day vs goal + 3 facts · the **two actions** (started 2026-11-03; baseline = days before) each with a tracker chart · MAIN: night profile (Sun–Thu vs Fri–Sat nights), screens-dark hours per night · SUPPORTING: the 2 trackers, what ends a work stretch, phone in Mac-busy vs Mac-idle hours · 6 live findings. Tunables in the `OV` constant (start date, targets, focus-block rules, Build apps). Shared helpers `loadEvents()` / `workBlocks()`. Definitions: `analysis/README.md`. Never hard-code personal numbers — the repo is public
- **Mac** (`#mac`): 7-day strip · MAIN: daily category mix, day envelope (first → last activity, exact, 12:30 AM line) · SUPPORTING: work time by stretch length per week, month by month (deep work vs leisure), daily rhythm, Chrome breakdown · app categories (collapsed; click an app → App Detail)
- **iPhone** (`#iphone`, built lazily): tiles · MAIN: each day split after-midnight vs rest (goal lines, 7-day avg), when the phone is used (6 AM → 6 AM) · SUPPORTING: top-3 categories with the "in no category (at least)" floor + table, weekly average, weekdays vs weekends by part of day, messages sent per phone-hour · patterns, notes. Category colours in `IP_CATS` (validated palette — keep the order)
- Mac app categories (Deep Work / Comms / Browse / Entertainment / System) defined in `CATS` near the top of index.html
- Chrome domain categories (Dev / Research / Entertainment / Comms / Shopping / Search / Other) defined in `CHROME_CATS` just below `CATS`. Suffix-matched. `app.blackbox.ai` and the Tab Suspender extension (`fiabciakcmgepblmdkmemdbbkilneeeh`) excluded as background noise.
- **Chrome → Mac category overrides** in `CHROME_TO_MAC_CAT`: for Mac-side charts, Chrome time is redistributed across Mac categories using each day's domain breakdown (e.g. `claude.ai` counts as Deep Work). Anything not listed defaults to Browse.

## Thresholds
- Green: under 120 mins
- Yellow: 120–240 mins
- Red: over 240 mins

## Excluded from analysis
- `Maps` app usage — required navigation, not discretionary screen time
- Strip it from any app rankings or totals if it appears

## Versioning
- Backward compatible always — new columns added to the right, old charts never break
- Charts show data only from the first week their required columns appear

## What's next
See `future_plan.md` — the user wants it kept to ≤3 actions. Don't add items without asking; drop finished ones.
Parked on purpose (not in the plan): Chrome history gaps on 2026-10-05/06/23 (maybe another profile or incognito; the user declined reading other profiles), Mac app drill-down, Chrome category refinements.
