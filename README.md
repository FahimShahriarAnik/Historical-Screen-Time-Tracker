# Screen Time Tracker

Two data sources: iPhone (manual) and Mac (automatic).

## Folder Structure
```
screentime/
├── data/
│   ├── screentime.csv        ← iPhone data (manual weekly entry)
│   ├── mac_usage.csv         ← Mac data, one row per app per day
│   ├── mac_sessions.csv      ← Mac session-level data (per-session granularity)
│   └── chrome_history.csv    ← Chrome domain data, one row per domain per day
├── dashboard/
│   └── index.html            ← Mac dashboard (serve via local server)
├── scripts/
│   ├── log.py                ← run every Sunday for iPhone data
│   ├── sync_mac.py           ← sync Mac usage from knowledgeC.db
│   └── sync_chrome.py        ← sync Chrome history
└── README.md
```

## Setup
1. Grant Full Disk Access (one-time) — needed for Mac auto-sync:
   - System Settings > Privacy & Security > Full Disk Access
   - Enable Terminal and/or Visual Studio Code
2. Sync data and open dashboard:
   ```bash
   python3 scripts/sync_mac.py
   python3 scripts/sync_chrome.py   # close Chrome first for best results
   cd /path/to/project && python3 -m http.server 8000
   # open http://localhost:8000/dashboard/
   ```

## Mac Data (automatic)

```bash
python3 scripts/sync_mac.py         # incremental sync (new days only)
python3 scripts/sync_mac.py --full  # overwrite with full history
```

Writes two files:
- `data/mac_usage.csv` — one row per app per day
- `data/mac_sessions.csv` — individual sessions (drives daily-rhythm chart, 14-day activity grid, focus-quality stats)

Reads from macOS `knowledgeC.db`. One row per app per day:

| Column | Description | Example |
|---|---|---|
| `date` | The day | `2026-04-06` |
| `app_name` | Friendly app name | `Chrome` |
| `bundle_id` | macOS bundle identifier | `com.google.Chrome` |
| `mins` | Minutes of usage | `106.1` |
| `sessions` | Number of focus sessions | `19` |
| `first_use` | First use time that day | `00:50:54` |
| `last_use` | Last use time that day | `03:45:15` |

## iPhone Data (manual, every Sunday, ~10 min)

```bash
python3 scripts/log.py
```

The script walks you through each day (Mon-Sun). You enter everything from the iPhone Screen Time UI.

After logging, commit:
```bash
git add data/
git commit -m "week of 2026-04-13"
git push
```

### iPhone Column Reference

#### Meta
| Column | Description | Example |
|---|---|---|
| `date` | The specific day | `2026-04-06` |
| `week_start` | Monday of that week | `2026-04-06` |

#### Screen Time
| Column | Description | Example |
|---|---|---|
| `total_mins` | Total screen time in minutes | `210` |

#### Hourly Pickups
`pick_12am` through `pick_11pm` — number of times you picked up phone in that hour.
Read from the bar chart in Screen Time > Pickups. Eyeball each bar.

#### Top 5 Apps
| Column | Description |
|---|---|
| `app1_name` | Name of #1 most-used app |
| `app1_mins` | Minutes spent on it |
| ... | repeat for app2 through app5 |

#### Categories (minutes)
| Column | Description |
|---|---|
| `cat_social` | Social Networking total mins |
| `cat_entertainment` | Entertainment total mins |
| `cat_productivity` | Productivity & Finance total mins |
| `cat_other` | Everything else |

Categories may not sum to `total_mins` — gaps are expected.

#### Behavioral
| Column | Description | Example |
|---|---|---|
| `first_app` | First app you opened that day | `Instagram` |
| `exercise_yn` | Did you exercise? | `Y` or `N` |
| `notes` | Free text, anything notable | `felt restless after 9pm` |

## Thresholds
- Under 120 mins (2 hrs) — good day
- 120-240 mins — watch it
- Over 240 mins (4 hrs) — freak out mode

## Chrome Data (automatic)

```bash
python3 scripts/sync_chrome.py         # incremental sync
python3 scripts/sync_chrome.py --full  # overwrite with full history
```

Close Chrome before running (or the DB may be locked). Writes `data/chrome_history.csv`:

| Column | Description | Example |
|---|---|---|
| `date` | The day | `2026-04-06` |
| `domain` | Bare domain | `github.com` |
| `visits` | Page navigations | `14` |
| `total_mins` | Time on domain (30 min/visit cap) | `38.2` |

Note: Chrome's `visit_duration` counts wall-time a tab is open, not active attention.
Each visit is capped at 30 minutes to filter out background/idle tabs.

## Excluded Apps
- Maps (required navigation, not discretionary)

## Computed Fields (auto in dashboard)
- Morning pickups (sum of pick_6am to pick_11am)
- Evening pickups (sum of pick_6pm to pick_11pm)
- Weekly avg screen time
- Exercise vs screen time correlation
