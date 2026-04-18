# Sales AI Automation Pipeline

An AI-powered lead generation pipeline that scrapes LinkedIn Sales Navigator via the [Vayne API](https://vayne.io), scores leads against your ICP definitions using Claude Code, and produces segmented CSVs ready for import into Linked Helper.

---

## How it works

```
Sales Navigator URL
        │
        ▼
  1. /scrape          Vayne API creates an order, polls until done,
                      downloads the advanced CSV → data/raw_leads.csv

        │  (optional)
        ▼
  2. /post-enrich     Fetches last N LinkedIn posts per lead via Vayne
                      Adds a `recent_posts` column → data/post_enriched_leads.csv

        │
        ▼
  3. /score           Claude Code reads your ICP PDFs from icp/
                      Scores every lead 0–100 with a short comment
                      → data/scored_leads.csv

        │
        ▼
  4. /segment         Filters leads above the score threshold
                      Creates one CSV per ICP → data/segments/<icp>.csv

        │
        ▼
  5. Import CSVs into Linked Helper and launch campaigns
```

Each step can be run individually or you can run the full pipeline with one command: `/sales-pipeline`.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Claude Code** | Install from [claude.ai/code](https://claude.ai/code) |
| **Python 3.11+** | [python.org](https://python.org) — must be on PATH |
| **Vayne API token** | Get from [vayne.io](https://vayne.io) → Dashboard → API Settings |
| **LinkedIn Sales Navigator** | Active subscription required |

---

## Installation

### 1. Clone the repository

**Windows (Command Prompt or PowerShell):**
```bat
git clone https://github.com/gozzkesshell/sales-clause-skill.git
cd sales-clause-skill
```

**Mac / Linux:**
```bash
git clone https://github.com/gozzkesshell/sales-clause-skill.git
cd sales-clause-skill
```

---

### 2. Install Python dependencies

**Windows:**
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Mac / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 3. Configure your API token

Copy the example env file and fill in your Vayne token:

**Windows:**
```bat
copy .env.example .env
notepad .env
```

**Mac / Linux:**
```bash
cp .env.example .env
nano .env
```

Edit `.env`:
```env
VAYNE_API_TOKEN=your_vayne_api_token_here
SCORE_THRESHOLD=60
```

- `VAYNE_API_TOKEN` — found in your Vayne dashboard under **API Settings**
- `SCORE_THRESHOLD` — minimum ICP fit score (0–100) to qualify a lead. Default is `60`

---

### 4. Add your ICP definitions

Place PDF files describing your Ideal Customer Profiles in the `icp/` folder. Each PDF becomes a scoring dimension.

```
icp/
  AI.pdf          → scored as "AI" ICP
  SaaS-Ops.pdf    → scored as "SaaS-Ops" ICP
```

The PDF should describe:
- Target job titles and seniority
- Ideal company size (employee count)
- Target industries
- Target locations
- Keywords that signal a good fit
- Any disqualifying signals

You can have **multiple ICPs** — each lead gets scored against all of them independently.

---

### 5. Open the project in Claude Code

**Windows:**
```bat
claude
```

**Mac / Linux:**
```bash
claude
```

Make sure you open Claude Code **from inside the project directory** so it picks up the `.claude/commands/` folder and the slash commands become available.

> **Tip:** On first launch, type `/` to see all available commands for this project.

---

## Usage

### Run the full pipeline

```
/sales-pipeline <sales_navigator_url>
```

With options:
```
/sales-pipeline <url> --limit 100 --name my-search --threshold 65
```

| Flag | Default | Description |
|---|---|---|
| `--limit N` | all | Max leads to scrape |
| `--name NAME` | auto-generated | Vayne order name (must be unique) |
| `--threshold N` | 60 (from .env) | Min score to qualify a lead |

Claude will walk you through each step, ask for confirmation before credit-heavy operations, and show a summary at the end.

---

### Run steps individually

#### `/scrape` — Collect leads from Sales Navigator

```
/scrape <sales_navigator_url>
/scrape <url> --limit 50
/scrape <url> --limit 100 --name "Q2-SaaS-search"
```

- Validates the URL with Vayne before creating an order
- Polls until scraping completes (shows live progress)
- Downloads the **advanced** CSV export to `data/raw_leads.csv`
- The advanced export already includes: full bio (`summary`), headline, job descriptions, company size, industry, skills, education, certifications

---

#### `/score` — Score leads against your ICPs

```
/score
/score --input data/raw_leads.csv
```

Claude Code reads every PDF in `icp/` and scores each lead 0–100 based on:

| Signal | Weight |
|---|---|
| Job title match vs ICP target personas | Heaviest |
| Company size vs ICP ideal range | High |
| Industry match | High |
| Location match | Medium |
| Keywords in bio, headline, skills | Medium |
| Recent posts content *(if post-enriched)* | Medium–High |
| Premium member, connections, career trajectory | Low |

Each lead gets:
- `score_<icp_name>` — integer 0–100
- `comment_<icp_name>` — up to 500-character explanation of why that score was assigned

Output: `data/scored_leads.csv`

---

#### `/post-enrich` — Add LinkedIn post content *(optional)*

Fetches the last N posts from each lead's LinkedIn profile and adds them as a `recent_posts` column. This is the strongest buying-intent signal available — someone actively posting about automation, AI tools, or operational scaling is a much warmer lead.

```
/post-enrich
```

Common patterns:

```
# Best use: borderline leads only (saves credits)
/post-enrich --min-score 40 --max-score 70

# Before any scoring (run on all leads)
/post-enrich --input data/raw_leads.csv --output data/post_enriched_leads.csv

# Last week only, top leads
/post-enrich --min-score 70 --post-limit 5 --time-limit week
```

| Flag | Default | Description |
|---|---|---|
| `--input PATH` | `data/scored_leads.csv` | Input CSV |
| `--output PATH` | `data/post_enriched_leads.csv` | Output CSV |
| `--min-score N` | none | Only process leads with ICP score ≥ N |
| `--max-score N` | none | Only process leads with ICP score ≤ N |
| `--post-limit N` | 10 | Posts per lead (max 20) |
| `--time-limit` | `month` | Post window: `1h` / `24h` / `week` / `month` |

**Cost:** 1 Vayne credit per person who reacted to each post. Unused credits are refunded automatically. The script estimates costs before creating jobs so you can confirm.

After post-enrichment, re-run scoring on the enriched file:
```
/score --input data/post_enriched_leads.csv
```

---

#### `/segment` — Create per-ICP CSVs

```
/segment
/segment --threshold 70
```

Reads `data/scored_leads.csv`, filters leads that meet the score threshold, and writes one CSV per ICP:

```
data/segments/
  AI.csv          ← leads that scored ≥ 60 on the AI ICP
  SaaS-Ops.csv    ← leads that scored ≥ 60 on the SaaS-Ops ICP
```

These files are ready to import directly into **Linked Helper** to launch campaigns.

---

#### `/enrich` — Add extra LinkedIn profile signals *(optional)*

Fetches `followerCount`, `openToWork`, and `hiring` badge for each lead via Vayne's batch profile scraping. **Usually not needed** — the Vayne advanced export already contains all key fields for scoring.

```
/enrich
```

**Cost:** 18 Vayne credits per profile.

---

## Recommended workflow

### Standard run
```
/scrape <url> --limit 100
/score
/segment
```

### With post enrichment for borderline leads
```
/scrape <url> --limit 100
/score
/post-enrich --min-score 40 --max-score 70
/score --input data/post_enriched_leads.csv
/segment
```

### Full pipeline in one command
```
/sales-pipeline <url> --limit 100
```

---

## Project structure

```
.
├── .claude/
│   └── commands/           ← Claude Code slash commands
│       ├── sales-pipeline.md
│       ├── scrape.md
│       ├── score.md
│       ├── post-enrich.md
│       ├── segment.md
│       └── enrich.md
├── pipeline/               ← Python scripts (called by the skills)
│   ├── config.py           ← Loads .env, shared settings
│   ├── scrape.py           ← Vayne order creation + CSV download
│   ├── enrich.py           ← Batch LinkedIn profile scraping
│   ├── post_enrich.py      ← LinkedIn post scraping
│   └── segment.py          ← Score filtering + per-ICP CSVs
├── icp/                    ← Your ICP PDF definitions (add yours here)
│   └── AI.pdf
├── data/                   ← Generated CSVs (gitignored)
│   ├── raw_leads.csv
│   ├── scored_leads.csv
│   ├── post_enriched_leads.csv
│   └── segments/
│       └── <icp_name>.csv
├── .env                    ← Your secrets (gitignored)
├── .env.example            ← Template
└── requirements.txt
```

---

## Vayne API credit costs

| Operation | Cost |
|---|---|
| Sales Navigator scraping | Depends on your Vayne plan |
| Profile enrichment (`/enrich`) | 18 credits per profile |
| Post scraping (`/post-enrich`) | 1 credit per post reactor (variable, unused refunded) |
| URL validation | Free |
| Credit estimation | Free |

Check your remaining credits anytime in the [Vayne dashboard](https://vayne.io).

---

## Troubleshooting

**`VAYNE_API_TOKEN not set`**
→ Make sure you created `.env` from `.env.example` and added your token. Claude Code must be launched from the project root directory.

**`Order name already exists` (409 error)**
→ Each Vayne order needs a unique name. Use `--name` to specify one, or the script auto-generates a timestamped name on retry.

**Scoring produces empty CSV**
→ Check that `icp/` contains at least one PDF and that `data/raw_leads.csv` exists (run `/scrape` first).

**Post-enrich jobs time out**
→ Vayne post scraping can take several minutes per profile. Try reducing `--post-limit` or using `--time-limit week` instead of `month`.

**`linkedin url` column not found during enrichment**
→ The column name varies by Vayne export format. Open your CSV and check the actual column name — the script searches for common variants automatically.

---

## License

MIT
