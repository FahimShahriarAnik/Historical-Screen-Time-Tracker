# Screen Time Tracker

Personal, local-only tracker for three sources: **iPhone** (Screen Time screenshots), **Mac apps** (macOS `knowledgeC.db`) and **Chrome** (browser history). One dashboard with Mac | iPhone tabs.

## Routine — every 3 weeks

1. **iPhone:** Settings → Screen Time → See All App & Website Activity → screenshot every **Day** and every full **Week** → AirDrop to the Mac → move them into `mobile time tracker/`.
2. **Mac:** quit Chrome, then in Terminal:
   ```bash
   cd ~/"Historical Screen Time Tracker" && python3 scripts/sync_all.py
   ```
   Check the iPhone table, type `y`. Mac + Chrome sync on their own.
3. **Dashboard** opens at `http://localhost:8000/dashboard/`. Ctrl+C in Terminal when done.

**Why every 3 weeks:** the sources delete old data. iOS shows only the current week plus the 3 before it, macOS keeps about 30 days and Chrome about 90. Every sync only *appends* finished days (never today) and never rewrites rows already saved.

## One-time setup
- **Full Disk Access** for Terminal: System Settings → Privacy & Security → Full Disk Access (needed to read `knowledgeC.db`).
- **Python packages:** `pip3 install numpy pillow`, used by the screenshot import.
- **Xcode Command Line Tools** (`xcode-select --install`): the import compiles a small Apple Vision OCR helper once.

## Scripts
| Script | What it does |
|---|---|
| `scripts/sync_all.py` | The whole routine: iPhone import (asks before writing) → Mac → Chrome → dashboard. `--no-serve` skips the dashboard |
| `scripts/import_iphone.py` | Screenshots → `data/`. `--dry-run` previews. Reads only the top level of `mobile time tracker/`. `sync_all.py` moves imported shots to `imported/<date>/` |
| `scripts/sync_mac.py` | Appends finished days from `knowledgeC.db` |
| `scripts/sync_chrome.py` | Appends finished days from Chrome's history DB (Default profile) |
| `scripts/log.py` | Manual fallback: type one iPhone week in by hand |

⚠ `--full` on either sync script **deletes** everything older than what the source still holds (about 30 days for Mac, 90 for Chrome). Back up `data/` first if you ever need it.

## Data (`data/`, gitignored — back up separately)

**`screentime.csv`** — iPhone, one row per day. Rows 2026-04-06 → 04-12 are synthetic sample data; real data starts 2026-10-12.
- `date`, `week_start` (Monday), `total_mins` (exact, from the screenshot)
- `cat_social`, `cat_entertainment`, `cat_productivity`: filled when the category is in that day's top 3. Categories don't have to add up to the total.
- `pick_12am` … `pick_11pm`, `app1_name`/`app1_mins` … `app5_*`, `cat_other`, `first_app`, `exercise_yn`: only filled by `log.py`, blank for screenshot imports
- `notes`: `screenshot import` for imported rows

**`iphone_categories.csv`** — `date, rank, category, mins`: the top 3 categories exactly as iOS shows them, including Travel and Other.

**`iphone_hourly.csv`** — `date, hour, metric, value, estimated`. `screen_mins` per hour, **estimated** from the bar heights. A day is kept only if its bars add up to within max(5 min, 3%) of the exact total. Long format, so pickups and notifications can be added later as new `metric` values.

**`mac_usage.csv`** — one row per app per day: `date, app_name, bundle_id, mins, sessions, first_use, last_use`.

**`mac_sessions.csv`** — one row per app session: `date, hour, app_name, bundle_id, session_mins`. Feeds the daily rhythm chart, the 14-day grid and the focus stats.

**`chrome_history.csv`** — one row per domain per day: `date, domain, visits, total_mins`. Each page visit is capped at 10 min, because Chrome counts how long a tab is open, not attention.

## Thresholds (iPhone)
Under 120 min a day is good · 120–240 is watch it · over 240 is a red day. The Maps app is excluded from all rankings.
