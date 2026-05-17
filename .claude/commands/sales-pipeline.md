Run the full Sales AI Automation Pipeline end-to-end.

User input: $ARGUMENTS

## Pipeline Steps

1. **Scrape** — Collect leads from Sales Navigator via Vayne API → `data/raw_leads.csv`
2. **Score** — Score each lead on ICP fit (done by Claude directly) → `data/scored_leads.csv`
3. **Post-enrich** *(optional)* — Fetch recent LinkedIn posts for borderline leads → `data/post_enriched_leads.csv`
4. **Re-score** *(if post-enriched)* — Re-run scoring on enriched file using post content as signal
5. **Segment** — Filter high-scoring leads into per-ICP CSVs → `data/segments/<icp>.csv`

---

## Instructions

### 0. Pre-flight check

Use the Read tool to check if `.env` exists. If it doesn't exist:
1. Tell the user their Vayne API token is needed
2. Ask them to paste their token
3. Create `.env` from `.env.example` with their token filled in
4. Continue — do NOT stop here if the token is provided

### Parse arguments
Expected: `<sales_navigator_url> [--limit N] [--name NAME] [--threshold SCORE]`
- URL is required. If not provided, ask for it.
- `--limit` — max leads to scrape (optional, 0 = all)
- `--name` — Vayne order name (optional, must be unique)
- `--threshold` — min ICP fit score to qualify leads (optional, default from .env or 60)

---

### Step 1: Scrape

Run using the Python command from CLAUDE.md (no detection needed — use it directly):
```
PYTHONIOENCODING=utf-8 <PYTHON> pipeline/scrape.py "<url>" [--limit N] [--name NAME]
```

Wait for completion. Report how many unique leads were scraped and confirm `data/raw_leads.csv` was created.

---

### Step 2: Score

Performed by Claude directly — no script, no bash commands for extraction.

1. Use the **Read tool** to read all PDF files from `icp/` (ICP name = filename without extension).
2. Use the **Read tool** to read `data/raw_leads.csv`.
3. Score every lead 0–100 per ICP inline — holistic fit judgment using:
   - **Title** (heaviest): does it match ICP target personas?
   - **Company size** (`linkedin company employee count`): ideal / acceptable / outside range?
   - **Industry** (`linkedin industry`): primary / secondary / no match?
   - **Location**: primary / secondary / not listed?
   - **Keywords** in `summary`, `headline`, `job description`, `skills`, `linkedin description`
   - **`recent_posts`** (if non-empty): strong buying-intent signal — quote relevant snippets
   - **Minor**: `premium member`, `number of connections`, career trajectory
4. Write a comment per lead per ICP (max 500 chars) naming specific signals.
5. After scoring **all** leads, write `data/scored_leads.csv` in a **single** `python -c` command. Include all original columns plus `score_<icp_name>` and `comment_<icp_name>` per ICP.

---

### Step 3: Segment

Run using the Python command from CLAUDE.md (no detection needed — use it directly):
```
PYTHONIOENCODING=utf-8 <PYTHON> pipeline/segment.py [--threshold N]
```

Creates `data/segments/<icp_name>.csv` for each ICP with qualifying leads.

---

### Final Report

After all steps:
- Total leads scraped
- Score distribution per ICP (80+, 60–79, 40–59, <40)
- Qualified leads per ICP (above threshold)
- File paths for each per-ICP CSV (ready for Linked Helper import)
- If 0 qualified: diagnose why (wrong personas in search? wrong industry? low scores across board?) and suggest specific fixes
