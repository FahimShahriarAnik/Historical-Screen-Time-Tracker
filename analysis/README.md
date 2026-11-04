# Analysis

How the **Overview** tab and its two actions were chosen. This file explains the methods only. Results with personal numbers stay local in `analysis/out/` (gitignored, because this repo is public):
- `analysis/out/REPORT.md` is the full report.
- `analysis/out/exploratory/` holds the analysts' scripts, charts and tables.

## How it was done (2026-11-03)
1. **Blind pass.** Four analysts looked only at `data/` and the raw Mac activity log, knowledgeC (Opus / Sonnet / Fable models). They did not see the dashboard or any earlier findings. Each had one lens:
   - whole picture, across devices;
   - minute-level Mac events (this one stopped early on a rate limit);
   - iPhone category by hour, read from screenshot pixels;
   - unconventional methods.
2. **Cross-check.** Their findings were compared with the dashboard's existing analyses and with `decisions.md`. Each was marked as matched, refined, contradicted or new.
3. **Iterate.** The key claims were recomputed independently. The work-night gap was confirmed (permutation p ≈ 0.003). Incoming messages were found to be distorting the night window and were removed. The "evening focus is better" claim did not hold under the dashboard's own block definition, so the page shows it only when the data supports it.
4. **Build.** The Overview computes every number live from `data/*.csv`.

## Top 5 methods
1. **A night-anchored day.** Look at evening → morning as one unit and split it by what follows: a workday or a weekend. Daily totals hid the main pattern, because the weekend moves the same minutes into the daytime.
2. **Joining devices on exact timestamps.** The Mac's activity log also holds the iPhone's sent/received messages, calls and alarms. Joined with the hourly phone minutes, they show *what* night use is: not messaging. Joined with Mac screen-on intervals, they show the "every screen dark" window.
3. **Checking at several levels of detail.** The same phone-vs-Mac question was correlated per hour, per part of day, per day and per week. Per hour, phone and Mac substitute for each other; per day the link disappears (a Simpson's-paradox-style reversal).
4. **Reading pixels for finer detail, plus a bound.** Measuring the coloured bar segments gives category × hour minutes; iOS colours mean rank, not category. Rank arithmetic then gives a hard lower bound on uncategorized time: gray minus 9 × the #3 category.
5. **Reconstructing focus blocks and what ends them.** Exact Mac intervals are merged into blocks, allowing ≤ 3-minute detours. The app that follows each block shows what broke it (Kaplan–Meier / competing-risks style).

Also used:
- variance decomposition of the daily total by part of day;
- a double-plotted actogram (a sleep-research chart);
- Markov chains, change points, Gini/Lorenz concentration;
- bootstrap confidence intervals, permutation tests and Benjamini–Hochberg correction (n = 21 iPhone days, so effect sizes and intervals are always reported).

## Top 5 visualizations
1. **Night profile:** phone minutes per hour from 6 PM to noon, nights before workdays vs nights before weekends, with the after-midnight band shaded.
2. **Screens-dark bar per night:** longest stretch with every device dark, coloured by what follows, against a 7-hour line.
3. **Action trackers:** one bar per night or weekday with a target line and a "started" marker. They are the feedback loop.
4. **Actogram:** days as rows, double-plotted, Mac and iPhone layers plus rest markers. Best for spotting drift. It's in `exploratory/`; too dense for the Overview.
5. **Simpson forest plot:** the phone–Mac correlation at each level of detail. Used to make the decision; not shown on the Overview.

## Definitions used on the Overview (`OV` in `dashboard/index.html`)
| Term | Definition |
|---|---|
| After midnight | iPhone minutes 00:00–05:59, assigned to the morning they end in |
| Work night | the night before Mon–Fri (Sun–Thu nights) |
| Screens dark | longest stretch from 6 PM to 2 PM next day that touches 05:00–08:00 and has: no phone hour with ≥ 2 min, no Mac screen-on, no *outgoing* iPhone message or call. Morning alarms end it. Phone use in a boundary hour is assumed to sit at its far side. Hour-level phone data → about ±30 min |
| Focus block | Mac "Build" apps (code, notes, papers, AI coding apps; not Chrome) back-to-back, detours ≤ 3 min, length = wall-clock span |
| Phone in Mac gaps | inside each day's first→last Mac hour: phone min/h in hours with Mac < 5 min vs hours with Mac ≥ 30 min |
| No-category floor | per day max(0, gray − 9 × the #3 category's minutes) |

## Not done yet
- Minute-level Mac interruption chains (the analyst was cut off).
- Pickups and notifications.
- Per-app iPhone data: the Week view's "Most Used" list, or tapping an hour bar.
- Whether the uncategorized night time is one app.
- Anything needing more than 21 iPhone days: trend, seasonality, weekday effects with real power.
