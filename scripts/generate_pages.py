#!/usr/bin/env python3
"""
Generate per-page history pages from the .pages.json sidecar files
emitted by each weekly report.

Outputs:
    pages/index.html         — directory of every page and article
    pages/{slug}.html        — full history for one entity

Usage:
    python generate_pages.py --reports-dir reports --output-dir pages
"""

import os
import sys
import re
import json
import argparse
import hashlib
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone


SITE_NAME = "SurePayroll"


def slugify(name):
    """Stable URL-safe slug from an entity name."""
    s = re.sub(r'[^\w\s-]', '', name.lower())
    s = re.sub(r'[\s_-]+', '-', s).strip('-')
    if not s:
        # fallback: hash so we always get something
        s = 'item-' + hashlib.md5(name.encode()).hexdigest()[:8]
    # cap length and add hash suffix to avoid collisions
    if len(s) > 60:
        s = s[:60] + '-' + hashlib.md5(name.encode()).hexdigest()[:6]
    return s


def load_all_events(reports_dir):
    """Walk all .pages.json sidecars and return a flat list of events."""
    all_events = []
    for f in Path(reports_dir).iterdir():
        if not f.name.endswith('.pages.json'):
            continue
        try:
            data = json.loads(f.read_text())
            all_events.extend(data)
        except Exception as e:
            print(f"  warning: could not load {f.name}: {e}")
    return all_events


# ---------- COMMON STYLES & CHROME ----------
COMMON_STYLES = """
  :root {
    --bg: #0e0e10; --panel: #16161a; --panel-2: #1c1c22;
    --line: #2a2a32; --line-2: #3a3a44;
    --ink: #f5f0e8; --ink-2: #b8b4ac; --ink-3: #76737a;
    --accent: #ffd866; --accent-2: #f97e72; --accent-3: #7ee0b8;
    --accent-4: #8fb8ff; --accent-5: #c89cff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    background: var(--bg); color: var(--ink);
    font-family: 'Inter Tight', -apple-system, sans-serif;
    line-height: 1.5; -webkit-font-smoothing: antialiased;
  }
  body {
    background:
      radial-gradient(ellipse 80% 50% at 50% -20%, rgba(255,216,102,0.08), transparent 70%),
      radial-gradient(ellipse 60% 40% at 100% 50%, rgba(126,224,184,0.04), transparent 70%),
      var(--bg);
    background-attachment: fixed; min-height: 100vh;
  }
  .grain {
    position: fixed; inset: 0; pointer-events: none; opacity: 0.03; z-index: 100;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' /%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.6'/%3E%3C/svg%3E");
  }
  .container { max-width: 1280px; margin: 0 auto; padding: 48px 32px; }
  .back-link {
    display: inline-flex; align-items: center; gap: 8px;
    color: var(--ink-3); text-decoration: none;
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    letter-spacing: 0.15em; text-transform: uppercase;
    margin-bottom: 32px; transition: color 0.15s;
  }
  .back-link:hover { color: var(--accent); }

  .masthead { border-bottom: 1px solid var(--line); padding-bottom: 40px; margin-bottom: 56px; position: relative; }
  .masthead::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, var(--accent), transparent); }
  .meta-row { display: flex; justify-content: space-between; align-items: center; font-family: 'JetBrains Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.15em; color: var(--ink-3); margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
  .meta-row .left { color: var(--accent); }
  h1 { font-family: 'Fraunces', serif; font-weight: 400; line-height: 0.95; letter-spacing: -0.02em; margin-bottom: 24px; font-variation-settings: 'opsz' 144; }
  h1.big { font-size: clamp(48px, 7vw, 96px); line-height: 0.92; }
  h1.med { font-size: clamp(32px, 4vw, 56px); }
  h1 em { font-style: italic; font-weight: 300; color: var(--accent); }
  .deck { font-family: 'Fraunces', serif; font-size: 20px; line-height: 1.4; color: var(--ink-2); max-width: 760px; }
  .deck strong { color: var(--ink); font-weight: 500; }

  .section-head { display: flex; align-items: baseline; gap: 16px; margin-bottom: 32px; padding-bottom: 16px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
  .section-num { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--accent); letter-spacing: 0.2em; }
  .section-head h2 { font-family: 'Fraunces', serif; font-weight: 500; font-size: 32px; letter-spacing: -0.02em; line-height: 1; }
  .section-head .kicker { margin-left: auto; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--ink-3); letter-spacing: 0.1em; }

  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 28px; }
  .panel-title { font-family: 'JetBrains Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--ink-3); margin-bottom: 20px; }

  footer { margin-top: 80px; padding-top: 32px; border-top: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--ink-3); letter-spacing: 0.15em; text-transform: uppercase; flex-wrap: wrap; gap: 16px; }
  footer .mark { font-family: 'Fraunces', serif; font-style: italic; color: var(--ink-2); text-transform: none; letter-spacing: 0; font-size: 13px; }

  ::-webkit-scrollbar { height: 8px; width: 8px; }
  ::-webkit-scrollbar-track { background: var(--panel); }
  ::-webkit-scrollbar-thumb { background: var(--line-2); border-radius: 99px; }
"""


