#!/usr/bin/env python3
"""
import_iphone.py — turn iPhone Screen Time screenshots into data rows.

Normally run via scripts/sync_all.py (every 3 weeks). iOS shows only the current
week + the 3 before it, so a longer gap loses days.
  1. iPhone → Settings → Screen Time → See All App & Website Activity.
     Day tab: screenshot every day (tap each bar, swipe back to earlier weeks).
     Week tab: screenshot each full week (used only as a checksum).
  2. Put the screenshots in `mobile time tracker/` (top level only — sync_all.py
     moves imported ones to `mobile time tracker/imported/<date>/`).
  3. python3 scripts/import_iphone.py --dry-run   # preview + checks, writes nothing
     python3 scripts/import_iphone.py             # append new days to data/

What it writes (append-only; dates already present are never touched):
  data/screentime.csv         one row per day: total_mins (exact) + cat_social /
                              cat_entertainment / cat_productivity when they're in
                              the day's top 3. Pickups / apps stay blank.
  data/iphone_categories.csv  date, rank, category, mins — the top 3 categories
                              exactly as shown (incl. Travel / Other / etc.)
  data/iphone_hourly.csv      date, hour, metric, value, estimated — minutes per
                              hour MEASURED FROM BAR HEIGHTS (estimated=Y).
                              Accepted only if the bars sum to within 5 min (or 3%,
                              whichever is larger) of the day's exact total.

"Today" screenshots are skipped (the day isn't over). Week views are checked
against the sum of their 7 days. Text is read with Apple's on-device Vision OCR
(scripts/ocr_helper.swift, compiled once into scripts/.bin/).
"""

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_DIR = ROOT / "mobile time tracker"
ST_CSV = DATA / "screentime.csv"
CAT_CSV = DATA / "iphone_categories.csv"
HOURLY_CSV = DATA / "iphone_hourly.csv"
OCR_SRC = ROOT / "scripts" / "ocr_helper.swift"
OCR_BIN = ROOT / "scripts" / ".bin" / "ocr_helper"

# Fallback only — the real header is read from screentime.csv so rows always line up with log.py.
ST_HEADER_FALLBACK = (
    ["date", "week_start", "total_mins"]
    + [f"pick_{h}" for h in ["12am"] + [f"{i}am" for i in range(1, 12)] + ["12pm"] + [f"{i}pm" for i in range(1, 12)]]
    + [f"app{i}_{k}" for i in range(1, 6) for k in ("name", "mins")]
    + ["cat_social", "cat_entertainment", "cat_productivity", "cat_other", "first_app", "exercise_yn", "notes"]
)
CAT_HEADER = ["date", "rank", "category", "mins"]
HOURLY_HEADER = ["date", "hour", "metric", "value", "estimated"]
ST_CAT_COLS = {"Social": "cat_social", "Entertainment": "cat_entertainment",
               "Productivity & Finance": "cat_productivity", "Productivity": "cat_productivity"}

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}
DAY_HDR = re.compile(r"^(Today|Yesterday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*([A-Za-z]+)\s+(\d{1,2})$")
WEEK_HDR = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})\s*[-–]\s*(?:[A-Za-z]{3,9}\.?\s+)?\d{1,2}\s+Average$")
DUR = re.compile(r"^\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*$")

GREEN, YELLOW, RED, DIM, BOLD, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"


def dur(text):
    m = DUR.match(text or "")
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def tol(total):
    """Allowed gap between summed hourly bars and the exact daily total."""
    return max(5, 0.03 * (total or 0))


def month_num(name):
    name = name.lower()
    for full, n in MONTHS.items():
        if full.startswith(name[:3]):
            return n
    return None


# ── OCR ────────────────────────────────────────────────────────────────────────
def ocr_binary():
    if not OCR_BIN.exists() or OCR_BIN.stat().st_mtime < OCR_SRC.stat().st_mtime:
        OCR_BIN.parent.mkdir(exist_ok=True)
        print(f"{DIM}Compiling OCR helper (one-time, ~10s)…{RESET}")
        subprocess.run(["swiftc", "-O", str(OCR_SRC), "-o", str(OCR_BIN)], check=True)
    return OCR_BIN


def ocr(paths):
    if not paths:
        return {}
    out = subprocess.run([str(ocr_binary()), *map(str, paths)], capture_output=True, text=True, check=True)
    res = {}
    for line in out.stdout.splitlines():
        o = json.loads(line)
        res[o["file"]] = sorted(o["lines"], key=lambda l: (l["y"], l["x"]))
    return res


