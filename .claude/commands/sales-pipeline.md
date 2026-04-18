Run the full Sales AI Automation Pipeline end-to-end.

User input: $ARGUMENTS

## Pipeline Steps

1. **Scrape** — Collect leads from Sales Navigator via Vayne API → `data/raw_leads.csv`
2. **Score** — Score each lead on ICP fit with a short comment (done by Claude Code) → `data/scored_leads.csv`
3. **Post-enrich** *(optional)* — Fetch recent LinkedIn posts for borderline leads → `data/post_enriched_leads.csv`
4. **Re-score** *(if post-enriched)* — Re-run scoring on enriched file using post content as signal
5. **Segment** — Filter high-scoring leads into per-ICP CSVs → `data/segments/<icp>.csv`

> **Optional steps:** `/enrich` adds followerCount/openToWork/hiring. `/post-enrich` adds recent post content (strongest buying-intent signal). Both can be skipped — the Vayne advanced export already contains all core fields for scoring.

## Instructions

### Parse arguments
Expected: `<sales_navigator_url> [--limit N] [--name NAME] [--threshold SCORE]`
- URL is required. If not provided, ask for it.
- `--limit` — max leads to scrape (optional, 0 = all)
- `--name` — Vayne order name (optional, must be unique)
- `--threshold` — min ICP fit score to qualify leads (optional, default from .env or 60)

---

### Step 1: Scrape

Run:
```
cd /c/Users/gozzk/projects/innotechfy/ai-automation && python pipeline/scrape.py "<url>" [--limit N] [--name NAME]
```

Wait for completion. Report how many leads were scraped and confirm `data/raw_leads.csv` was created.

---

### Step 2: Score

Performed by Claude Code directly (no Python script):

1. Read all PDF files from `icp/` — each is an ICP definition. ICP name = filename without extension.
2. Read `data/raw_leads.csv`. Key columns to use:
   - `job title` — current role (heaviest weight for ICP match)
   - `summary` — full LinkedIn About/bio
   - `headline` — LinkedIn headline
   - `job description` — current role description
   - `skills` — skills list
   - `company` — company name
   - `linkedin company employee count` — numeric headcount (use for size check)
   - `linkedin industry` — industry
   - `location` — person's location
   - `linkedin description`, `linkedin specialities` — company context
   - `premium member`, `number of connections` — minor signals
   - `job title (2)`, `job description (2)`, `company (2)` (and 3, 4) — career history
3. Score each lead 0–100 per ICP — holistic fit judgment:
   - Title match vs ICP target personas (heaviest weight)
   - Company size vs ICP ideal/acceptable range
   - Industry vs ICP primary/secondary industries
   - Location vs ICP primary/secondary geographies
   - Keyword signals in summary, headline, description, skills
   - Minor: premium member, connections, career trajectory
4. Write a short comment per lead per ICP (max 500 chars) naming the specific signals.
5. Process in batches of 20. Write results to `data/scored_leads.csv` incrementally.
   Output columns: all original columns + `score_<icp_name>` + `comment_<icp_name>` per ICP.

---

### Step 3: Segment

Run:
```
cd /c/Users/gozzk/projects/innotechfy/ai-automation && python pipeline/segment.py [--threshold N]
```

Creates `data/segments/<icp_name>.csv` for each ICP with qualifying leads.

---

### Final Report

After all steps:
- Total leads scraped
- Score distribution per ICP (80+, 60–79, 40–59, <40)
- Qualified leads per ICP (above threshold)
- File paths for each per-ICP CSV (ready for Linked Helper import)
