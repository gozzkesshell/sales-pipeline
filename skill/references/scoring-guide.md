# Scoring Guide

This is how you score leads in the `/score` step. Do this yourself — no script needed.

## Setup

1. **Read all PDFs** from `icp/` — each is an ICP definition. ICP name = filename without extension (e.g. `AI.pdf` → ICP `AI`).
2. **Read the input CSV** (default: `data/raw_leads.csv`, or `data/post_enriched_leads.csv` if it exists and is newer).

## CSV columns to use

| Column | Weight | Notes |
|---|---|---|
| `job title` | Heaviest | Current role — primary match signal |
| `summary` | High | LinkedIn About/bio section |
| `headline` | High | LinkedIn headline |
| `job description` | High | Current role description |
| `skills` | Medium | Comma-separated skills list |
| `company` | Context | Company name |
| `linkedin company employee count` | High | Numeric headcount — use for size check |
| `linkedin industry` | High | Industry |
| `location` | Medium | Person's location |
| `linkedin description` | Medium | Company about section |
| `linkedin specialities` | Medium | Company specialties |
| `premium member` | Low | Boolean |
| `number of connections` | Low | Connection count |
| `job title (2)`, `company (2)` etc. | Low | Career history (same pattern for 3, 4) |
| `recent_posts` | Strong (if present) | Added by post-enrich step |

## Scoring each lead

Score 0–100 per ICP. These signals combine into a holistic judgment:

### Title match (heaviest — can move score 30+ points)
- Core buyer title from the ICP (e.g. VP Ops, COO, Head of Customer Success) → high score
- Adjacent buyer title → moderate
- Wrong persona entirely → low score regardless of other signals

### Company size (high weight — ±15 points)
- In the ICP's ideal range → strong positive
- In acceptable range → moderate positive
- Outside both → meaningful negative

### Industry (high weight — ±12 points)
- ICP's primary industry → strong positive
- Secondary industry → moderate
- No match → weak negative

### Location (medium weight — ±8 points)
- Primary geography → positive
- Secondary → slight positive
- Not listed → slight negative

### Keywords (medium weight — ±10 points)
Scan `summary`, `headline`, `job description`, `skills`, `linkedin description` for ICP-relevant terms.
- Many matches across fields → boost
- Zero keyword signals → slight negative

### Recent posts (strong when present — ±15 points)
Each post formatted as `[YYYY-MM-DD | 👍N 💬N] content`.
- Posts about automation, AI tools, ops scaling, workflow pain, process improvement → strong boost (+10–15)
- Posts about team building / hiring in relevant area → moderate boost (+5–8)
- Active posting in last 30 days → slight positive (+3)
- High engagement on relevant posts → slight boost (+2)
- Unrelated topics → neutral
- Empty field → no signal, don't penalise
Always quote the most relevant snippet in the comment when this fires.

### Minor signals (±5 points total)
- `premium member` = true → +2
- 500+ connections → +2
- Career progression toward target role → +1–3

## Output format

Process in batches of 20. Write results incrementally to `data/scored_leads.csv`.

Add two columns per ICP to the CSV:
- `score_<icp_name>` — integer 0–100
- `comment_<icp_name>` — max 500 chars explaining the score

**Comment examples:**
- `"82: VP of Customer Success at 450-person SaaS (US). Core buyer title, ideal company size, primary industry. Summary mentions automation and scaling ops team."`
- `"28: Software Engineer at VC firm (11–50 employees). Wrong title, company too small, no relevant keywords."`
- `"67: Head of Operations at 800-person HealthTech (UK). Title and size match. Recent post: 'drowning in manual processes, evaluating automation tools' — strong buying signal."`

## After scoring

Print a summary per ICP:
- Score distribution: 80+, 60–79, 40–59, <40
- Top 5 leads by name + score

Suggest next steps:
- If there are many 40–70 leads: offer post-enrich to refine them
- Otherwise: suggest segment