# ── image helpers ─────────────────────────────────────────────────────────────
def capture_time(path):
    try:
        ex = Image.open(path).getexif()
        raw = ex.get_ifd(0x8769).get(36867) or ex.get(306)
        if raw:
            return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def measure_bars(path, chart_top_y, chart_bottom_y):
    """Minutes per hour from the Day view's hourly bar chart.
    chart_top_y / chart_bottom_y: normalized y range that contains the chart (from OCR anchors).
    Handles 23/25-hour DST days by counting hour slots per 6-hour section."""
    im = np.asarray(Image.open(path).convert("RGB")).astype(int)
    H, W, _ = im.shape
    y0, y1 = int(chart_top_y * H), int(chart_bottom_y * H)
    x0, x1 = int(0.05 * W), int(0.86 * W)
    reg = im[y0:y1, x0:x1]
    flat = reg.reshape(-1, 3)
    colors, counts = np.unique(flat, axis=0, return_counts=True)
    bg = colors[counts.argmax()]
    # gridline color = most common non-background color in rows that are mostly non-bg
    nonbg = (np.abs(reg - bg).sum(-1) > 12)
    line_rows = [i for i, f in enumerate(nonbg.mean(1)) if f > 0.85]
    if len(line_rows) < 2:
        raise ValueError("chart gridlines not found")
    grid = np.median(reg[line_rows[-1]], axis=0)
    is_grid = (np.abs(reg - grid) <= 8).all(-1)
    hrows = [y0 + i for i, f in enumerate(is_grid.mean(1)) if f > 0.5]
    groups = []
    for r in hrows:
        if groups and r - groups[-1][-1] <= 1:
            groups[-1].append(r)
        else:
            groups.append([r])
    top, base = groups[0][0], groups[-1][0]
    ppm = (base - top) / 60.0
    if ppm < 1:
        raise ValueError("chart scale not found")
    band = is_grid[top - y0 + 3: base - y0 - 2]
    vcols = [x0 + i for i, f in enumerate(band.mean(0)) if f > 0.3]
    vx = []
    for c in vcols:
        if vx and c - vx[-1][-1] <= 1:
            vx[-1].append(c)
        else:
            vx.append([c])
    vx = [sum(v) / len(v) for v in vx]
    if len(vx) < 5:
        raise ValueError(f"expected 5 vertical gridlines, found {len(vx)}")
    vx = vx[:5] if len(vx) == 5 else [vx[0]] + vx[-4:]
    sections = [vx[i + 1] - vx[i] for i in range(4)]
    unit = sorted(sections)[1] / 6  # median-ish 6-hour section
    slots_per = [round(s / unit) for s in sections]
    n = sum(slots_per)
    hours = {24: list(range(24)), 25: [0, 1, 1] + list(range(2, 24)), 23: [0, 1] + list(range(3, 24))}.get(n)
    if hours is None:
        raise ValueError(f"unexpected slot count {n}")
    centers = []
    for i, k in enumerate(slots_per):
        w = sections[i] / k
        centers += [vx[i] + (j + 0.5) * w for j in range(k)]
    mins = {h: 0.0 for h in range(24)}
    for h, cx in zip(hours, centers):
        best = 0
        for dx in (-2, 0, 2):
            x, y, run = int(cx) + dx, base - 1, 0
            while y > top - 5 and np.abs(im[y, x] - bg).sum() > 12:
                y -= 1
                run += 1
            best = max(best, run)
        mins[h] += min(best / ppm, 60.0)
    return mins, n


def crop_total(path, header_y, tmpdir):
    im = Image.open(path).convert("L")
    W, H = im.size
    box = (0, int((header_y + 0.012) * H), int(0.65 * W), int((header_y + 0.07) * H))
    c = ImageOps.invert(im.crop(box)).resize((int(0.65 * W) * 2, int(0.058 * H) * 2))
    out = Path(tmpdir) / f"{path.stem}_total.png"
    c.save(out)
    return out


