# SurePayroll Webflow Activity Reporter

Generates a beautiful weekly HTML activity report for the SurePayroll Webflow site, every Monday morning.

## What you get

- **`index.html`** — dashboard listing all reports, newest first, grouped by year, **with a search bar that searches across every report at once**
- **`reports/YYYY-Wnn_YYYY-MM-DD_YYYY-MM-DD.html`** — one per week, fully self-contained interactive page
- A GitHub Action that runs every Monday at 8am Chicago time, generates the report for the previous week, and commits it back to the repo

## The search

The dashboard's search box looks across every report at once. You can find:
- **Pages** — "New Sign Up", "Payment Processing", "Pricing"
- **Articles** — "EIN", "Form 941", any keyword from an article title
- **People** — "Marina", "Dustin", "Kevin"
- **Domains** — "partners", "blog", "www.surepayroll"
- **Milestones** — "library install", "branch", "production publish"

Results are grouped by category and link straight to the report where it happened. Filter pills above the box (All / Pages / Articles / People / Publishes / Milestones) narrow the search to one type. Press `/` anywhere on the page to jump to the search box.

## Architecture

```
scripts/
  generate_report.py    # the engine — fetches API, renders one HTML report
  generate_index.py     # scans reports/ and builds the dashboard
  backfill.py           # generates many reports in one go (uses cached events)
  weekly_run.py         # the Monday-morning runner (last Mon-Sun)
  report_template.html  # the HTML template — design lives here
.github/workflows/
  weekly.yml            # the cron schedule
reports/                # generated reports go here
index.html              # generated dashboard
```

---

## Setup (one time)

### 1. Get a Webflow API token

Webflow → **Site Settings** → **Apps & Integrations** → **API access** → **Generate API token**

The token needs the **`sites:read`** and **`activity:read`** scopes (Enterprise plan required for activity logs).

Save the token somewhere safe — you'll paste it into GitHub in a moment.

### 2. Create the GitHub repo

```bash
# from this folder
git init
git add .
git commit -m "Initial reporter setup"

# create a repo on github.com (private is fine), then:
git remote add origin git@github.com:YOU/surepayroll-webflow-reports.git
git branch -M main
git push -u origin main
```

### 3. Add secrets to GitHub

In your GitHub repo, go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret** and add:

| Name | Value |
|---|---|
| `WEBFLOW_API_TOKEN` | the token from step 1 |
| `WEBFLOW_SITE_ID` | `65a823bc36fc91ffafdc2c3e` (already the SurePayroll site) |

### 4. Run the backfill (one time, from GitHub — no terminal needed)

This generates a report for every week from Jan 1, 2026 to today (~18 reports).

1. Push the code to GitHub (you did this in step 2)
2. In the repo, click the **Actions** tab
3. Click **Weekly Webflow Activity Report** in the left sidebar
4. Click the **Run workflow** dropdown on the right
5. In the **backfill_from** field, type `2026-01-01`
6. Click the green **Run workflow** button

About 3 minutes later, the action finishes and you'll see a fresh commit on `main` with all 18 reports plus an updated `index.html`.

> **If you'd rather run it locally** (not necessary):
> ```bash
> export WEBFLOW_API_TOKEN=your_token_here
> python3 scripts/backfill.py --from 2026-01-01
> git add reports/ index.html && git commit -m "Backfill 2026" && git push
> ```

### 5. View the reports

If you want to view them on your own machine, just open `index.html` in a browser.

If you want a public URL, enable GitHub Pages: **Settings** → **Pages** → Source: **Deploy from a branch** → Branch: **main** → Folder: **`/ (root)`**. After ~1 minute your archive lives at `https://YOU.github.io/surepayroll-webflow-reports/`.

---

## Running on a schedule

### Automatic (recommended) — GitHub Actions

The workflow at `.github/workflows/weekly.yml` runs every Monday at 13:00 UTC (8am Chicago / 9am EDT). It:

1. Generates last week's report (previous Monday-Sunday)
2. Rebuilds `index.html`
3. Commits both back to the repo

You don't need your computer on. GitHub provides 2,000 free Action minutes per month for private repos and unlimited for public repos. Each run takes ~30 seconds.

To change the schedule, edit the `cron` line in `weekly.yml`:
```yaml
- cron: '0 13 * * 1'   # min hour day month day-of-week (1 = Monday)
```

### Manual — local cron / Task Scheduler

If you'd rather run on your own machine:

**macOS / Linux (`crontab -e`):**
```
0 8 * * 1 cd /path/to/agent_project && WEBFLOW_API_TOKEN=xxx python3 scripts/weekly_run.py
```

**Windows Task Scheduler:**
- Trigger: Weekly, Monday at 8:00 AM
- Action: `python.exe`
- Arguments: `C:\path\to\agent_project\scripts\weekly_run.py`
- Set environment variable `WEBFLOW_API_TOKEN` in System Properties first

The trade-off: your computer needs to be on at 8am Monday. GitHub Actions doesn't have that limitation.

---

## Common operations

### Generate one report on demand
```bash
python scripts/generate_report.py --start 2026-04-21 --end 2026-04-27
```

### Regenerate the index after editing reports manually
```bash
python scripts/generate_index.py
```

### Backfill a specific range
```bash
python scripts/backfill.py --from 2026-02-01 --to 2026-03-31
```

### Backfill, skipping reports that already exist
```bash
python scripts/backfill.py --from 2026-01-01 --skip-existing
```

---

## What the agent does, step by step

When the GitHub Action fires every Monday:

1. **Checkout** — pulls the current state of the repo
2. **Determine last week** — last Mon to last Sun (`weekly_run.py`)
3. **Fetch activity logs** — paginates the Webflow Data API until it has all events back to last Monday
4. **Render the report** — fills the HTML template, writes `reports/2026-Wnn_*.html`
5. **Rebuild index.html** — scans `reports/`, extracts stats, generates the dashboard
6. **Commit & push** — `git add reports/ index.html && git commit && git push`

If anything goes wrong, the Action shows up red in your GitHub Actions tab and (if you've configured email notifications) you'll get an email.

---

## Troubleshooting

**"WEBFLOW_API_TOKEN environment variable not set"**
You skipped step 3, or you're running locally without exporting the variable.

**API returns 401 Unauthorized**
Token is wrong, expired, or doesn't have `activity:read` scope. Generate a new one.

**API returns 403 Forbidden on activity_logs**
Activity logs require an Enterprise plan. You confirmed this works for SurePayroll already.

**Action runs but no commit appears**
The workflow only commits if there are changes. If the report was already generated for that week, nothing happens — that's intentional.

**A report shows zero events**
That week genuinely had no activity. The empty states in the HTML handle this gracefully ("A quiet week", etc.).

---

## Customization ideas

- **Email digest** — add a step in the workflow that emails the report each Monday
- **Slack notification** — post a summary to a Slack channel
- **More sites** — pass `--site-id` to generate reports for additional Webflow sites
- **Different cadence** — daily, biweekly, or monthly by changing `weekly_run.py` and the cron line

The template (`scripts/report_template.html`) is where the visual design lives. Changes there flow through to all future reports.
