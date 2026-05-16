# Sales Pipeline — Claude Code context

## Python

Detect the correct Python command for this machine:

- **Mac / Linux:** use `python3`
- **Windows (standard install):** use `python`
- **Windows + Claude Code (Codex runtime):** check if this path exists first:
  `/c/Users/<username>/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`
  If it exists, use it. Otherwise fall back to `python`.

Always set `PYTHONIOENCODING=utf-8` to avoid encoding errors on Windows.

Run a one-liner to confirm which command works before the first script run:
```bash
PYTHONIOENCODING=utf-8 python3 -c "print('ok')" 2>/dev/null || \
PYTHONIOENCODING=utf-8 python -c "print('ok')"
```

Do **not** spend time searching for Python beyond the above check.

## Running pipeline scripts

Replace `<PYTHON>` with whichever command works above.

```bash
# Scrape
PYTHONIOENCODING=utf-8 <PYTHON> pipeline/scrape.py "<url>" [--limit N] [--name NAME]

# Post-enrich
PYTHONIOENCODING=utf-8 <PYTHON> pipeline/post_enrich.py [--min-score N] [--max-score N]

# Segment
PYTHONIOENCODING=utf-8 <PYTHON> pipeline/segment.py [--threshold N]
```

Scoring is done by Claude directly (read ICP PDFs from icp/, score leads in data/raw_leads.csv or data/post_enriched_leads.csv, write data/scored_leads.csv).

## Project layout

```
pipeline/
  scrape.py        — Vayne API scraping (multi-order, parallel)
  post_enrich.py   — LinkedIn post scraping via Vayne
  segment.py       — Filter scored leads into per-ICP CSVs
  config.py        — Loads .env (VAYNE_API_TOKEN, SCORE_THRESHOLD=60)
icp/               — ICP PDF definitions (one file = one ICP)
data/
  raw_leads.csv          — output of scrape
  post_enriched_leads.csv — output of post_enrich
  scored_leads.csv       — output of scoring (score_<icp>, comment_<icp> columns)
  segments/<icp>.csv     — output of segment
.env               — VAYNE_API_TOKEN, SCORE_THRESHOLD
```

## Do not

- Do not read pipeline scripts before running them — the commands above are sufficient
- Do not use PowerShell for running scripts — use Bash
- Do not prompt for Python path confirmation if the one-liner above already confirmed it
