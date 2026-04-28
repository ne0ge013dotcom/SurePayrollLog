#!/usr/bin/env python3
"""
Generate index.html — a dashboard listing every weekly report.

Scans the reports/ directory for HTML files matching the pattern
{year-week}_{start}_{end}.html and extracts metadata for the listing.

Usage:
    python generate_index.py --reports-dir reports --output index.html
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone


SITE_NAME = "SurePayroll"


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{site_name} · Webflow Activity · All Reports</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700;9..144,900&family=JetBrains+Mono:wght@400;500;700&family=Inter+Tight:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0e0e10; --panel: #16161a; --panel-2: #1c1c22;
    --line: #2a2a32; --line-2: #3a3a44;
    --ink: #f5f0e8; --ink-2: #b8b4ac; --ink-3: #76737a;
    --accent: #ffd866; --accent-2: #f97e72; --accent-3: #7ee0b8;
    --accent-4: #8fb8ff; --accent-5: #c89cff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: var(--bg); color: var(--ink);
    font-family: 'Inter Tight', -apple-system, sans-serif;
    line-height: 1.5; -webkit-font-smoothing: antialiased;
  }}
  body {{
    background:
      radial-gradient(ellipse 80% 50% at 50% -20%, rgba(255,216,102,0.08), transparent 70%),
      radial-gradient(ellipse 60% 40% at 100% 50%, rgba(126,224,184,0.04), transparent 70%),
      var(--bg);
    background-attachment: fixed; min-height: 100vh;
  }}
  .grain {{
    position: fixed; inset: 0; pointer-events: none; opacity: 0.03; z-index: 100;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' /%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.6'/%3E%3C/svg%3E");
  }}
  .container {{ max-width: 1280px; margin: 0 auto; padding: 48px 32px; }}

  .masthead {{ border-bottom: 1px solid var(--line); padding-bottom: 40px; margin-bottom: 56px; position: relative; }}
  .masthead::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, var(--accent), transparent); }}
  .meta-row {{ display: flex; justify-content: space-between; align-items: center; font-family: 'JetBrains Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.15em; color: var(--ink-3); margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }}
  .meta-row .left {{ color: var(--accent); }}
  h1 {{ font-family: 'Fraunces', serif; font-weight: 400; font-size: clamp(48px, 7vw, 108px); line-height: 0.92; letter-spacing: -0.03em; margin-bottom: 24px; font-variation-settings: 'opsz' 144; }}
  h1 em {{ font-style: italic; font-weight: 300; color: var(--accent); }}
  .deck {{ font-family: 'Fraunces', serif; font-size: 22px; line-height: 1.4; color: var(--ink-2); max-width: 720px; }}
  .deck strong {{ color: var(--ink); font-weight: 500; }}

  /* ========== SEARCH ========== */
  .search-wrap {{
    margin-bottom: 56px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 24px;
    position: relative;
  }}
  .search-wrap::before {{
    content: ''; position: absolute; top: 0; left: 0;
    width: 100%; height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent-3), transparent);
  }}
  .search-label {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.2em; color: var(--ink-3);
    margin-bottom: 12px;
  }}
  .search-input-wrap {{
    position: relative;
  }}
  .search-input {{
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: 14px 18px 14px 48px;
    color: var(--ink);
    font-family: 'Fraunces', serif;
    font-size: 22px;
    font-weight: 400;
    line-height: 1.2;
    transition: border-color 0.15s;
    font-variation-settings: 'opsz' 24;
  }}
  .search-input:focus {{
    outline: none;
    border-color: var(--accent);
  }}
  .search-input::placeholder {{
    color: var(--ink-3);
    font-style: italic;
  }}
  .search-icon {{
    position: absolute; left: 16px; top: 50%; transform: translateY(-50%);
    width: 22px; height: 22px; color: var(--ink-3);
    pointer-events: none;
  }}
  .search-input:focus ~ .search-icon {{ color: var(--accent); }}
  .search-clear {{
    position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
    background: var(--panel-2); border: none;
    color: var(--ink-3); cursor: pointer;
    width: 28px; height: 28px; border-radius: 99px;
    font-family: 'JetBrains Mono', monospace; font-size: 12px;
    display: none; align-items: center; justify-content: center;
  }}
  .search-clear.visible {{ display: flex; }}
  .search-clear:hover {{ color: var(--ink); background: var(--line-2); }}

  .filter-pills {{
    display: flex; gap: 6px; margin-top: 14px; flex-wrap: wrap;
  }}
  .filter-pill {{
    background: var(--panel-2); border: 1px solid var(--line);
    color: var(--ink-2); cursor: pointer;
    padding: 5px 12px; border-radius: 99px;
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.1em;
    transition: all 0.15s;
  }}
  .filter-pill:hover {{ border-color: var(--ink-3); color: var(--ink); }}
  .filter-pill.active {{
    background: var(--accent); color: var(--bg); border-color: var(--accent);
    font-weight: 700;
  }}

  .search-status {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: var(--ink-3); letter-spacing: 0.05em;
    margin-top: 14px;
    min-height: 14px;
  }}
  .search-status strong {{ color: var(--accent-3); font-weight: 700; }}

  .search-results {{
    margin-top: 18px;
    max-height: 560px; overflow-y: auto;
    display: none;
    border-top: 1px dashed var(--line-2);
    padding-top: 18px;
  }}
  .search-results.visible {{ display: block; }}

  .result-group {{
    margin-bottom: 24px;
  }}
  .result-group-title {{
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-3);
    margin-bottom: 10px;
    display: flex; align-items: baseline; gap: 8px;
  }}
  .result-group-count {{
    color: var(--accent); font-weight: 700;
  }}
  .result-list {{
    display: flex; flex-direction: column; gap: 4px;
  }}
  .result-item {{
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 12px; align-items: baseline;
    padding: 10px 14px;
    background: var(--panel-2);
    border-radius: 3px;
    border-left: 2px solid var(--line-2);
    transition: all 0.12s;
  }}
  .result-item:hover {{
    background: var(--bg); border-left-color: var(--accent);
    transform: translateX(2px);
  }}
  .result-item.cat-page {{ border-left-color: var(--accent-4); }}
  .result-item.cat-article {{ border-left-color: var(--accent-3); }}
  .result-item.cat-user {{ border-left-color: var(--accent); }}
  .result-item.cat-publish {{ border-left-color: var(--accent-2); }}
  .result-item.cat-milestone {{ border-left-color: var(--accent-5); }}

  .result-main-link {{
    text-decoration: none; color: inherit;
    display: block; overflow: hidden;
  }}
  .result-main {{ overflow: hidden; }}
  .result-title {{
    font-family: 'Fraunces', serif; font-size: 15px; font-weight: 500;
    line-height: 1.3; color: var(--ink);
    overflow: hidden; text-overflow: ellipsis;
  }}
  .result-title mark {{
    background: rgba(255,216,102,0.25); color: var(--accent);
    border-radius: 2px; padding: 0 2px;
  }}
  .result-title .history-arrow {{
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    color: var(--accent); letter-spacing: 0.1em;
    text-transform: uppercase; margin-left: 6px;
    opacity: 0.6; transition: opacity 0.12s;
  }}
  .result-main-link:hover .history-arrow {{ opacity: 1; }}
  .result-main-link:hover .result-title {{ color: var(--accent); }}
  .result-detail {{
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    color: var(--ink-3); margin-top: 3px; letter-spacing: 0.05em;
  }}

  .result-meta {{
    text-align: right; flex-shrink: 0;
    display: flex; flex-direction: column; align-items: flex-end; gap: 2px;
  }}
  .result-period, .result-period-link {{
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    color: var(--ink-2); letter-spacing: 0.05em;
    text-transform: uppercase;
    text-decoration: none;
  }}
  .result-period-link:hover {{ color: var(--accent); }}
  .result-week {{
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    color: var(--ink-3); letter-spacing: 0.15em;
  }}
  .result-week-link {{
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    color: var(--ink-3); letter-spacing: 0.15em;
    text-decoration: none;
    transition: color 0.12s;
  }}
  .result-week-link:hover {{ color: var(--accent); }}

  .search-empty {{
    text-align: center; padding: 40px 20px;
    color: var(--ink-3); font-family: 'Fraunces', serif;
    font-size: 18px; font-style: italic;
  }}

  /* ========== STATS ========== */
  .summary-stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--line); border: 1px solid var(--line); margin-bottom: 64px; border-radius: 4px; overflow: hidden; }}
  .stat {{ background: var(--panel); padding: 28px 24px; }}
  .stat-label {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 12px; }}
  .stat-value {{ font-family: 'Fraunces', serif; font-weight: 500; font-size: 48px; line-height: 1; letter-spacing: -0.02em; color: var(--accent); }}
  .stat-value.green {{ color: var(--accent-3); }}
  .stat-value.coral {{ color: var(--accent-2); }}
  .stat-value.blue {{ color: var(--accent-4); }}

  .section-head {{ display: flex; align-items: baseline; gap: 16px; margin-bottom: 32px; padding-bottom: 16px; border-bottom: 1px solid var(--line); }}
  .section-num {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--accent); letter-spacing: 0.2em; }}
  .section-head h2 {{ font-family: 'Fraunces', serif; font-weight: 500; font-size: 36px; letter-spacing: -0.02em; line-height: 1; }}
  .section-head .kicker {{ margin-left: auto; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--ink-3); letter-spacing: 0.1em; }}

  /* Year section grouping */
  .year-block {{ margin-bottom: 56px; }}
  .year-label {{
    font-family: 'JetBrains Mono', monospace; font-size: 12px;
    letter-spacing: 0.3em; color: var(--ink-3); text-transform: uppercase;
    margin-bottom: 20px; padding-bottom: 8px;
    border-bottom: 1px dashed var(--line-2);
  }}

  .reports-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; }}
  .report-card {{
    display: block;
    background: var(--panel); border: 1px solid var(--line);
    border-radius: 4px; padding: 24px;
    text-decoration: none; color: inherit;
    transition: transform 0.18s, border-color 0.18s, box-shadow 0.18s;
    position: relative; overflow: hidden;
  }}
  .report-card::before {{
    content: ''; position: absolute; left: 0; top: 0;
    width: 3px; height: 100%; background: var(--line-2);
    transition: background 0.18s;
  }}
  .report-card:hover {{
    transform: translateY(-2px); border-color: var(--accent);
    box-shadow: 0 12px 32px -12px rgba(255,216,102,0.18);
  }}
  .report-card:hover::before {{ background: var(--accent); }}
  .report-card.latest {{ border-color: rgba(255,216,102,0.5); }}
  .report-card.latest::before {{ background: var(--accent); }}
  .report-card.latest .latest-tag {{
    position: absolute; top: 12px; right: 12px;
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    letter-spacing: 0.2em; text-transform: uppercase;
    background: var(--accent); color: var(--bg);
    padding: 3px 8px; border-radius: 2px; font-weight: 700;
  }}

  .report-week {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    letter-spacing: 0.2em; color: var(--accent);
    text-transform: uppercase; margin-bottom: 8px;
  }}
  .report-period {{
    font-family: 'Fraunces', serif; font-weight: 500;
    font-size: 22px; letter-spacing: -0.01em; line-height: 1.2;
    margin-bottom: 20px;
  }}
  .report-stats {{
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 12px; padding-top: 16px; border-top: 1px dashed var(--line);
  }}
  .report-stat-label {{
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    letter-spacing: 0.15em; text-transform: uppercase; color: var(--ink-3);
    margin-bottom: 4px;
  }}
  .report-stat-value {{
    font-family: 'Fraunces', serif; font-weight: 500; font-size: 20px;
    color: var(--ink);
  }}
  .report-stat-value.events {{ color: var(--accent); }}
  .report-stat-value.publishes {{ color: var(--accent-2); }}
  .report-stat-value.users {{ color: var(--accent-3); }}

  .empty-state {{
    text-align: center; padding: 80px 20px;
    background: var(--panel); border: 1px dashed var(--line-2); border-radius: 4px;
  }}
  .empty-state h3 {{ font-family: 'Fraunces', serif; font-size: 32px; color: var(--ink-2); margin-bottom: 12px; font-weight: 500; }}
  .empty-state p {{ color: var(--ink-3); }}

  footer {{ margin-top: 80px; padding-top: 32px; border-top: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--ink-3); letter-spacing: 0.15em; text-transform: uppercase; flex-wrap: wrap; gap: 16px; }}
  footer .mark {{ font-family: 'Fraunces', serif; font-style: italic; color: var(--ink-2); text-transform: none; letter-spacing: 0; font-size: 13px; }}

  ::-webkit-scrollbar {{ height: 8px; width: 8px; }}
  ::-webkit-scrollbar-track {{ background: var(--panel); }}
  ::-webkit-scrollbar-thumb {{ background: var(--line-2); border-radius: 99px; }}

  @media (max-width: 900px) {{
    .summary-stats {{ grid-template-columns: repeat(2, 1fr); }}
    .search-input {{ font-size: 18px; }}
  }}
</style>
</head>
<body>
<script>window.__SEARCH_DATA__ = __SEARCH_DATA_JSON_SENTINEL__;</script>
<div class="grain"></div>
<div class="container">

  <header class="masthead">
    <div class="meta-row">
      <div class="left">◆ ARCHIVE</div>
      <div>{site_name} · WEBFLOW WORKSPACE</div>
      <div>{num_reports} REPORTS</div>
    </div>
    <h1>The <em>Weekly</em><br>Archive.</h1>
    <p class="deck">Every weekly activity report for the {site_name} Webflow site, generated automatically each Monday morning. Search across all reports below, or browse by week.</p>
  </header>

  <!-- ===== SEARCH ===== -->
  <div class="search-wrap">
    <div class="search-label">SEARCH ACROSS ALL {num_reports} REPORTS</div>
    <div class="search-input-wrap">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="7"/>
        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input type="text" class="search-input" id="searchInput" placeholder="Try: New Sign Up, Marina, EIN, payment, partners.surepayroll..." autocomplete="off" spellcheck="false">
      <button class="search-clear" id="searchClear" aria-label="Clear search">✕</button>
    </div>
    <div class="filter-pills" id="filterPills">
      <button class="filter-pill active" data-cat="all">All</button>
      <button class="filter-pill" data-cat="page">Pages</button>
      <button class="filter-pill" data-cat="article">Articles</button>
      <button class="filter-pill" data-cat="user">People</button>
      <button class="filter-pill" data-cat="publish">Publishes</button>
      <button class="filter-pill" data-cat="milestone">Milestones</button>
    </div>
    <div class="search-status" id="searchStatus">Type to search across {entries_count} entries from every report.</div>
    <div class="search-results" id="searchResults"></div>
  </div>

  <div class="summary-stats">
    <div class="stat">
      <div class="stat-label">Reports Generated</div>
      <div class="stat-value">{num_reports}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Total Events Tracked</div>
      <div class="stat-value blue">{total_events:,}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Total Publishes</div>
      <div class="stat-value coral">{total_publishes}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Latest Report</div>
      <div class="stat-value green" style="font-size:24px;line-height:1.2">{latest_period}</div>
    </div>
  </div>

  <section style="margin-bottom:56px">
    <a href="pages/index.html" style="display:block;background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:32px;text-decoration:none;color:inherit;transition:all 0.18s;position:relative;overflow:hidden">
      <div style="position:absolute;left:0;top:0;width:3px;height:100%;background:var(--accent-3)"></div>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap">
        <div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:0.2em;color:var(--accent-3);text-transform:uppercase;margin-bottom:8px">◆ NEW VIEW</div>
          <div style="font-family:'Fraunces',serif;font-weight:500;font-size:32px;line-height:1.1;letter-spacing:-0.02em;margin-bottom:6px">Browse by Page or Article →</div>
          <div style="color:var(--ink-2);font-size:14px;line-height:1.4;max-width:640px">See the full edit history of any single page or article — every modification, publish, and rename across every report.</div>
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--ink-3);text-align:right;letter-spacing:0.15em;text-transform:uppercase;line-height:1.6">
          <div style="color:var(--accent-3);font-family:'Fraunces',serif;font-size:36px;font-weight:500;line-height:1">→</div>
        </div>
      </div>
    </a>
  </section>

  <section>
    <div class="section-head">
      <div class="section-num">§ 01</div>
      <h2>All Reports</h2>
      <div class="kicker">NEWEST FIRST</div>
    </div>
    {report_blocks}
  </section>

  <footer>
    <div>WEBFLOW DATA API · ENTERPRISE ACTIVITY LOG</div>
    <div class="mark">— index regenerated each run —</div>
    <div>UPDATED · {generated_date}</div>
  </footer>
</div>

<script>
(function() {{
  const input = document.getElementById('searchInput');
  const clearBtn = document.getElementById('searchClear');
  const status = document.getElementById('searchStatus');
  const results = document.getElementById('searchResults');
  const pillContainer = document.getElementById('filterPills');

  let SEARCH_DATA = window.__SEARCH_DATA__ || [];
  let activeCategory = 'all';
  let lastQuery = '';

  // Category labels and ordering for grouped output
  const CAT_LABELS = {{
    page: 'Pages',
    article: 'Articles',
    user: 'People',
    publish: 'Publishes',
    milestone: 'Milestones',
    'event-type': 'Event types',
  }};
  const CAT_ORDER = ['page', 'article', 'user', 'publish', 'milestone', 'event-type'];

  // Initial status
  if (SEARCH_DATA.length > 0) {{
    status.textContent = `Type to search across ${{SEARCH_DATA.length.toLocaleString()}} entries from every report.`;
  }} else {{
    status.textContent = 'No search index available. Generate a report to populate it.';
  }}

  function escapeHtml(s) {{
    return String(s).replace(/[&<>"']/g, c =>
      ({{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }})[c]);
  }}

  function highlight(text, query) {{
    if (!query) return escapeHtml(text);
    const escaped = escapeHtml(text);
    // Match each word in query individually so multi-word search works
    const words = query.trim().split(/\\s+/).filter(w => w.length > 0);
    if (words.length === 0) return escaped;
    // Build a regex that matches any of the words
    const re = new RegExp('(' + words.map(w =>
      w.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&')).join('|') + ')', 'gi');
    return escaped.replace(re, '<mark>$1</mark>');
  }}

  function searchEntries(query, category) {{
    if (!query || query.trim().length < 2) {{
      // No query: show only category filter (or nothing if 'all')
      if (category === 'all') return [];
      return SEARCH_DATA.filter(e => e.cat === category);
    }}
    const q = query.toLowerCase().trim();
    const words = q.split(/\\s+/).filter(w => w.length > 0);
    const filtered = SEARCH_DATA.filter(e => {{
      if (category !== 'all' && e.cat !== category) return false;
      const hay = ((e.haystack || '') + ' ' + (e.title || '') + ' ' + (e.detail || '')).toLowerCase();
      return words.every(w => hay.indexOf(w) !== -1);
    }});

    // Score by how many words match in title (more relevant = higher score)
    return filtered.map(e => {{
      const title = (e.title || '').toLowerCase();
      let score = 0;
      for (const w of words) if (title.indexOf(w) !== -1) score += 2;
      // Bonus if title starts with the first word
      if (title.startsWith(words[0])) score += 3;
      return {{ entry: e, score }};
    }}).sort((a, b) => b.score - a.score).map(x => x.entry);
  }}

  function render(query, category) {{
    const matches = searchEntries(query, category);

    // Update status line
    if (!query || query.trim().length < 2) {{
      if (category === 'all') {{
        status.innerHTML = `Type at least 2 characters to search across <strong>${{SEARCH_DATA.length.toLocaleString()}}</strong> entries.`;
        results.classList.remove('visible');
        results.innerHTML = '';
        return;
      }}
      status.innerHTML = `Showing all <strong>${{matches.length.toLocaleString()}}</strong> ${{CAT_LABELS[category] || category}} entries.`;
    }} else {{
      const catLabel = category === 'all' ? '' : ` in ${{CAT_LABELS[category] || category}}`;
      status.innerHTML = `<strong>${{matches.length.toLocaleString()}}</strong> result${{matches.length === 1 ? '' : 's'}} for "${{escapeHtml(query)}}"${{catLabel}}`;
    }}

    if (matches.length === 0) {{
      results.classList.add('visible');
      results.innerHTML = '<div class="search-empty">Nothing matched. Try a different word or clear filters.</div>';
      return;
    }}

    // Group matches by category
    const grouped = {{}};
    for (const m of matches) {{
      if (!grouped[m.cat]) grouped[m.cat] = [];
      grouped[m.cat].push(m);
    }}

    let html = '';
    for (const cat of CAT_ORDER) {{
      if (!grouped[cat]) continue;
      const items = grouped[cat];
      // Cap at 50 per category so the list stays manageable
      const displayed = items.slice(0, 50);
      const more = items.length - displayed.length;
      html += `<div class="result-group">
        <div class="result-group-title">
          <span>${{CAT_LABELS[cat] || cat}}</span>
          <span class="result-group-count">${{items.length}}${{more > 0 ? ` (showing 50)` : ''}}</span>
        </div>
        <div class="result-list">`;
      for (const e of displayed) {{
        // For page/article entries, the title links to the history page;
        // the period/week shown on the right links separately to the weekly report.
        const hasHistory = (e.cat === 'page' || e.cat === 'article') && e.slug;
        const primaryHref = hasHistory ? `pages/${{escapeHtml(e.slug)}}.html` : escapeHtml(e.report);
        const reportHref = escapeHtml(e.report);
        const historyArrow = hasHistory
          ? ' <span class="history-arrow">→ history</span>'
          : '';
        const ctxLink = hasHistory
          ? `<a href="${{reportHref}}" class="result-week-link" title="See this in the ${{escapeHtml(e.week || 'week')}} report">${{escapeHtml(e.week || '')}} →</a>`
          : `<a href="${{reportHref}}" class="result-week" style="text-decoration:none;color:inherit">${{escapeHtml(e.week || '')}}</a>`;

        html += `<div class="result-item cat-${{e.cat}}">
          <a href="${{primaryHref}}" class="result-main-link">
            <div class="result-main">
              <div class="result-title">${{highlight(e.title, query)}}${{historyArrow}}</div>
              <div class="result-detail">${{highlight(e.detail || '', query)}}</div>
            </div>
          </a>
          <div class="result-meta">
            <a href="${{reportHref}}" class="result-period-link">${{escapeHtml(e.period || '')}}</a>
            ${{ctxLink}}
          </div>
        </div>`;
      }}
      html += '</div></div>';
    }}

    results.innerHTML = html;
    results.classList.add('visible');
  }}

  function update() {{
    const q = input.value;
    lastQuery = q;
    clearBtn.classList.toggle('visible', q.length > 0);
    render(q, activeCategory);
  }}

  // Wire up search input (debounced)
  let debounceTimer = null;
  input.addEventListener('input', () => {{
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(update, 80);
  }});

  // Clear button
  clearBtn.addEventListener('click', () => {{
    input.value = '';
    update();
    input.focus();
  }});

  // ESC to clear
  input.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape') {{
      input.value = '';
      update();
    }}
  }});

  // Filter pills
  pillContainer.addEventListener('click', (e) => {{
    const btn = e.target.closest('.filter-pill');
    if (!btn) return;
    pillContainer.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    activeCategory = btn.dataset.cat;
    update();
  }});

  // Keyboard shortcut: / to focus search (when not already typing)
  document.addEventListener('keydown', (e) => {{
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {{
      e.preventDefault();
      input.focus();
    }}
  }});
}})();
</script>
</body>
</html>
"""


