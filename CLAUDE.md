# Sales Pipeline — Claude Code context

## Python

Always use this exact Python executable — do not search for others:
```
PYTHONIOENCODING=utf-8 /c/Users/gozzk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe
```

Always set `PYTHONIOENCODING=utf-8` to avoid encoding errors on Windows.

Always `cd` into the project root before running pipeline scripts:
```
cd /c/Users/gozzk/projects/innotechfy/ai-automation
```

## Running pipeline scripts

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

- Do not search for Python or read pipeline scripts before running them
- Do not use `python`, `python3`, or `py` — use the full path above
- Do not use PowerShell for running scripts — use Bash
