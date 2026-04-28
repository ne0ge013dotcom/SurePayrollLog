#!/usr/bin/env python3
"""
Generate a SurePayroll Webflow activity report for a given date range.

Usage:
    python generate_report.py --start 2026-04-21 --end 2026-04-27
    python generate_report.py --start 2026-04-21 --end 2026-04-27 --output reports/
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict
from pathlib import Path


# ============================================================================
# CONFIGURATION
# ============================================================================
SITE_ID = os.environ.get('WEBFLOW_SITE_ID', '65a823bc36fc91ffafdc2c3e')  # SurePayroll
SITE_NAME = "SurePayroll"
WEBFLOW_TOKEN = os.environ.get('WEBFLOW_API_TOKEN')  # required from env
API_BASE = 'https://api.webflow.com/v2'
PAGE_LIMIT = 100  # max per Webflow API
MAX_PAGES = 1000  # safety cap for full backfills


# ============================================================================
# WEBFLOW API
# ============================================================================
def fetch_activity_logs(site_id, start_dt, max_pages=MAX_PAGES):
    """
    Fetch activity logs going back until we pass start_dt.
    Returns list of events (newest first). Stops paginating when oldest event
    on a page is before start_dt.
    """
    if not WEBFLOW_TOKEN:
        raise RuntimeError(
            "WEBFLOW_API_TOKEN environment variable not set.\n"
            "Get a token from https://webflow.com/dashboard/account/integrations\n"
            "and set: export WEBFLOW_API_TOKEN=your_token_here"
        )

    all_events = []
    offset = 0

    for page in range(max_pages):
        url = f"{API_BASE}/sites/{site_id}/activity_logs?limit={PAGE_LIMIT}&offset={offset}"
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {WEBFLOW_TOKEN}',
            'Accept': 'application/json',
        })

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            raise RuntimeError(f"Webflow API error {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error fetching {url}: {e}") from e

        items = data.get('items', [])
        if not items:
            break

        all_events.extend(items)

        # Check if we've reached events older than start_dt
        oldest = parse_dt(items[-1]['createdOn'])
        print(f"  page {page + 1}: fetched {len(items)} events, oldest = {oldest.isoformat()}")
        if oldest < start_dt:
            break

        offset += PAGE_LIMIT

    return all_events


# ============================================================================
# DATA PROCESSING
# ============================================================================
def parse_dt(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def filter_to_range(events, start_dt, end_dt):
    return [e for e in events if start_dt <= parse_dt(e['createdOn']) <= end_dt]


def build_summary(events, start_dt, end_dt):
    """Build the data summary that the HTML template consumes."""
    # Event type counts
    event_counts = Counter(e['event'] for e in events)

    # User counts and breakdown
    user_counts = Counter()
    user_event_breakdown = defaultdict(Counter)
    for e in events:
        if 'user' in e:
            name = e['user'].get('displayName', 'Unknown')
            user_counts[name] += 1
            user_event_breakdown[name][e['event']] += 1

    # Publishes
    publishes = [e for e in events if e['event'] == 'site_published']
    publish_users = Counter(e['user']['displayName'] for e in publishes if 'user' in e)
    domain_counts = Counter()
    for e in publishes:
        domain = e.get('payload', {}).get('domain', 'unknown')
        domain_counts[domain] += 1

    # CMS articles
    cms_events = [e for e in events if e['event'] == 'cms_item']
    cms_articles = Counter()
    for e in cms_events:
        name = e.get('resourceName', 'unknown')
        op = e.get('resourceOperation', '?')
        cms_articles[(name, op)] += 1

    # Pages modified (DOM)
    page_dom = [e for e in events if e['event'] == 'page_dom_modified']
    page_counts = Counter(e.get('resourceName', 'unknown') for e in page_dom)

    # Daily activity
    daily = defaultdict(int)
    daily_users = defaultdict(set)
    for e in events:
        day = e['createdOn'][:10]
        daily[day] += 1
        if 'user' in e:
            daily_users[day].add(e['user']['displayName'])

    # Build full date list for the period
    date_list = []
    cursor = start_dt
    while cursor <= end_dt:
        date_list.append(cursor.strftime('%Y-%m-%d'))
        cursor += timedelta(days=1)

    return {
        'period': {'start': start_dt.strftime('%Y-%m-%d'), 'end': end_dt.strftime('%Y-%m-%d')},
        'total_events': len(events),
        'event_counts': dict(event_counts),
        'user_counts': dict(user_counts),
        'user_event_breakdown': {u: dict(c) for u, c in user_event_breakdown.items()},
        'publish_users': dict(publish_users),
        'domain_counts': dict(domain_counts),
        'cms_articles': {f"{n}|{o}": c for (n, o), c in cms_articles.items()},
        'page_counts': dict(page_counts),
        'daily': dict(daily),
        'daily_users': {d: list(u) for d, u in daily_users.items()},
        'total_publishes': len(publishes),
        'total_cms': len(cms_events),
        'date_list': date_list,
    }


def build_significant(events):
    """Extract notable events for the timeline."""
    significant = []
    for e in events:
        ev = e['event']
        op = e.get('resourceOperation', '')
        name = e.get('resourceName', '')
        user = e.get('user', {}).get('displayName', 'System')

        if ev == 'site_published':
            domain = e.get('payload', {}).get('domain', '')
            if 'staging' in domain or 'webflow.io' in domain:
                continue
            significant.append({
                'date': e['createdOn'][:10], 'time': e['createdOn'][11:16],
                'type': 'site_publish', 'icon': 'globe',
                'title': f'Production publish to {domain}', 'user': user,
            })
        elif ev == 'library_installed':
            significant.append({
                'date': e['createdOn'][:10], 'time': e['createdOn'][11:16],
                'type': 'library', 'icon': 'package',
                'title': 'Library installed', 'user': user,
            })
        elif ev in ('branch_created', 'branch_merged'):
            icon = 'git-branch' if ev == 'branch_created' else 'git-merge'
            verb = 'created' if ev == 'branch_created' else 'merged'
            significant.append({
                'date': e['createdOn'][:10], 'time': e['createdOn'][11:16],
                'type': 'branch', 'icon': icon,
                'title': f'Branch {verb}: {name}', 'user': user,
            })
        elif ev == 'page_created':
            significant.append({
                'date': e['createdOn'][:10], 'time': e['createdOn'][11:16],
                'type': 'page_create', 'icon': 'file-plus',
                'title': 'Page created', 'user': user,
            })
        elif ev == 'cms_item' and op == 'PUBLISHED':
            title_text = name[:60] + ('...' if len(name) > 60 else '')
            significant.append({
                'date': e['createdOn'][:10], 'time': e['createdOn'][11:16],
                'type': 'article_published', 'icon': 'book-open',
                'title': f'Article published: {title_text}', 'user': user,
            })
    return significant


def build_insights(summary, num_events):
    """Generate three top-line insight cards."""
    insights = []

    # Insight 1: dominant event type
    if summary['event_counts']:
        top_event, top_count = max(summary['event_counts'].items(), key=lambda x: x[1])
        if num_events > 0:
            pct = (top_count / num_events) * 100
            insights.append({
                'num': f'{pct:.1f}%',
                'text': f'<strong>{top_event.replace("_", " ").title()}</strong> dominated activity — {top_count} of {num_events} events were of this type.',
            })

    # Insight 2: top contributor
    if summary['user_counts']:
        top_user, top_user_count = max(summary['user_counts'].items(), key=lambda x: x[1])
        insights.append({
            'num': str(top_user_count),
            'text': f'<strong>{top_user}</strong> led the period with {top_user_count} events.',
        })

    # Insight 3: peak day
    if summary['daily']:
        peak_day, peak_count = max(summary['daily'].items(), key=lambda x: x[1])
        peak_dt = datetime.strptime(peak_day, '%Y-%m-%d')
        insights.append({
            'num': str(peak_count),
            'text': f'<strong>{peak_dt.strftime("%b %-d").upper()} was the busiest day</strong>, with {peak_count} events.',
        })

    # Pad with placeholders if fewer than 3
    while len(insights) < 3:
        insights.append({'num': '—', 'text': 'Quiet period.'})

    return insights


# ============================================================================
# SEARCH INDEX
# ============================================================================
def build_search_entries(events, summary, significant, report_url, period_str):
    """
    Build a flat list of searchable entries for this report.
    Each entry has enough text to match against and enough context to display.
    Categories: page, article, user, publish, event-type, milestone.
    """
    entries = []

    # Pages (DOM-modified)
    for page_name, count in summary.get('page_counts', {}).items():
        entries.append({
            'cat': 'page',
            'title': page_name,
            'detail': f'{count} DOM edit{"s" if count != 1 else ""}',
            'haystack': f'page {page_name}',
            'report': report_url,
            'period': period_str,
        })

    # Articles (CMS items, deduped by name)
    article_totals = {}
    for key, count in summary.get('cms_articles', {}).items():
        name, op = key.split('|')
        if name not in article_totals:
            article_totals[name] = {'modified': 0, 'published': 0, 'created': 0}
        if op == 'MODIFIED':
            article_totals[name]['modified'] += count
        elif op == 'PUBLISHED':
            article_totals[name]['published'] += count
        elif op == 'CREATED':
            article_totals[name]['created'] += count

    for name, ops in article_totals.items():
        bits = []
        if ops['published']:
            bits.append(f'{ops["published"]} publish{"es" if ops["published"] != 1 else ""}')
        if ops['modified']:
            bits.append(f'{ops["modified"]} edit{"s" if ops["modified"] != 1 else ""}')
        if ops['created']:
            bits.append('created')
        entries.append({
            'cat': 'article',
            'title': name,
            'detail': ', '.join(bits) if bits else 'CMS activity',
            'haystack': f'article {name}',
            'report': report_url,
            'period': period_str,
        })

    # Users
    for user_name, count in summary.get('user_counts', {}).items():
        entries.append({
            'cat': 'user',
            'title': user_name,
            'detail': f'{count} event{"s" if count != 1 else ""}',
            'haystack': f'user {user_name}',
            'report': report_url,
            'period': period_str,
        })

    # Domains published to (production only)
    for domain, count in summary.get('domain_counts', {}).items():
        is_staging = 'staging' in domain or 'webflow.io' in domain
        entries.append({
            'cat': 'publish',
            'title': domain,
            'detail': f'{count} publish{"es" if count != 1 else ""}{" (staging)" if is_staging else ""}',
            'haystack': f'publish deploy domain {domain}',
            'report': report_url,
            'period': period_str,
        })

    # Significant events / milestones (each becomes a searchable item)
    for s in significant:
        entries.append({
            'cat': 'milestone',
            'title': s['title'],
            'detail': f'{s["date"]} · {s["user"]}',
            'haystack': f'{s["type"]} {s["title"]} {s["user"]} {s["date"]}',
            'report': report_url,
            'period': period_str,
        })

    return entries


# ============================================================================
# RENDERING
# ============================================================================
def format_period(start_dt, end_dt):
    """Human-readable period string."""
    if start_dt.year == end_dt.year:
        return f"{start_dt.strftime('%b %-d')} – {end_dt.strftime('%b %-d, %Y')}"
    return f"{start_dt.strftime('%b %-d, %Y')} – {end_dt.strftime('%b %-d, %Y')}"


def render_report(start_dt, end_dt, events, output_path, template_path):
    """Render the HTML report and write to output_path."""
    filtered = filter_to_range(events, start_dt, end_dt)
    summary = build_summary(filtered, start_dt, end_dt)
    significant = build_significant(filtered)
    insights = build_insights(summary, len(filtered))

    # Headline copy
    days_count = (end_dt - start_dt).days + 1
    if days_count <= 8:
        headline = f"The Last <em>Week</em><br>of Activity."
    elif days_count <= 32:
        headline = f"The Last <em>{days_count}</em><br>Days, in Detail."
    else:
        headline = f"<em>{days_count} Days</em><br>of the Site."

    period_str = format_period(start_dt, end_dt)
    deck_text = (
        f"A complete account of every change made to the {SITE_NAME} Webflow site "
        f"between <strong>{start_dt.strftime('%B %-d')}</strong> and "
        f"<strong>{end_dt.strftime('%B %-d, %Y')}</strong>. "
        f"<strong>{len(filtered)} events</strong>, "
        f"<strong>{len(summary['user_counts'])} contributor{'s' if len(summary['user_counts']) != 1 else ''}</strong>, "
        f"<strong>{summary['total_publishes']} site publish{'es' if summary['total_publishes'] != 1 else ''}</strong>."
    )

    contributor_detail = "no attributed users" if not summary['user_counts'] else \
        f"from designers and developers to content authors"
    publish_detail = "no production deploys this period" if summary['total_publishes'] == 0 else \
        f"across <strong>{len(summary['domain_counts'])} domain{'s' if len(summary['domain_counts']) != 1 else ''}</strong>"

    # Count unique articles touched
    unique_articles = set()
    for key in summary['cms_articles']:
        name = key.split('|')[0]
        unique_articles.add(name)
    article_publishes = sum(c for k, c in summary['cms_articles'].items() if k.endswith('|PUBLISHED'))

    # Build the data payload for the JS
    payload = {
        'summary': summary,
        'significant': significant,
        'insights': insights,
        'date_list': summary['date_list'],
    }

    # Template substitutions
    template = Path(template_path).read_text()
    replacements = {
        '{{TITLE}}': f"{SITE_NAME} · Activity · {period_str}",
        '{{SITE_NAME}}': SITE_NAME,
        '{{ISSUE_TAG}}': f"WEEKLY · {start_dt.strftime('%Y-W%V').upper()}",
        '{{HEADLINE}}': headline,
        '{{DECK}}': deck_text,
        '{{TOTAL_EVENTS}}': f"{len(filtered):,}",
        '{{NUM_EVENT_TYPES}}': str(len(summary['event_counts'])),
        '{{ACTIVE_DAYS}}': str(sum(1 for v in summary['daily'].values() if v > 0)),
        '{{NUM_CONTRIBUTORS}}': str(len(summary['user_counts'])),
        '{{CONTRIBUTOR_DETAIL}}': contributor_detail,
        '{{NUM_SITE_PUBLISHES}}': str(summary['total_publishes']),
        '{{PUBLISH_DETAIL}}': publish_detail,
        '{{NUM_ARTICLES}}': str(len(unique_articles)),
        '{{NUM_CMS_EDITS}}': str(summary['total_cms']),
        '{{NUM_ARTICLE_PUBLISHES}}': str(article_publishes),
        '{{DATE_RANGE_KICKER}}': f"{start_dt.strftime('%b %-d').upper()} → {end_dt.strftime('%b %-d').upper()} / {days_count} DAYS",
        '{{ATTRIBUTED_EVENTS}}': str(sum(summary['user_counts'].values())),
        '{{NUM_DOMAINS}}': str(len(summary['domain_counts'])),
        '{{NUM_HIGHLIGHTS}}': str(len(significant)),
        '{{REPORT_PERIOD}}': period_str,
        '{{GENERATED_DATE}}': datetime.now(timezone.utc).strftime('%b %-d, %Y').upper(),
        '{{DATA_JSON}}': json.dumps(payload),
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)

    Path(output_path).write_text(template)

    # Build search entries — relative URL the index page can link to
    output_path_obj = Path(output_path)
    report_url = f"{output_path_obj.parent.name}/{output_path_obj.name}"
    search_entries = build_search_entries(
        filtered, summary, significant, report_url, period_str
    )

    return {
        'path': str(output_path),
        'period': period_str,
        'start': start_dt.strftime('%Y-%m-%d'),
        'end': end_dt.strftime('%Y-%m-%d'),
        'total_events': len(filtered),
        'total_publishes': summary['total_publishes'],
        'contributors': len(summary['user_counts']),
        'cms_edits': summary['total_cms'],
        'search_entries': search_entries,
    }


# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description='Generate a Webflow activity report.')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', default='reports', help='Output directory (default: reports)')
    parser.add_argument('--site-id', default=SITE_ID, help='Webflow site ID')
    parser.add_argument('--cache-events', help='Optional path to cache fetched events JSON')
    parser.add_argument('--load-events', help='Optional path to load events from instead of fetching')
    parser.add_argument('--meta-out', help='Optional path to write report metadata JSON')
    args = parser.parse_args()

    start_dt = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(args.end).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    if args.load_events:
        print(f"Loading events from {args.load_events}")
        events = json.loads(Path(args.load_events).read_text())
    else:
        print(f"Fetching activity logs (will paginate until before {start_dt.isoformat()})...")
        events = fetch_activity_logs(args.site_id, start_dt)
        print(f"  fetched {len(events)} events total")
        if args.cache_events:
            Path(args.cache_events).parent.mkdir(parents=True, exist_ok=True)
            Path(args.cache_events).write_text(json.dumps(events))
            print(f"  cached to {args.cache_events}")

    # Output filename: reports/2026-W17_2026-04-21_2026-04-27.html
    week_iso = start_dt.strftime('%Y-W%V')
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{week_iso}_{args.start}_{args.end}.html"
    output_path = output_dir / filename

    # Path to template
    script_dir = Path(__file__).parent
    template_path = script_dir / 'report_template.html'

    print(f"Rendering report → {output_path}")
    meta = render_report(start_dt, end_dt, events, output_path, template_path)

    # Write the search-entries sidecar next to the report
    sidecar_path = output_path.with_suffix('').with_name(output_path.stem + '.search.json')
    sidecar_path.write_text(json.dumps(meta['search_entries']))

    print(f"\n✓ Report generated: {meta['path']}")
    print(f"  Period:        {meta['period']}")
    print(f"  Total events:  {meta['total_events']}")
    print(f"  Contributors:  {meta['contributors']}")
    print(f"  Site publishes: {meta['total_publishes']}")
    print(f"  Search index:  {len(meta['search_entries'])} entries")

    if args.meta_out:
        Path(args.meta_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.meta_out).write_text(json.dumps(meta, indent=2))
        print(f"  Metadata: {args.meta_out}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
