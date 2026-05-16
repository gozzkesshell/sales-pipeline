Score leads on how closely they match each ICP. Performed by Claude directly — no script needed.

User input: $ARGUMENTS

## Instructions

### 1. Read inputs (use the Read tool — do NOT use bash)

- Read all PDF files from `icp/` (one per ICP; ICP name = filename without extension).
- Read the leads CSV:
  - Default: `data/raw_leads.csv`
  - If `--input PATH` was passed, use that path instead
  - If `data/post_enriched_leads.csv` exists and is newer than `data/raw_leads.csv`, prefer it

### 2. Score all leads inline

For each lead, assign a score 0–100 per ICP based on:

| Signal | Weight |
|---|---|
| Job title match vs ICP target personas | Heaviest — can move score ±30 |
| Company size (`linkedin company employee count`) vs ICP ideal/acceptable range | High — ±15 |
| Industry (`linkedin industry`) vs ICP primary/secondary | High — ±12 |
| Location vs ICP geographies | Medium — ±8 |
| Keywords in `summary`, `headline`, `job description`, `skills`, `linkedin description` | Medium — ±10 |
| `recent_posts` content (if present) | Strong — ±15 |
| `premium member`, `number of connections`, career progression | Minor — ±5 total |

**Title match rules:**
- Core buyer persona (VP/Head/Director of Ops, COO, Head of CS, CTO, etc.) → high base score
- Adjacent buyer → moderate
- Wrong persona entirely → low score regardless of other signals

**Recent posts rules (when `recent_posts` column is non-empty):**
- Posts about automation, AI, ops scaling, process pain → +10–15
- Posts about hiring/team building in target area → +5–8
- Active posting in last 30 days → +3
- Unrelated topics → neutral; empty → no penalty
- Always quote the most relevant snippet in the comment when this fires

### 3. Write a comment per lead per ICP (max 500 chars)

Name the specific signals. Examples:
- `"82: VP of Customer Success at 450-person SaaS (US). Core buyer, ideal size, primary industry. Summary mentions automation and scaling ops."`
- `"28: Software Engineer at VC firm (11-50 emp). Wrong title, wrong size, no relevant keywords."`

### 4. Write the scored CSV — one shot at the end

After scoring **all** leads:
- Write `data/scored_leads.csv` in a **single** `python -c` command
- Include all original columns plus `score_<icp_name>` and `comment_<icp_name>` per ICP
- Properly quote fields that contain commas or newlines
- Do NOT create intermediate files, temp scripts, or multiple write passes

### 5. Print summary

After writing the file:
- Total leads scored
- Per ICP: distribution (80+, 60–79, 40–59, <40) and top 5 leads by name + score
- Suggest next step: post-enrich borderline leads (40–70) or run `/segment`
