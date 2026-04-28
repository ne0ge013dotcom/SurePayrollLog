#!/usr/bin/env python3
"""
Backfill weekly reports from a start date to today.

Iterates one week at a time (Mon-Sun by default), fetching events ONCE
in bulk and reusing the cache to render each weekly report.

Usage:
    python backfill.py --from 2026-01-01
    python backfill.py --from 2026-01-01 --to 2026-04-28
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta


def week_starts_between(start, end):
    """
    Return list of (week_start, week_end) tuples covering start..end.
    Each week is Monday-Sunday. The first week starts on or after `start`.
    """
    weeks = []
    # Snap start forward to Monday if not already
    cursor = start
    days_to_monday = (cursor.weekday()) % 7  # 0=Mon
    # If start is mid-week, the first "week" runs from start to the following Sunday,
    # so users get a partial-week report rather than skipping early days.
    if cursor.weekday() != 0:
        # First chunk: start to the next Sunday
        first_sunday = cursor + timedelta(days=(6 - cursor.weekday()))
        if first_sunday > end:
            first_sunday = end
        weeks.append((cursor, first_sunday))
        cursor = first_sunday + timedelta(days=1)

    while cursor <= end:
        week_end = cursor + timedelta(days=6)
        if week_end > end:
            week_end = end
        weeks.append((cursor, week_end))
        cursor = week_end + timedelta(days=1)

    return weeks


def main():
    parser = argparse.ArgumentParser(description='Backfill weekly Webflow activity reports.')
    parser.add_argument('--from', dest='start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to', dest='end', help='End date (default: today)')
    parser.add_argument('--reports-dir', default='reports', help='Output directory for reports')
    parser.add_argument('--cache-events', default='.cache/events.json', help='Where to cache fetched events')
    parser.add_argument('--site-id', default=os.environ.get('WEBFLOW_SITE_ID', '65a823bc36fc91ffafdc2c3e'))
    parser.add_argument('--skip-fetch', action='store_true', help='Skip API fetch, use existing cache')
    parser.add_argument('--skip-existing', action='store_true', help='Skip weeks where the report file already exists')
    args = parser.parse_args()

    start_dt = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    if args.end:
        end_dt = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    else:
        end_dt = datetime.now(timezone.utc)
    # Normalize end to end of day
    end_dt = end_dt.replace(hour=23, minute=59, second=59)

    print(f"Backfill window: {start_dt.date()} → {end_dt.date()}")

    weeks = week_starts_between(start_dt, end_dt)
    print(f"Will generate {len(weeks)} weekly reports.\n")

    # Fetch all events ONCE for the whole window, then render each week from the cache.
    cache_path = Path(args.cache_events)
    script_dir = Path(__file__).parent
    generate_script = script_dir / 'generate_report.py'

    if not args.skip_fetch:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Use generate_report.py with a wide window just to fetch+cache,
        # but since it would also render, do a direct API call here instead.
        # Simpler: import the fetch function.
        sys.path.insert(0, str(script_dir))
        from generate_report import fetch_activity_logs

        print(f"Fetching events from API back to {start_dt.date()}...")
        events = fetch_activity_logs(args.site_id, start_dt)
        print(f"  total fetched: {len(events)} events\n")

        cache_path.write_text(json.dumps(events))
        print(f"  cached → {cache_path}\n")

    # Now render each week using the cache
    Path(args.reports_dir).mkdir(parents=True, exist_ok=True)
    succeeded = 0
    skipped = 0
    failed = []

    for i, (ws, we) in enumerate(weeks, 1):
        ws_str = ws.strftime('%Y-%m-%d')
        we_str = we.strftime('%Y-%m-%d')
        week_iso = ws.strftime('%Y-W%V')
        expected_file = Path(args.reports_dir) / f"{week_iso}_{ws_str}_{we_str}.html"

        if args.skip_existing and expected_file.exists():
            print(f"[{i}/{len(weeks)}] {ws_str} → {we_str} : SKIP (exists)")
            skipped += 1
            continue

        print(f"[{i}/{len(weeks)}] {ws_str} → {we_str}")
        cmd = [
            sys.executable, str(generate_script),
            '--start', ws_str, '--end', we_str,
            '--output', args.reports_dir,
            '--load-events', str(cache_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ✗ FAILED: {result.stderr}")
            failed.append((ws_str, we_str, result.stderr))
        else:
            # Print the success summary line from the child output
            for line in result.stdout.splitlines():
                if 'events' in line.lower() or 'report generated' in line.lower():
                    print(f"  {line.strip()}")
            succeeded += 1

    print(f"\n{'='*60}")
    print(f"Backfill complete: {succeeded} succeeded, {skipped} skipped, {len(failed)} failed")
    if failed:
        print("\nFailures:")
        for ws, we, err in failed:
            print(f"  {ws} → {we}: {err[:200]}")

    # Regenerate index
    print("\nRegenerating index.html...")
    index_script = script_dir / 'generate_index.py'
    result = subprocess.run([
        sys.executable, str(index_script),
        '--reports-dir', args.reports_dir,
        '--output', 'index.html',
    ], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"Index generation failed: {result.stderr}")
        return 1

    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
