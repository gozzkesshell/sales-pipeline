# Sales Pipeline — Claude Code context

## Python

- **Mac / Linux:** `python3`
- **Windows with Claude Code (Codex runtime):** use the full path, substituting your Windows username:
  `/c/Users/<username>/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`

Always prepend `PYTHONIOENCODING=utf-8`.

**Do NOT run any detection or verification commands.** Just pick the right command above and run the script directly. If Python is wrong, the script will error clearly.

## Running pipeline scripts

```bash
# Scrape
PYTHONIOENCODING=utf-8 <PYTHON> pipeline/scrape.py "<url>" [--limit N] [--name NAME]

# Post-enrich
PYTHONIOENCODING=utf-8 <PYTHON> pipeline/post_enrich.py [--min-score N] [--max-score N]

# Segment
PYTHONIOENCODING=utf-8 <PYTHON> pipeline/segment.py [--threshold N]
```

## Scoring (done by Claude, no script)

1. Use the **Read tool** to read `icp/*.pdf` and `data/raw_leads.csv` (or `data/post_enriched_leads.csv` if newer).
2. Score all leads **inline** — do NOT use bash to extract fields or reformat data.
3. After scoring all leads, write `data/scored_leads.csv` in a **single** `python -c` command or Write tool call.
4. Do NOT create intermediate files, temp scripts, or multiple write passes.

## Rules — follow strictly

- Do NOT run Python detection or version-check commands
- Do NOT check if `.env` exists before running — scripts report missing config clearly
- Do NOT read pipeline scripts before running them
- Do NOT use PowerShell — use Bash only
- Do NOT use bash to extract/reformat CSV rows for scoring — use the Read tool

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