# ---------- INDEX (DIRECTORY OF PAGES & ARTICLES) ----------

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{site_name} · Pages & Articles · Activity History</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700;9..144,900&family=JetBrains+Mono:wght@400;500;700&family=Inter+Tight:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{common_styles}

  /* search/filter */
  .controls {{ display: grid; grid-template-columns: 1fr auto; gap: 14px; margin-bottom: 32px; align-items: center; }}
  .search-input-wrap {{ position: relative; }}
  .search-input {{
    width: 100%; background: var(--panel); border: 1px solid var(--line);
    border-radius: 3px; padding: 12px 16px 12px 44px;
    color: var(--ink); font-family: 'Fraunces', serif; font-size: 18px;
    transition: border-color 0.15s;
  }}
  .search-input:focus {{ outline: none; border-color: var(--accent); }}
  .search-icon {{ position: absolute; left: 14px; top: 50%; transform: translateY(-50%); width: 20px; height: 20px; color: var(--ink-3); pointer-events: none; }}
  .filter-pills {{ display: flex; gap: 6px; }}
  .filter-pill {{
    background: var(--panel-2); border: 1px solid var(--line);
    color: var(--ink-2); cursor: pointer;
    padding: 8px 16px; border-radius: 99px;
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.1em;
    transition: all 0.15s;
  }}
  .filter-pill:hover {{ border-color: var(--ink-3); color: var(--ink); }}
  .filter-pill.active {{ background: var(--accent); color: var(--bg); border-color: var(--accent); font-weight: 700; }}

  /* table */
  .entity-table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }}
  .entity-table th {{
    text-align: left; padding: 14px 18px;
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    letter-spacing: 0.15em; text-transform: uppercase;
    color: var(--ink-3); border-bottom: 1px solid var(--line);
    background: var(--panel-2);
    font-weight: 500;
  }}
  .entity-table th.sortable {{ cursor: pointer; user-select: none; }}
  .entity-table th.sortable:hover {{ color: var(--accent); }}
  .entity-table th.sorted::after {{ content: ' ▾'; color: var(--accent); }}
  .entity-table th.sorted.asc::after {{ content: ' ▴'; }}
  .entity-table td {{ padding: 14px 18px; border-bottom: 1px solid var(--line); vertical-align: middle; }}
  .entity-table tr:last-child td {{ border-bottom: none; }}
  .entity-table tr.entity-row {{ cursor: pointer; transition: background 0.12s; }}
  .entity-table tr.entity-row:hover {{ background: rgba(255,216,102,0.04); }}
  .entity-row a {{ color: inherit; text-decoration: none; }}

  .entity-name {{ font-family: 'Fraunces', serif; font-size: 16px; font-weight: 500; line-height: 1.3; }}
  .entity-name a {{ color: var(--ink); }}
  .entity-name a:hover {{ color: var(--accent); }}
  .entity-name mark {{ background: rgba(255,216,102,0.25); color: var(--accent); border-radius: 2px; padding: 0 2px; }}

  .type-pill {{
    display: inline-block; padding: 2px 8px; border-radius: 99px;
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    letter-spacing: 0.15em; text-transform: uppercase;
    border: 1px solid;
  }}
  .type-pill.page {{ background: rgba(143,184,255,0.1); color: var(--accent-4); border-color: rgba(143,184,255,0.25); }}
  .type-pill.article {{ background: rgba(126,224,184,0.1); color: var(--accent-3); border-color: rgba(126,224,184,0.25); }}

  .num-cell {{ font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--ink-2); text-align: right; }}
  .num-cell.accent {{ color: var(--accent); font-weight: 700; font-size: 16px; }}
  .date-cell {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--ink-3); }}

  .summary-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--line); border: 1px solid var(--line); margin-bottom: 40px; border-radius: 4px; overflow: hidden; }}
  .stat {{ background: var(--panel); padding: 24px 20px; }}
  .stat-label {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 10px; }}
  .stat-value {{ font-family: 'Fraunces', serif; font-weight: 500; font-size: 40px; line-height: 1; letter-spacing: -0.02em; color: var(--accent); }}
  .stat-value.green {{ color: var(--accent-3); }}
  .stat-value.coral {{ color: var(--accent-2); }}
  .stat-value.blue {{ color: var(--accent-4); }}

  .empty-results {{ padding: 60px 20px; text-align: center; color: var(--ink-3); font-family: 'Fraunces', serif; font-style: italic; font-size: 18px; }}

  @media (max-width: 900px) {{
    .summary-row {{ grid-template-columns: repeat(2, 1fr); }}
    .controls {{ grid-template-columns: 1fr; }}
    .filter-pills {{ flex-wrap: wrap; }}
  }}
