# Sales Navigator Search Exporter

Exports LinkedIn Sales Navigator search results to `results.csv` using
your own logged-in session. Conservative by design.

## Requirements

- Python 3.9+ installed (https://www.python.org/downloads/)
- Google Chrome installed (https://www.google.com/chrome/) — the tool
  uses your real Chrome binary, not bundled Chromium, for a more
  consistent fingerprint.

## Setup (one-time)

**Mac / Linux**

```bash
chmod +x setup.sh run.sh
./setup.sh
```

**Windows**

```
setup.bat
```

This creates a local virtual environment and registers Google Chrome
with Playwright. If Chrome is already installed, no download happens.
Nothing is installed system-wide beyond the venv.

## First run — log in once

**Mac / Linux**

```bash
./run.sh "https://www.linkedin.com/sales/search/people?query=..."
```

**Windows**

```
run.bat "https://www.linkedin.com/sales/search/people?query=..."
```

A browser window opens. On the first run, log into LinkedIn Sales
Navigator manually in that window, then press Enter in the terminal.
The session is stored in `./chrome-profile/` and reused next time.

## Each subsequent run

Same command with a different search URL. The tool will:

1. Open the browser using your saved session
2. Navigate to the search URL
3. Scroll, read results, paginate up to **4 pages / 100 results**
4. Append rows to `results.csv`

## Output columns

`name, title, company, description, profile_url, scraped_at, source_url`

## Safety guardrails (do not disable)

- **1 run per calendar day** (tracked in `.scrape-state.json`)
- **Max 4 pages / 100 results per run**
- Randomized delays: 3–8s between actions, 30–90s between pages
- Read-only: no JavaScript injection, no DOM manipulation
- Dedicated browser profile (won't conflict with your real Chrome)

## Important

Automated extraction from LinkedIn is against their User Agreement
regardless of how human-like the automation is. Use at your own
account risk. Keep volumes low and don't share the profile directory.

## Files

- `scrape.py` — the tool
- `setup.sh` / `setup.bat` — one-time setup
- `run.sh` / `run.bat` — daily use
- `chrome-profile/` — your logged-in browser session (don't share)
- `results.csv` — your exported data (appended to)
- `.scrape-state.json` — daily run counter
