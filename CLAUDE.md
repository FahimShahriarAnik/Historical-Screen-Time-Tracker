# CLAUDE.md — Screen Time Tracker

This file is read by Claude Code on every session. Do not delete it.

## Project Purpose
Personal screen time tracking system with two data sources:
- **iPhone** — manual weekly entry via `scripts/log.py` (~10 min/week)
- **Mac** — auto-synced from macOS via `scripts/sync_mac.py` + `scripts/sync_chrome.py`

Goals differ by device:
- iPhone: reduce to under 120 mins/day (freak out threshold: 240 mins)
- Mac: make usage **purposeful** — understand deep-work share, focus quality, and boundary drift

## Folder Structure
```
screentime/
├── CLAUDE.md
├── README.md
├── data/
│   ├── screentime.csv        ← iPhone data, one row per day (manual)
│   ├── mac_usage.csv         ← Mac data, one row per app per day (auto)
│   ├── mac_sessions.csv      ← Mac session-level data, one row per session (auto)
│   └── chrome_history.csv    ← Chrome domain data, one row per domain per day (auto)
├── dashboard/
│   └── index.html            ← Mac dashboard, served via python3 -m http.server 8000
└── scripts/
    ├── log.py                ← interactive weekly iPhone logger
    ├── sync_mac.py           ← auto-sync Mac usage from knowledgeC.db
    └── sync_chrome.py        ← auto-sync Chrome history from browser SQLite DB
```

## Data Sources

### iPhone (`data/screentime.csv`)
- Currently has **sample data** — real data will be populated weekly
- Never modify or delete existing rows
- All columns documented in `README.md`
- Categories (`cat_*`) are **not required** to sum to `total_mins` — gaps are expected
- Pickup columns use 12-hour AM/PM format: `pick_12am` through `pick_11pm`

### Mac (`data/mac_usage.csv` + `data/mac_sessions.csv`)
- Auto-populated by `scripts/sync_mac.py` from macOS `knowledgeC.db`
- `mac_usage.csv`: long format, one row per app per day (date, app_name, bundle_id, mins, sessions, first_use, last_use)
- `mac_sessions.csv`: session level, one row per session (date, hour, app_name, bundle_id, session_mins)
- Requires Full Disk Access for Terminal/VSCode
- Run `python3 scripts/sync_mac.py` to incrementally sync, `--full` to overwrite

### Chrome (`data/chrome_history.csv`)
- Auto-populated by `scripts/sync_chrome.py` from Chrome's SQLite history DB
- One row per domain per day (date, domain, visits, total_mins)
- Each visit duration capped at 10 min to exclude background/idle tabs
- Run with Chrome closed for most accurate data (DB may be locked)

## Weekly Workflow

### Every Sunday (~10 min) — iPhone data
1. `python3 scripts/log.py` — enter last week's Screen Time manually (Mon–Sun)
2. Data stays local — `data/*.csv` is gitignored. Back up separately if needed.

### Anytime — Mac + Chrome data (run after a work session or weekly)
1. `python3 scripts/sync_mac.py` — pulls new days from `knowledgeC.db`
2. `python3 scripts/sync_chrome.py` — pulls Chrome history (**close Chrome first**)
3. `cd /path/to/project && python3 -m http.server 8000`
4. Open `http://localhost:8000/dashboard/`

### After adding new apps to your Mac
- Edit the `CATS` object near the top of `dashboard/index.html` to assign the new app to a category
- Re-run `python3 scripts/sync_mac.py --full` if you want to backfill historical data

## Chrome Data — Assumptions & Limitations

**What Chrome tracks:** wall-clock time a tab/page was open — not whether you were actively looking at it. A tab left open overnight accumulates hours even if untouched.

**Cap applied:** each individual page navigation is capped at **10 min** before summing into `total_mins`. This eliminates the "idle open tab" effect (e.g. a tab left open 8 hours → 10 min, not 480 min). Multiple real navigations on the same site still accumulate normally (20 clicks on github.com = up to 200 min).

**Why 10 min:** a single page navigation rarely represents more than 10 min of focused attention. The cap is conservative but fair — it reduces inflation without zeroing out real use.

**Visit count is more reliable than time** for detecting actual usage patterns. If `total_mins / visits` is high (≥ 8 min/visit), the domain likely has idle open tabs. The dashboard flags these with ⚠.

**Re-run after cap change:** if you ever change `MAX_VISIT_DURATION_US` in `sync_chrome.py`, always re-run with `--full` to regenerate historical data from scratch. Incremental sync won't fix already-written rows.

## Dashboard
- `dashboard/index.html` — single file, Chart.js 4 via CDN
- Served via: `python3 -m http.server 8000` from project root
- Open: `http://localhost:8000/dashboard/`
- Mac app categories (Deep Work / Comms / Browse / Entertainment / System) defined in `CATS` near the top of index.html
- Chrome domain categories (Dev / Research / Entertainment / Comms / Shopping / Search / Other) defined in `CHROME_CATS` just below `CATS`. Suffix-matched: `console.firebase.google.com` → Dev. `app.blackbox.ai` and the Tab Suspender extension (`fiabciakcmgepblmdkmemdbbkilneeeh`) excluded as background noise.
- **Chrome → Mac category overrides** in `CHROME_TO_MAC_CAT` (just below `CHROME_CATS`). For Mac-side charts, Chrome time is *redistributed* across Mac categories using each day's domain breakdown (e.g., time on `claude.ai` counts as Deep Work, not Browse). Only affects: 7-day strip's % deep work, Daily Category Mix, Daily Rhythm, Weekday vs Weekend. The Chrome breakdown panel is untouched. To add/remove a domain → edit the `deep_work` / `entertainment` arrays in this constant. Anything not listed defaults to Browse.
- Sections (in order): 7-day summary, app categories explorer, daily category mix, focus quality, workday bounds, **daily rhythm (category × hour line)**, **last 14-day raw activity grid**, **fortnight comparison (last 14d vs prior 14d)**, **Chrome category breakdown**, app trends, weekday vs weekend
- Fortnight comparison shows: workday-boundary shift, focus-quality stat tiles (avg session / longest / per-day), top-10 apps movement table

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

## What to build next (priority order)
1. iPhone dashboard — charts from `screentime.csv` (once real data is populated)
2. Mac dashboard app drill-down — currently clicking an app chip opens a basic detail panel
   - Add a persistent app selector dropdown so any app can be explored without hunting for its chip
   - Expand the detail view: streak tracking (consecutive days used), time-of-day heatmap per app, week-over-week trend
3. Chrome category refinements (follow-up to v1 categorization)
   - Per-domain overrides for ambiguous sites (e.g. tag specific YouTube channels as Research)
   - 30-day stacked area chart of category mix over time (was deferred from v1)
4. Input validation script (optional later)