def parse_report_filename(filename):
    """Extract metadata from filename like '2026-W17_2026-04-21_2026-04-27.html'."""
    m = re.match(r'^(\d{4})-W(\d{1,2})_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.html$', filename)
    if not m:
        return None
    return {
        'year': int(m.group(1)),
        'week': int(m.group(2)),
        'start': m.group(3),
        'end': m.group(4),
        'filename': filename,
    }


def extract_report_meta(html_path):
    """Pull the data payload out of a generated report so we can show stats."""
    try:
        text = html_path.read_text()
        # Find the embedded JSON
        m = re.search(r'const REPORT_DATA = (\{.*?\});\s*\n', text, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(1))
        summary = data.get('summary', {})
        return {
            'total_events': summary.get('total_events', 0),
            'publishes': summary.get('total_publishes', 0),
            'contributors': len(summary.get('user_counts', {})),
        }
    except Exception as e:
        print(f"  warning: could not parse {html_path.name}: {e}")
        return None


def format_period(start_str, end_str):
    s = datetime.fromisoformat(start_str)
    e = datetime.fromisoformat(end_str)
    if s.month == e.month:
        return f"{s.strftime('%b %-d')} – {e.strftime('%-d, %Y')}"
    if s.year == e.year:
        return f"{s.strftime('%b %-d')} – {e.strftime('%b %-d, %Y')}"
    return f"{s.strftime('%b %-d, %Y')} – {e.strftime('%b %-d, %Y')}"


