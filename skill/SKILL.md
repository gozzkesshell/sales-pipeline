---
name: sales-pipeline
description: >
  AI-powered B2B sales lead pipeline using LinkedIn Sales Navigator + Vayne API.
  Use this skill whenever the user wants to scrape leads, score them against ICPs,
  enrich with LinkedIn post data, or segment into campaign-ready CSVs.
  Trigger on: "scrape leads", "score my leads", "run the pipeline", "segment",
  "post-enrich", "sales navigator", "ICP fit", "vayne", "qualified leads",
  "find leads", "run pipeline", or any mention of LinkedIn lead generation workflow.
  Even if they just say "scrape this URL" or "who are my best leads?" — use this skill.
---

# Sales Pipeline Skill

You are running an AI-powered sales lead generation pipeline. This skill lets users
scrape LinkedIn Sales Navigator leads, score them against ICP definitions, optionally
enrich with recent post data, and segment into per-ICP CSVs ready for outreach.

## Step 1: Find the project directory

Check these locations in order until you find one that contains `pipeline/scrape.py`:

1. Current working directory (`.`)
2. `~/Applications/sales-pipeline` (Mac one-click install default)
3. `~/sales-pipeline`
4. Any path the user mentions

If you can't find the project, tell the user:
> "I can't find the sales pipeline project. Can you tell me where it's installed?"

Once found, store that as **PROJECT_DIR**. All paths below are relative to it.

## Step 2: Detect the Python command

- Mac/Linux: use `PROJECT_DIR/.venv/bin/python`
- Windows: use `PROJECT_DIR/.venv/Scripts/python`
- Fallback: `python3` or `python`

Always `cd` into PROJECT_DIR before running any script.

## Step 3: Understand what the user wants

Parse their message and map it to one of these actions:

| User says | Action |
|---|---|
| "scrape [URL]" / "get leads from [URL]" | → **scrape** |
| "score" / "score my leads" / "score them" | → **score** |
| "post-enrich" / "enrich with posts" / "get recent posts" | → **post-enrich** |
| "segment" / "filter leads" / "export for campaign" | → **segment** |
| "run the pipeline" / "full pipeline" / "do everything" | → **full pipeline** |
| "status" / "what do I have" / "check progress" | → **status** |

If it's ambiguous, ask one short question.

---

## Actions

### Scrape

Requires: a Sales Navigator search URL.

If no URL is in the message, ask: "What's the Sales Navigator search URL?"

Run:
```
cd PROJECT_DIR
PYTHON pipeline/scrape.py "URL" [--limit N] [--name NAME]
```

- `--limit` if the user mentioned a number of leads
- `--name` if the user gave it a name

Tell the user: how many leads were found, that it may take a few minutes, and show progress as it runs.

After completion: report leads scraped, confirm `data/raw_leads.csv` exists, suggest next step (`score my leads`).

---

### Score

Read the ICP definitions and score every lead yourself — this step is done by you (Claude), not a Python script.

**Full scoring instructions are in `references/scoring-guide.md`** — read it before scoring.

Default input: `data/raw_leads.csv`. If `data/post_enriched_leads.csv` exists and is newer, use that instead (or ask the user which to use).

After scoring, write `data/scored_leads.csv` with the score and comment columns added.

---

### Post-Enrich

Requires: leads CSV with LinkedIn URLs. Most useful for borderline leads (score 40–70).

Run:
```
cd PROJECT_DIR
PYTHON pipeline/post_enrich.py [--input PATH] [--min-score N] [--max-score N] [--post-limit N] [--time-limit WINDOW]
```

Before running, tell the user:
- How many leads will be processed
- Cost: ~1 Vayne credit per person who reacted to each post (variable, unused credits refunded)
- Time: roughly 2–3 min per 10 leads

After: report how many leads got post data, suggest re-running score on the enriched file.

---

### Segment

Run:
```
cd PROJECT_DIR
PYTHON pipeline/segment.py [--threshold N]
```

Default threshold: 60 (or whatever is in `.env` as `SCORE_THRESHOLD`).

After: list each `data/segments/<icp>.csv`, how many leads are in each, and remind the user these are ready for Linked Helper import.

---

### Full Pipeline

Walk through all steps in order, pausing for confirmation at the post-enrich step (it costs credits). Steps:

1. Scrape → ask for URL if not provided
2. Score → run immediately after scrape
3. Post-enrich → ask: "Do you want to post-enrich borderline leads (40–70 score)? It costs Vayne credits."
4. Re-score → if post-enriched, re-run scoring on enriched file
5. Segment → filter and export

Print a summary at the end: total leads, score distribution per ICP, qualified leads per ICP, file locations.

---

### Status

Check what files exist and report:

```
data/raw_leads.csv            → N leads (scraped YYYY-MM-DD HH:MM)
data/scored_leads.csv         → N leads scored, M ICPs
data/post_enriched_leads.csv  → N leads enriched
data/segments/                → X.csv (N leads), Y.csv (N leads)
icp/                          → [list of ICP PDFs]
.env                          → token configured: yes/no
```

---

## Error handling

**`VAYNE_API_TOKEN not set`**: Tell the user to open `.env` in the project folder and paste their Vayne token.

**`Order name already exists`**: Add a timestamp suffix to the name and retry.

**Script not found / venv missing**: Tell the user to re-run `install-mac.command` (Mac) or `pip install -r requirements.txt` (manual setup).

**No ICP PDFs in `icp/`**: Tell the user to add at least one PDF to the `icp/` folder describing their ideal customer, then re-run score.

**`data/raw_leads.csv` missing**: Remind them to scrape first.

---

## Tone

Be concise and action-oriented. Show progress as scripts run. After each step, tell the user what happened and suggest the obvious next step. Don't explain the whole pipeline upfront unless they ask — just do what they asked and move forward.