</style>
</head>
<body>
<script>window.__ENTITIES__ = __ENTITIES_JSON_SENTINEL__;</script>
<div class="grain"></div>
<div class="container">

  <a href="../index.html" class="back-link">← BACK TO ALL REPORTS</a>

  <header class="masthead">
    <div class="meta-row">
      <div class="left">◆ ENTITY DIRECTORY</div>
      <div>{site_name} · WEBFLOW WORKSPACE</div>
      <div>{total_entities} ENTITIES TRACKED</div>
    </div>
    <h1 class="big">Pages &<br><em>Articles</em>.</h1>
    <p class="deck">Every page and article that has been touched in any of the {num_reports} reports. Click any name to see its full edit history — every modification, publish, and rename, mapped to the week it happened.</p>
  </header>

  <div class="summary-row">
    <div class="stat">
      <div class="stat-label">Pages</div>
      <div class="stat-value blue">{num_pages}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Articles</div>
      <div class="stat-value green">{num_articles}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Total Events</div>
      <div class="stat-value">{total_events:,}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Active Editors</div>
      <div class="stat-value coral">{num_editors}</div>
    </div>
  </div>

  <div class="controls">
    <div class="search-input-wrap">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input type="text" class="search-input" id="searchInput" placeholder="Filter pages and articles..." autocomplete="off" spellcheck="false">
    </div>
    <div class="filter-pills" id="filterPills">
      <button class="filter-pill active" data-type="all">All</button>
      <button class="filter-pill" data-type="page">Pages</button>
      <button class="filter-pill" data-type="article">Articles</button>
    </div>
  </div>

  <table class="entity-table" id="entityTable">
    <thead>
      <tr>
        <th class="sortable" data-sort="name">Name</th>
        <th style="width:90px">Type</th>
        <th class="sortable sorted" data-sort="events" style="width:90px;text-align:right">Events</th>
        <th class="sortable" data-sort="last" style="width:140px">Last activity</th>
        <th class="sortable" data-sort="first" style="width:140px">First activity</th>
        <th style="width:120px">Editors</th>
      </tr>
    </thead>
    <tbody id="entityRows"></tbody>
  </table>
  <div class="empty-results" id="emptyResults" style="display:none">No entities match your filters.</div>

  <footer>
    <div>WEBFLOW DATA API · ENTERPRISE ACTIVITY LOG</div>
    <div class="mark">— page directory —</div>
    <div>UPDATED · {generated_date}</div>
  </footer>
</div>