def main():
    parser = argparse.ArgumentParser(description='Generate index.html listing all reports.')
    parser.add_argument('--reports-dir', default='reports', help='Directory containing report HTML files')
    parser.add_argument('--output', default='index.html', help='Output index path')
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Find and parse all report files
    reports = []
    for f in reports_dir.iterdir():
        if not f.is_file() or not f.name.endswith('.html'):
            continue
        meta = parse_report_filename(f.name)
        if not meta:
            continue
        stats = extract_report_meta(f) or {}
        meta.update(stats)
        meta['relative_path'] = f"{reports_dir.name}/{f.name}"
        meta['period'] = format_period(meta['start'], meta['end'])
        reports.append(meta)

    # Sort newest first
    reports.sort(key=lambda r: (r['year'], r['week']), reverse=True)

    # ---- Build aggregated search index from sidecar files ----
    # Each report writes <basename>.search.json beside it; merge them all.
    aggregated_search = []
    for r in reports:
        sidecar = reports_dir / (Path(r['filename']).stem + '.search.json')
        if not sidecar.exists():
            continue
        try:
            entries = json.loads(sidecar.read_text())
            for e in entries:
                # Tag each entry with which week it belongs to
                e['week'] = f"{r['year']}-W{r['week']:02d}"
            aggregated_search.extend(entries)
        except Exception as ex:
            print(f"  warning: could not load search sidecar {sidecar.name}: {ex}")

    # Write the merged search index next to the index.html
    search_index_path = Path(args.output).parent / 'search_index.json'
    search_index_path.write_text(json.dumps(aggregated_search))
    print(f"  search index: {len(aggregated_search)} entries → {search_index_path}")

    # Aggregate stats
    total_events = sum(r.get('total_events', 0) for r in reports)
    total_publishes = sum(r.get('publishes', 0) for r in reports)
    latest_period = reports[0]['period'] if reports else 'No reports yet'

    # Build report cards grouped by year
    if not reports:
        report_blocks = """
        <div class="empty-state">
          <h3>No reports yet</h3>
          <p>Run <code>python scripts/generate_report.py --start YYYY-MM-DD --end YYYY-MM-DD</code> to generate one.</p>
        </div>
        """
    else:
        # Group by year
        by_year = {}
        for r in reports:
            by_year.setdefault(r['year'], []).append(r)

        blocks = []
        for year in sorted(by_year.keys(), reverse=True):
            year_reports = by_year[year]
            cards = []
            for i, r in enumerate(year_reports):
                # Latest report overall = first card of newest year
                is_latest = (year == reports[0]['year'] and r['week'] == reports[0]['week'])
                latest_tag = '<div class="latest-tag">LATEST</div>' if is_latest else ''
                latest_class = 'latest' if is_latest else ''

                events = r.get('total_events', 0)
                pubs = r.get('publishes', 0)
                users = r.get('contributors', 0)

                cards.append(f"""
                <a href="{r['relative_path']}" class="report-card {latest_class}">
                  {latest_tag}
                  <div class="report-week">WEEK {r['week']:02d} · {r['year']}</div>
                  <div class="report-period">{r['period']}</div>
                  <div class="report-stats">
                    <div class="report-stat">
                      <div class="report-stat-label">Events</div>
                      <div class="report-stat-value events">{events:,}</div>
                    </div>
                    <div class="report-stat">
                      <div class="report-stat-label">Publishes</div>
                      <div class="report-stat-value publishes">{pubs}</div>
                    </div>
                    <div class="report-stat">
                      <div class="report-stat-label">People</div>
                      <div class="report-stat-value users">{users}</div>
                    </div>
                  </div>
                </a>
                """)

            blocks.append(f"""
            <div class="year-block">
              <div class="year-label">— {year} · {len(year_reports)} report{'s' if len(year_reports) != 1 else ''} —</div>
              <div class="reports-grid">
                {''.join(cards)}
              </div>
            </div>
            """)

        report_blocks = ''.join(blocks)

    html = INDEX_TEMPLATE.format(
        site_name=SITE_NAME,
        num_reports=len(reports),
        total_events=total_events,
        total_publishes=total_publishes,
        latest_period=latest_period,
        report_blocks=report_blocks,
        entries_count=f"{len(aggregated_search):,}",
        generated_date=datetime.now(timezone.utc).strftime('%b %-d, %Y · %H:%M UTC').upper(),
    )

    # Inject the search data after format() so JSON braces don't break .format()
    html = html.replace(
        '__SEARCH_DATA_JSON_SENTINEL__',
        json.dumps(aggregated_search),
    )

    Path(args.output).write_text(html)
    print(f"✓ Index written: {args.output} ({len(reports)} reports listed)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
