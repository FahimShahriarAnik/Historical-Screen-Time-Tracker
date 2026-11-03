# Decisions & Insights

Last checked: **2026-11-03** (result below). Re-check whenever you want, no fixed date.

---

## Insights acted on

**Chrome tab accumulation**
- Open tabs were inflating usage (blackbox.ai: 53h, was just a sitting tab)
- Lowered cap to 10 min/navigation in `sync_chrome.py`
- Started closing Chrome when not actively using it

**WhatsApp: Mac vs phone**
- Considered moving it off Mac to cut interruptions
- Decided against — moving to phone increases pickups, which works against the iPhone goal
- Stays on Mac, notifications muted

**VS Code fragmentation**
- 88% of sessions under 5 min, zero over 25 min
- Caused by two things: reactive pings + self-interruption from mid-work ideas
- Slack kept as-is (professor only, no waste there)

---

## Decision

The urge to message someone mid-work is the real problem — usually triggered by avoiding something hard, not genuine urgency.

**The fix:**
- When an idea to message someone comes up mid-work → write it in a "messages to send" section in the daily Obsidian note
- Don't send. Capture and return to work.
- Send during natural windows:
  - **8am–12pm** — family (Bangladesh)
  - **8pm onward** — everyone else

**Check (planned for 2026-05-12, done 2026-11-03 on Oct 4 – Nov 2 Mac data):**

| | April (before) | October (after) | Target | |
|---|---|---|---|---|
| WhatsApp sessions / 30 days | ~570 | ~270 | drop | ✓ halved |
| VS Code avg session | 1.4 min | 2.5 min | > 5 min | ✗ not yet |
| VS Code sessions ≥ 25 min | 0 | 11 | — | improving |

WhatsApp sessions roughly halved. VS Code focus is better but still fragmented (84% of sessions are under 5 min).

---

## Dashboard performance ceiling (note, 2026-04-27)

The dashboard does **all analysis in the browser on every page load** — `python3 -m http.server` is just static files. CSVs are reparsed and every chart recomputed from scratch each refresh.

**Growth rate (measured at 43 days of data):**
- `mac_sessions.csv`: ~8.6 KB / 190 rows per day (the heavy one)
- `chrome_history.csv`: ~1.3 KB / 37 rows per day
- `mac_usage.csv`: ~0.7 KB / 10 rows per day
- Total: ~10.6 KB/day → ~3.8 MB/year

**Storage:** never the bottleneck. 10 years ≈ 38 MB of CSV. Ignore.

**Browser performance ceiling:**
| sessions rows | ≈ duration | feel |
|---|---|---|
| ~8K (today)  | 43 days   | instant |
| ~100K        | ~1.5 yr   | ~400ms, slight pause |
| ~500K        | ~7 yr     | ~2 sec, noticeable |
| ~1M+         | 14+ yr    | sluggish |

**Why it slows down:** each chart independently filters the full sessions array. The fortnight comparison alone filters it 4×. Across ~10 builders the redundant scans add up.

**Trigger to act:** when refreshes start feeling sluggish (or sessions row count crosses ~100K — roughly mid-2027 at current pace).

**The fix when needed:** pre-bucket sessions into `byDate[date] = [...]` once after `parseCSV`, then have every builder read from the map instead of `.filter()`-ing the array. ~10–20× speedup, pushes the comfortable ceiling to ~10 years. Don't do it before that — premature optimization.
