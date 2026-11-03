#!/usr/bin/env python3
"""
sync_all.py — the whole routine in one command. Run every 3 weeks:

    cd ~/"Historical Screen Time Tracker" && python3 scripts/sync_all.py

1. iPhone  — previews new screenshots in `mobile time tracker/`, asks before writing,
             then moves them to `mobile time tracker/imported/<today>/`.
2. Mac     — appends finished days from knowledgeC.db (Terminal needs Full Disk Access).
3. Chrome  — asks you to quit Chrome if it's open, then appends finished days.
4. Opens the dashboard; Ctrl+C stops the server.

Everything is append-only: rows already in data/ are never changed.
Why 3 weeks: iOS shows only the current week + the 3 before it, and macOS keeps ~30 days.
"""

import argparse
import shutil
import socket
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SHOTS = ROOT / "mobile time tracker"
URL = "http://localhost:8000/dashboard/"
IMG = (".png", ".jpg", ".jpeg")
BOLD, DIM, GREEN, YELLOW, RED, RESET = "\033[1m", "\033[2m", "\033[92m", "\033[93m", "\033[91m", "\033[0m"


def step(n, title):
    print(f"\n{BOLD}── {n}. {title} {'─' * (44 - len(title))}{RESET}")


def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=ROOT).returncode == 0


def ask(prompt):
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return ""


def iphone():
    step(1, "iPhone screenshots")
    shots = sorted(p for p in SHOTS.glob("*") if p.suffix.lower() in IMG)
    if not shots:
        print(f"{YELLOW}No new screenshots in '{SHOTS.name}/' — iPhone skipped.{RESET}")
        return
    if not run("import_iphone.py", "--dry-run"):
        print(f"{RED}Preview failed — nothing written, screenshots left in place.{RESET}")
        return
    if ask(f"\n{BOLD}Write these days? [y/N] {RESET}") != "y":
        print(f"{DIM}Nothing written, screenshots left in place.{RESET}")
        return
    if not run("import_iphone.py"):
        print(f"{RED}Import failed — screenshots left in place.{RESET}")
        return
    dest = SHOTS / "imported" / date.today().isoformat()
    dest.mkdir(parents=True, exist_ok=True)
    for p in shots:
        target = dest / p.name
        if target.exists():
            target = dest / f"{p.stem}_{int(time.time())}{p.suffix}"
        shutil.move(str(p), str(target))
    print(f"{DIM}Moved {len(shots)} screenshots → {dest.relative_to(ROOT)}/{RESET}")


def mac():
    step(2, "Mac apps")
    if not run("sync_mac.py"):
        print(f"{RED}Mac sync failed. If it mentions authorization: System Settings → Privacy & Security"
              f" → Full Disk Access → turn on Terminal, reopen Terminal, run this again.{RESET}")


def chrome():
    step(3, "Chrome history")
    if subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True).returncode == 0:
        ask(f"{YELLOW}Chrome is open — quit it (Cmd+Q) for the most accurate data, then press Enter.{RESET} ")
    run("sync_chrome.py")


def dashboard():
    step(4, "Dashboard")
    with socket.socket() as s:
        busy = s.connect_ex(("127.0.0.1", 8000)) == 0
    if busy:
        print(f"{DIM}Port 8000 is already serving — opening it.{RESET}")
        subprocess.run(["open", URL])
        return
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8000", "--bind", "127.0.0.1"],
                           cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.7)
    subprocess.run(["open", URL])
    print(f"{GREEN}{URL}{RESET}  {DIM}(Ctrl+C here to stop the server){RESET}")
    try:
        srv.wait()
    except KeyboardInterrupt:
        srv.terminate()
        srv.wait()
        print("\nServer stopped.")


def main():
    ap = argparse.ArgumentParser(description="iPhone import + Mac sync + Chrome sync + dashboard")
    ap.add_argument("--no-serve", action="store_true", help="sync only, don't start the dashboard")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # keep our headings in order with the child scripts' output
    iphone()
    mac()
    chrome()
    nxt = date.today() + timedelta(weeks=3)
    print(f"\n{BOLD}Next run: {nxt:%a %b} {nxt.day}{RESET}  {DIM}(every 3 weeks){RESET}")
    if not args.no_serve:
        dashboard()


if __name__ == "__main__":
    main()