<script>
(function() {{
  const entities = window.__ENTITIES__ || [];
  const tbody = document.getElementById('entityRows');
  const emptyEl = document.getElementById('emptyResults');
  const input = document.getElementById('searchInput');
  const pills = document.getElementById('filterPills');
  const headers = document.querySelectorAll('#entityTable th.sortable');

  let activeType = 'all';
  let sortKey = 'events';
  let sortAsc = false;
  let query = '';

  function escape(s) {{
    return String(s).replace(/[&<>"']/g, c =>
      ({{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }})[c]);
  }}

  function highlight(text, q) {{
    if (!q) return escape(text);
    const escaped = escape(text);
    const words = q.trim().split(/\\s+/).filter(Boolean);
    if (!words.length) return escaped;
    const re = new RegExp('(' + words.map(w => w.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&')).join('|') + ')', 'gi');
    return escaped.replace(re, '<mark>$1</mark>');
  }}

  function fmtDate(iso) {{
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric', year: 'numeric' }});
  }}

  function render() {{
    let list = entities.slice();

    // Type filter
    if (activeType !== 'all') list = list.filter(e => e.type === activeType);

    // Query filter
    if (query.trim()) {{
      const words = query.toLowerCase().trim().split(/\\s+/).filter(Boolean);
      list = list.filter(e => {{
        const hay = (e.name + ' ' + e.editors.join(' ')).toLowerCase();
        return words.every(w => hay.indexOf(w) !== -1);
      }});
    }}

    // Sort
    list.sort((a, b) => {{
      let av, bv;
      if (sortKey === 'name') {{ av = a.name.toLowerCase(); bv = b.name.toLowerCase(); }}
      else if (sortKey === 'events') {{ av = a.events; bv = b.events; }}
      else if (sortKey === 'last') {{ av = a.last_iso; bv = b.last_iso; }}
      else if (sortKey === 'first') {{ av = a.first_iso; bv = b.first_iso; }}
      if (av < bv) return sortAsc ? -1 : 1;
      if (av > bv) return sortAsc ? 1 : -1;
      return 0;
    }});

    if (list.length === 0) {{
      tbody.innerHTML = '';
      emptyEl.style.display = 'block';
      return;
    }}
    emptyEl.style.display = 'none';

    tbody.innerHTML = list.map(e => `
      <tr class="entity-row" onclick="window.location.href='${{escape(e.slug)}}.html'">
        <td><div class="entity-name"><a href="${{escape(e.slug)}}.html">${{highlight(e.name, query)}}</a></div></td>
        <td><span class="type-pill ${{e.type}}">${{e.type}}</span></td>
        <td class="num-cell accent">${{e.events}}</td>
        <td class="date-cell">${{fmtDate(e.last_iso)}}</td>
        <td class="date-cell">${{fmtDate(e.first_iso)}}</td>
        <td class="num-cell">${{e.editors.length}}</td>
      </tr>
    `).join('');
  }}

  input.addEventListener('input', () => {{ query = input.value; render(); }});

  pills.addEventListener('click', (e) => {{
    const btn = e.target.closest('.filter-pill');
    if (!btn) return;
    pills.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    activeType = btn.dataset.type;
    render();
  }});

  headers.forEach(h => h.addEventListener('click', () => {{
    const k = h.dataset.sort;
    if (sortKey === k) sortAsc = !sortAsc;
    else {{ sortKey = k; sortAsc = (k === 'name'); }}
    headers.forEach(h2 => {{
      h2.classList.toggle('sorted', h2.dataset.sort === sortKey);
      h2.classList.toggle('asc', h2.dataset.sort === sortKey && sortAsc);
    }});
    render();
  }}));

  render();
}})();
</script>
</body>
</html>
"""


# ---------- DETAIL PAGE (PER ENTITY HISTORY) ----------

DETAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{entity_name} · Activity History · {site_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700;9..144,900&family=JetBrains+Mono:wght@400;500;700&family=Inter+Tight:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{common_styles}

  .entity-tag {{
    display: inline-block; padding: 4px 12px; border-radius: 99px;
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    letter-spacing: 0.15em; text-transform: uppercase;
    border: 1px solid; margin-bottom: 16px;
  }}
  .entity-tag.page {{ background: rgba(143,184,255,0.1); color: var(--accent-4); border-color: rgba(143,184,255,0.3); }}
  .entity-tag.article {{ background: rgba(126,224,184,0.1); color: var(--accent-3); border-color: rgba(126,224,184,0.3); }}

  .summary-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--line); border: 1px solid var(--line); margin-bottom: 56px; border-radius: 4px; overflow: hidden; }}
  .stat {{ background: var(--panel); padding: 24px 20px; }}
  .stat-label {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 10px; }}
  .stat-value {{ font-family: 'Fraunces', serif; font-weight: 500; font-size: 40px; line-height: 1; letter-spacing: -0.02em; color: var(--accent); font-variation-settings: 'opsz' 56; }}
  .stat-value.green {{ color: var(--accent-3); }}
  .stat-value.coral {{ color: var(--accent-2); }}
  .stat-value.blue {{ color: var(--accent-4); }}
  .stat-value.small {{ font-size: 22px; line-height: 1.2; }}

  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 56px; }}

  /* action breakdown bars */
  .action-row {{ display: grid; grid-template-columns: 160px 1fr 50px; gap: 12px; align-items: center; margin-bottom: 10px; }}
  .action-name {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--ink-2); letter-spacing: 0.02em; }}
  .action-bar {{ height: 8px; background: var(--panel-2); border-radius: 1px; overflow: hidden; }}
  .action-bar > div {{ height: 100%; background: var(--accent); }}
  .action-row.modified .action-bar > div {{ background: var(--accent); }}
  .action-row.published .action-bar > div {{ background: var(--accent-3); }}
  .action-row.dom .action-bar > div {{ background: var(--accent-2); }}
  .action-row.settings .action-bar > div {{ background: var(--accent-5); }}
  .action-row.code .action-bar > div {{ background: var(--accent-4); }}
  .action-count {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--ink); text-align: right; }}

  /* editor breakdown */
  .editor-row {{ display: grid; grid-template-columns: 1fr 1fr 50px; gap: 12px; align-items: center; margin-bottom: 10px; }}
  .editor-name {{ font-family: 'Fraunces', serif; font-size: 15px; font-weight: 500; }}
  .editor-bar {{ height: 8px; background: var(--panel-2); border-radius: 1px; overflow: hidden; }}
  .editor-bar > div {{ height: 100%; background: var(--accent-3); }}
  .editor-count {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent-3); text-align: right; font-weight: 700; }}

  /* week heatmap */
  .week-strip {{ display: flex; gap: 3px; flex-wrap: nowrap; overflow-x: auto; padding: 4px 0; }}
  .week-cell {{ flex: 1 0 32px; aspect-ratio: 1; border-radius: 3px; position: relative; min-width: 32px; max-width: 60px; transition: transform 0.15s; cursor: pointer; }}
  .week-cell:hover {{ transform: scale(1.15); outline: 1px solid var(--accent); z-index: 5; }}
  .week-cell .tip {{
    position: absolute; bottom: calc(100% + 6px); left: 50%; transform: translateX(-50%);
    background: var(--ink); color: var(--bg);
    padding: 6px 10px; border-radius: 4px;
    font-size: 11px; font-family: 'JetBrains Mono', monospace;
    white-space: nowrap; opacity: 0; pointer-events: none;
    transition: opacity 0.15s; z-index: 20;
  }}
  .week-cell:hover .tip {{ opacity: 1; }}
  .week-strip-labels {{ display: flex; gap: 3px; flex-wrap: nowrap; margin-top: 6px; padding: 0; }}
  .week-strip-labels > div {{ flex: 1 0 32px; min-width: 32px; max-width: 60px; text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 9px; color: var(--ink-3); }}

  /* timeline */
  .timeline {{ position: relative; padding-left: 36px; }}
  .timeline::before {{ content: ''; position: absolute; left: 8px; top: 8px; bottom: 0; width: 1px; background: linear-gradient(to bottom, var(--accent) 0%, var(--line-2) 100%); }}
  .timeline-day {{ margin-bottom: 28px; position: relative; }}
  .timeline-day::before {{ content: ''; position: absolute; left: -36px; top: 6px; width: 17px; height: 17px; background: var(--bg); border: 2px solid var(--accent); border-radius: 50%; }}
  .timeline-date {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--accent); margin-bottom: 12px; }}
  .timeline-events {{ display: flex; flex-direction: column; gap: 8px; }}
  .timeline-event {{
    display: grid; grid-template-columns: 60px 1fr 140px 120px;
    gap: 14px; align-items: baseline;
    padding: 10px 14px;
    background: var(--panel);
    border-radius: 3px; border-left: 2px solid var(--line-2);
    font-size: 13px;
  }}
  .timeline-event:hover {{ background: var(--panel-2); border-left-color: var(--accent); }}
  .timeline-event.published {{ border-left-color: var(--accent-3); }}
  .timeline-event.modified {{ border-left-color: var(--accent); }}
  .timeline-event.dom {{ border-left-color: var(--accent-2); }}
  .timeline-event.settings {{ border-left-color: var(--accent-5); }}
  .timeline-event.code {{ border-left-color: var(--accent-4); }}

  .te-time {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--ink-3); }}
  .te-action {{ color: var(--ink); font-weight: 500; }}
  .te-user {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--ink-2); text-transform: uppercase; letter-spacing: 0.05em; }}
  .te-link {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--accent); text-align: right; text-decoration: none; letter-spacing: 0.1em; text-transform: uppercase; }}
  .te-link:hover {{ color: var(--accent-3); }}

  .timeline-scroll {{ max-height: 720px; overflow-y: auto; padding-right: 12px; }}

  @media (max-width: 900px) {{
    .summary-row {{ grid-template-columns: repeat(2, 1fr); }}
    .two-col {{ grid-template-columns: 1fr; }}
    .timeline-event {{ grid-template-columns: 1fr; gap: 4px; padding: 14px; }}
    .te-link {{ text-align: left; }}
  }}
</style>
</head>
<body>
<div class="grain"></div>
<div class="container">

  <a href="index.html" class="back-link">← BACK TO ALL PAGES & ARTICLES</a>

  <header class="masthead">
    <span class="entity-tag {entity_type}">{entity_type_upper}</span>
    <h1 class="med">{entity_name_html}</h1>
    <p class="deck">{deck_text}</p>
  </header>

  <div class="summary-row">
    <div class="stat">
      <div class="stat-label">Total Events</div>
      <div class="stat-value">{total_events}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Editors</div>
      <div class="stat-value green">{num_editors}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Weeks active</div>
      <div class="stat-value blue">{weeks_active}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Most recent</div>
      <div class="stat-value coral small">{most_recent_label}</div>
    </div>
  </div>

  <section style="margin-bottom:56px">
    <div class="section-head">
      <div class="section-num">§ 01</div>
      <h2>Activity by Week</h2>
      <div class="kicker">{num_weeks_total} WEEKS / {weeks_active} ACTIVE</div>
    </div>
    <div class="panel">
      <div class="panel-title">EVENTS PER WEEK · HOVER FOR DETAIL</div>
      <div class="week-strip">{week_cells}</div>
      <div class="week-strip-labels">{week_labels}</div>
    </div>
  </section>

  <div class="two-col">
    <div class="panel">
      <div class="panel-title">ACTIONS BREAKDOWN</div>
      {actions_html}
    </div>
    <div class="panel">
      <div class="panel-title">WHO MADE THE EDITS</div>
      {editors_html}
    </div>
  </div>

  <section>
    <div class="section-head">
      <div class="section-num">§ 02</div>
      <h2>Full History</h2>
      <div class="kicker">{total_events} EVENTS · NEWEST FIRST</div>
    </div>
    <div class="panel">
      <div class="panel-title">EVERY MODIFICATION, IN ORDER</div>
      <div class="timeline-scroll">
        <div class="timeline">{timeline_html}</div>
      </div>
    </div>
  </section>

  <footer>
    <div>WEBFLOW DATA API · ENTERPRISE ACTIVITY LOG</div>
    <div class="mark">— history of {entity_name_short} —</div>
    <div>UPDATED · {generated_date}</div>
  </footer>
</div>
</body>
</html>
"""


def html_escape(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&#39;'))


def action_class(action):
    """CSS class for an action label."""
    a = action.lower()
    if 'publish' in a:
        return 'published'
    if 'dom' in a:
        return 'dom'
    if 'modif' in a:
        return 'modified'
    if 'setting' in a:
        return 'settings'
    if 'code' in a:
        return 'code'
    return ''


def fmt_iso_date(iso):
    """Format ISO timestamp as 'Apr 22, 2026'."""
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return dt.strftime('%b %-d, %Y').upper()
    except Exception:
        return iso[:10]


def fmt_iso_time(iso):
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return dt.strftime('%H:%M')
    except Exception:
        return iso[11:16] if len(iso) >= 16 else ''


# Names to exclude — these are CSS selectors that get reported as "pages"
# in the activity log but aren't real pages.
EXCLUDED_NAMES = {'body', 'head', 'html'}


def render_detail_page(name, entity_type, events, all_weeks, output_path):
    """Render one detail page for a single entity."""
    # Sort events newest first
    events_sorted = sorted(events, key=lambda e: e['timestamp'], reverse=True)
    total = len(events_sorted)

    # Stats
    editors = Counter(e['user'] for e in events_sorted)
    actions = Counter(e['action'] for e in events_sorted)
    weeks = sorted(set(e['week'] for e in events_sorted))
    weeks_active = len(weeks)

    # Most recent — formatted naturally
    most_recent = events_sorted[0]['timestamp'] if events_sorted else None
    most_recent_label = fmt_iso_date(most_recent) if most_recent else '—'
    if most_recent:
        try:
            dt = datetime.fromisoformat(most_recent.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            days_ago = (now - dt).days
            if days_ago == 0:
                most_recent_label = 'TODAY'
            elif days_ago == 1:
                most_recent_label = 'YESTERDAY'
            elif days_ago < 7:
                most_recent_label = f'{days_ago} DAYS AGO'
            elif days_ago < 31:
                most_recent_label = f'{days_ago // 7} WEEK{"S" if days_ago // 7 != 1 else ""} AGO'
            else:
                most_recent_label = fmt_iso_date(most_recent)
        except Exception:
            pass

    # Deck text
    type_label = 'page' if entity_type == 'page' else 'article'
    first_iso = events_sorted[-1]['timestamp']
    last_iso = events_sorted[0]['timestamp']
    span = f"between {fmt_iso_date(first_iso).title()} and {fmt_iso_date(last_iso).title()}"
    deck = (
        f"Every recorded change to this {type_label}, drawn from {weeks_active} weekly "
        f"report{'s' if weeks_active != 1 else ''}. <strong>{total} event{'s' if total != 1 else ''}</strong> "
        f"by <strong>{len(editors)} editor{'s' if len(editors) != 1 else ''}</strong>, {span}."
    )

    # Action bars
    action_max = max(actions.values()) if actions else 1
    action_rows = []
    for action, count in actions.most_common():
        pct = (count / action_max) * 100
        cls = action_class(action)
        action_rows.append(
            f'<div class="action-row {cls}">'
            f'<div class="action-name">{html_escape(action)}</div>'
            f'<div class="action-bar"><div style="width:{pct:.1f}%"></div></div>'
            f'<div class="action-count">{count}</div>'
            f'</div>'
        )
    actions_html = '\n'.join(action_rows) if action_rows else '<div style="color:var(--ink-3);font-style:italic">No actions.</div>'

    # Editor bars
    editor_max = max(editors.values()) if editors else 1
    editor_rows = []
    for editor, count in editors.most_common():
        pct = (count / editor_max) * 100
        editor_rows.append(
            f'<div class="editor-row">'
            f'<div class="editor-name">{html_escape(editor)}</div>'
            f'<div class="editor-bar"><div style="width:{pct:.1f}%"></div></div>'
            f'<div class="editor-count">{count}</div>'
            f'</div>'
        )
    editors_html = '\n'.join(editor_rows) if editor_rows else '<div style="color:var(--ink-3);font-style:italic">No editors recorded.</div>'

    # Week strip across the whole timeline
    events_by_week = Counter(e['week'] for e in events_sorted)
    max_week_count = max(events_by_week.values()) if events_by_week else 1

    # Map week -> a representative report URL (use the report from any event in that week)
    week_to_report = {}
    for e in events_sorted:
        week_to_report.setdefault(e['week'], e['report'])

    cells = []
    labels = []
    for w in all_weeks:
        count = events_by_week.get(w, 0)
        if count == 0:
            color = 'var(--panel-2)'
        else:
            ratio = (count / max_week_count) ** 0.7
            opacity = 0.2 + 0.75 * ratio
            color = f'rgba(255,216,102,{opacity:.2f})'
        # Find the report URL — even for empty weeks we won't link
        if count > 0 and w in week_to_report:
            link_open = f'<a href="../{html_escape(week_to_report[w])}" style="display:block;width:100%;height:100%;border-radius:3px">'
            link_close = '</a>'
        else:
            link_open = link_close = ''
        cells.append(
            f'<div class="week-cell" style="background:{color}">'
            f'{link_open}{link_close}'
            f'<div class="tip">{w} · {count} event{"s" if count != 1 else ""}</div>'
            f'</div>'
        )
        # Show every other week label so it's not too crowded
        try:
            week_num = int(w.split('W')[1])
            label = f'W{week_num:02d}' if week_num % 2 == 1 else ''
        except Exception:
            label = ''
        labels.append(f'<div>{label}</div>')

    week_cells = '\n'.join(cells)
    week_labels = '\n'.join(labels)

    # Timeline grouped by date
    by_day = defaultdict(list)
    for e in events_sorted:
        day = e['timestamp'][:10]
        by_day[day].append(e)

    day_blocks = []
    for day in sorted(by_day.keys(), reverse=True):
        day_events = by_day[day]
        try:
            dt = datetime.fromisoformat(day)
            day_label = dt.strftime('%a, %b %-d, %Y · {}').format(f'{len(day_events)} event{"s" if len(day_events) != 1 else ""}').upper()
        except Exception:
            day_label = day
        event_rows = []
        for e in day_events:
            cls = action_class(e['action'])
            time_str = fmt_iso_time(e['timestamp'])
            link_html = f'<a href="../{html_escape(e["report"])}" class="te-link">{html_escape(e["week"])} REPORT</a>'
            event_rows.append(
                f'<div class="timeline-event {cls}">'
                f'<div class="te-time">{time_str}</div>'
                f'<div class="te-action">{html_escape(e["action"])}</div>'
                f'<div class="te-user">{html_escape(e["user"])}</div>'
                f'{link_html}'
                f'</div>'
            )
        day_blocks.append(
            f'<div class="timeline-day">'
            f'<div class="timeline-date">{day_label}</div>'
            f'<div class="timeline-events">{"".join(event_rows)}</div>'
            f'</div>'
        )
    timeline_html = '\n'.join(day_blocks)

    # Render
    name_short = name if len(name) <= 50 else name[:50] + '…'
    html = DETAIL_TEMPLATE.format(
        common_styles=COMMON_STYLES,
        site_name=SITE_NAME,
        entity_name=html_escape(name),
        entity_name_html=html_escape(name),
        entity_name_short=html_escape(name_short),
        entity_type=entity_type,
        entity_type_upper=entity_type.upper(),
        deck_text=deck,
        total_events=total,
        num_editors=len(editors),
        weeks_active=weeks_active,
        num_weeks_total=len(all_weeks),
        most_recent_label=most_recent_label,
        actions_html=actions_html,
        editors_html=editors_html,
        week_cells=week_cells,
        week_labels=week_labels,
        timeline_html=timeline_html,
        generated_date=datetime.now(timezone.utc).strftime('%b %-d, %Y · %H:%M UTC').upper(),
    )

    output_path.write_text(html)


def main():
    parser = argparse.ArgumentParser(description='Generate per-entity history pages.')
    parser.add_argument('--reports-dir', default='reports', help='Directory containing report sidecars')
    parser.add_argument('--output-dir', default='pages', help='Where to write the page directory')
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading page events from sidecars in {reports_dir}/...")
    all_events = load_all_events(reports_dir)
    print(f"  loaded {len(all_events)} page-level events")

    if not all_events:
        print("  no events found — nothing to generate.")
        return 0

    # Group events by entity (skipping CSS selectors miscategorized as pages)
    by_entity = defaultdict(list)
    for e in all_events:
        if e['entity'].lower() in EXCLUDED_NAMES:
            continue
        by_entity[(e['entity'], e['entity_type'])].append(e)

    # All weeks that have ANY data, used for the per-entity heatmap strip
    all_weeks = sorted(set(e['week'] for e in all_events))

    # Slug map
    slug_map = {}
    used_slugs = set()
    for (name, etype) in by_entity.keys():
        s = slugify(name)
        # Avoid collisions
        base = s
        i = 2
        while s in used_slugs:
            s = f"{base}-{i}"
            i += 1
        used_slugs.add(s)
        slug_map[(name, etype)] = s

    # Generate detail pages
    print(f"Generating {len(by_entity)} detail pages...")
    entity_summary = []
    for (name, etype), events in by_entity.items():
        slug = slug_map[(name, etype)]
        detail_path = output_dir / f"{slug}.html"
        render_detail_page(name, etype, events, all_weeks, detail_path)

        editors = sorted(set(e['user'] for e in events))
        timestamps = sorted(e['timestamp'] for e in events)
        entity_summary.append({
            'name': name,
            'type': etype,
            'slug': slug,
            'events': len(events),
            'editors': editors,
            'first_iso': timestamps[0],
            'last_iso': timestamps[-1],
        })

    # Sort by event count desc for default
    entity_summary.sort(key=lambda e: e['events'], reverse=True)

    # Generate index page
    num_pages = sum(1 for e in entity_summary if e['type'] == 'page')
    num_articles = sum(1 for e in entity_summary if e['type'] == 'article')
    all_editors = set()
    for e in all_events:
        all_editors.add(e['user'])

    # Count distinct weekly reports we drew from
    sidecar_count = sum(1 for f in reports_dir.iterdir() if f.name.endswith('.pages.json'))

    index_html = INDEX_TEMPLATE.format(
        common_styles=COMMON_STYLES,
        site_name=SITE_NAME,
        total_entities=len(entity_summary),
        num_pages=num_pages,
        num_articles=num_articles,
        total_events=len(all_events),
        num_editors=len(all_editors),
        num_reports=sidecar_count,
        generated_date=datetime.now(timezone.utc).strftime('%b %-d, %Y · %H:%M UTC').upper(),
    )
    index_html = index_html.replace(
        '__ENTITIES_JSON_SENTINEL__',
        json.dumps(entity_summary),
    )

    (output_dir / 'index.html').write_text(index_html)
    print(f"✓ Index written: {output_dir}/index.html ({len(entity_summary)} entities)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