# ── parsing ───────────────────────────────────────────────────────────────────
def parse(path, lines, cap):
    hdr = next((l for l in lines if 0.15 < l["y"] < 0.40 and (DAY_HDR.match(l["text"]) or l["text"].endswith("Average"))), None)
    if not hdr:
        return {"kind": "skip", "why": "not a Screen Time Day/Week view"}
    t = hdr["text"]
    m = DAY_HDR.match(t)
    if m:
        mo, dd = month_num(m.group(2)), int(m.group(3))
        d = date(cap.year, mo, dd)
        if d > cap.date():
            d = date(cap.year - 1, mo, dd)
        rec = {"kind": "day", "date": d, "today": m.group(1) == "Today", "hdr_y": hdr["y"]}
        below = [l for l in lines if hdr["y"] < l["y"] < hdr["y"] + 0.07 and dur(l["text"]) is not None and l["h"] > 0.025]
        rec["total"] = dur(below[0]["text"]) if below else None
        axis = [l for l in lines if re.fullmatch(r"12\s?AM", l["text"].replace(" ", " "))]
        upd = next((l for l in lines if l["text"].startswith("Updated")), None)
        ax_y = axis[-1]["y"] if axis else None
        rec["axis_y"] = ax_y
        lab60 = next((l for l in lines if l["text"] == "60m"), None)
        rec["chart"] = (lab60["y"] - 0.01 if lab60 else None, ax_y)
        cats = []
        if ax_y and upd:
            vals = [l for l in lines if ax_y < l["y"] < upd["y"] and dur(l["text"]) is not None]
            for v in vals:
                lab = [l for l in lines if v["y"] - 0.04 < l["y"] < v["y"] - 0.005 and abs(l["x"] - v["x"]) < 0.03 and dur(l["text"]) is None]
                if lab:
                    cats.append((v["x"], lab[0]["text"], dur(v["text"])))
        rec["cats"] = [(name, mins) for _, name, mins in sorted(cats)]
        return rec
    # week view
    if t == "Daily Average":
        return {"kind": "skip", "why": "current (incomplete) week"}
    if t.startswith("Last Week"):
        cap_mon = cap.date() - timedelta(days=cap.weekday())
        start = cap_mon - timedelta(days=7)
    else:
        w = WEEK_HDR.match(t)
        if not w:
            return {"kind": "skip", "why": f"unrecognized week header {t!r}"}
        mo, dd = month_num(w.group(1)), int(w.group(2))
        start = date(cap.year, mo, dd)
        if start > cap.date():
            start = date(cap.year - 1, mo, dd)
        start -= timedelta(days=start.weekday())
    tst = next((l for l in lines if l["text"] == "Total Screen Time"), None)
    total = None
    if tst:
        same = [l for l in lines if abs(l["y"] - tst["y"]) < 0.01 and dur(l["text"]) is not None]
        total = dur(same[0]["text"]) if same else None
    return {"kind": "week", "start": start, "total": total}


# ── csv helpers ───────────────────────────────────────────────────────────────
def existing_dates(path):
    if not path.exists():
        return set()
    with open(path, newline="") as f:
        return {r["date"] for r in csv.DictReader(f) if r.get("date")}


def append(path, header, rows):
    if not rows:
        return
    new = not path.exists() or not path.read_text().strip()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if new:
            w.writeheader()
        w.writerows(rows)


