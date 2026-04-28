#!/usr/bin/env python3
"""
weekly_run.py — runs every Monday morning. Generates a report for the
previous Monday-Sunday week and rebuilds the index.

This is the script the GitHub Action calls.
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta


def main():
    today = datetime.now(timezone.utc).date()

    # Find last Monday and last Sunday
    # If today is Monday, "last week" = previous Monday → previous Sunday
    days_since_monday = today.weekday()  # 0 if today is Monday
    if days_since_monday == 0:
        last_monday = today - timedelta(days=7)
    else:
        last_monday = today - timedelta(days=days_since_monday + 7)
    last_sunday = last_monday + timedelta(days=6)

    print(f"Today: {today} ({today.strftime('%A')})")
    print(f"Generating report for: {last_monday} → {last_sunday}\n")

    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Generate the weekly report
    cmd = [
        sys.executable, str(script_dir / 'generate_report.py'),
        '--start', last_monday.isoformat(),
        '--end', last_sunday.isoformat(),
        '--output', str(repo_root / 'reports'),
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("Report generation FAILED")
        return 1

    # Regenerate the index
    cmd = [
        sys.executable, str(script_dir / 'generate_index.py'),
        '--reports-dir', str(repo_root / 'reports'),
        '--output', str(repo_root / 'index.html'),
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("Index generation FAILED")
        return 1

    print("\n✓ Weekly run complete")
    return 0


if __name__ == '__main__':
    sys.exit(main())