def st_header():
    if ST_CSV.exists():
        with open(ST_CSV, newline="") as f:
            h = next(csv.reader(f), None)
            if h:
                return h
    return ST_HEADER_FALLBACK


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Import iPhone Screen Time screenshots")
    ap.add_argument("folder", nargs="?", default=str(DEFAULT_DIR))
    ap.add_argument("--dry-run", action="store_true", help="parse and check only; write nothing")
    args = ap.parse_args()

    folder = Path(args.folder)
    files = sorted(p for p in folder.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if not files:
        sys.exit(f"No screenshots found in {folder}")
    print(f"{BOLD}Reading {len(files)} screenshots from {folder.name}/{RESET}")

    texts = ocr(files)
    days, weeks, skipped = {}, {}, []
    for p in files:
        cap = capture_time(p)
        rec = parse(p, texts.get(str(p), []), cap)
        rec["file"], rec["cap"] = p, cap
        if rec["kind"] == "day":
            if rec["today"]:
                skipped.append((p.name, f"{rec['date']} is today at capture time (partial day)"))
                continue
            # several shots of one day (e.g. scrolled down to Pickups): keep the most complete, then the latest
            def rank(r): return (None not in r["chart"], r["total"] is not None, r["cap"])
            prev = days.get(rec["date"])
            if not prev or rank(rec) > rank(prev):
                days[rec["date"]] = rec
        elif rec["kind"] == "week":
            weeks[rec["start"]] = rec
        else:
            skipped.append((p.name, rec["why"]))

    # hourly bars + total cross-check; re-OCR the big number when it's missing or disagrees
    for d, r in days.items():
        try:
            top, bottom = r["chart"]
            r["hourly"], r["slots"] = measure_bars(r["file"], top, bottom)
            r["bar_sum"] = sum(r["hourly"].values())
        except Exception as e:
            r["hourly"], r["bar_sum"], r["bar_err"] = None, None, str(e)
    retry = [r for r in days.values() if r["total"] is None or (r["bar_sum"] is not None and abs(r["bar_sum"] - r["total"]) > tol(r["total"]))]
    if retry:
        with tempfile.TemporaryDirectory() as td:
            crops = {crop_total(r["file"], r["hdr_y"], td): r for r in retry}
            res = ocr(list(crops))
            for cpath, r in crops.items():
                vals = [dur(l["text"]) for l in res.get(str(cpath), []) if dur(l["text"]) is not None]
                if vals:
                    r["total"] = vals[0]

    # report
    print(f"\n{'date':<12}{'day':<5}{'total':>7}{'bars':>8}  top categories")
    ok_days = []
    for d in sorted(days):
        r = days[d]
        tot, bs = r["total"], r["bar_sum"]
        status = ""
        if tot is None:
            status = f"{RED}✗ total unreadable — check {r['file'].name}{RESET}"
        elif bs is None:
            status = f"{YELLOW}! bars unreadable ({r.get('bar_err')}) — total kept, hourly skipped{RESET}"
        elif abs(bs - tot) > tol(tot):
            status = f"{YELLOW}! bars sum {bs:.0f} ≠ total {tot} — hourly skipped, check {r['file'].name}{RESET}"
            r["hourly"] = None
        elif abs(bs - tot) > 5:
            status = f"{DIM}(bars {bs - tot:+.0f} min vs total — within 3%, kept){RESET}"
        if r.get("slots") in (23, 25):
            status += f" {DIM}({r['slots']}-hour DST day){RESET}"
        if tot is not None:
            ok_days.append(d)
        cats = ", ".join(f"{n} {m}m" for n, m in r["cats"])
        col = GREEN if (tot or 0) < 120 else YELLOW if (tot or 0) <= 240 else RED
        print(f"{d.isoformat():<12}{d.strftime('%a'):<5}{col}{(tot if tot is not None else '?'):>7}{RESET}"
              f"{(f'{bs:.0f}' if bs is not None else '-'):>8}  {cats} {status}")

    if weeks:
        print(f"\n{BOLD}Week checksums{RESET} (sum of 7 days vs Week view total)")
        for start in sorted(weeks):
            w = weeks[start]
            ds = [start + timedelta(days=i) for i in range(7)]
            have = [days[x]["total"] for x in ds if x in days and days[x]["total"] is not None]
            if len(have) < 7 or w["total"] is None:
                print(f"  {start} week: {DIM}incomplete ({len(have)}/7 days) — not checked{RESET}")
                continue
            diff = sum(have) - w["total"]
            mark = f"{GREEN}✓{RESET}" if abs(diff) <= 10 else f"{RED}✗{RESET}"
            print(f"  {start} week: days {sum(have)} vs week {w['total']}  (diff {diff:+d}) {mark}")
    for name, why in skipped:
        print(f"  {DIM}skipped {name}: {why}{RESET}")

    # write (append-only, new dates only)
    have_st, have_cat, have_hr = existing_dates(ST_CSV), existing_dates(CAT_CSV), existing_dates(HOURLY_CSV)
    header = st_header()
    st_rows, cat_rows, hr_rows = [], [], []
    for d in ok_days:
        r, ds = days[d], d.isoformat()
        if ds not in have_st:
            row = {k: "" for k in header}
            row.update(date=ds, week_start=(d - timedelta(days=d.weekday())).isoformat(),
                       total_mins=r["total"], notes="screenshot import")
            for name, mins in r["cats"]:
                if name in ST_CAT_COLS and ST_CAT_COLS[name] in row:
                    row[ST_CAT_COLS[name]] = mins
            st_rows.append(row)
        if ds not in have_cat:
            cat_rows += [{"date": ds, "rank": i, "category": n, "mins": m} for i, (n, m) in enumerate(r["cats"], 1)]
        if r["hourly"] and ds not in have_hr:
            hr_rows += [{"date": ds, "hour": h, "metric": "screen_mins", "value": round(v, 1), "estimated": "Y"}
                        for h, v in sorted(r["hourly"].items())]

    new_days = len(st_rows)
    print(f"\nNew days: {new_days}  (already in screentime.csv: {len(ok_days) - new_days})")
    if args.dry_run:
        print(f"{DIM}--dry-run: nothing written.{RESET}")
        return
    append(ST_CSV, header, st_rows)
    append(CAT_CSV, CAT_HEADER, cat_rows)
    append(HOURLY_CSV, HOURLY_HEADER, hr_rows)
    print(f"{GREEN}✓ Wrote {len(st_rows)} days → screentime.csv, {len(cat_rows)} rows → iphone_categories.csv, "
          f"{len(hr_rows)} rows → iphone_hourly.csv{RESET}")


if __name__ == "__main__":
    main()
