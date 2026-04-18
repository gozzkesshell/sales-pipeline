Score leads on how closely they match each ICP. Performed by Claude Code directly — no external API needed.

User input: $ARGUMENTS

## Input CSV columns (Vayne advanced export)

The CSV already contains everything needed for scoring. Key columns:
- `first name`, `last name`, `linkedin url`, `location`
- `job title` — current role
- `job description` — current role description
- `summary` — full LinkedIn About/bio section
- `headline` — LinkedIn headline
- `skills` — comma-separated skills list
- `company` — current company name
- `linkedin company employee count` — numeric headcount (use this for size)
- `linkedin employees` — size range (fallback)
- `linkedin industry` — industry
- `linkedin description` — company about
- `linkedin specialities` — company specialties
- `corporate website` — company website
- `premium member` — boolean
- `number of connections` — connections count
- `job title (2)`, `job description (2)`, `company (2)` — previous role #2 (same pattern for 3, 4)
- `recent_posts` *(optional, added by `/post-enrich`)* — concatenated recent LinkedIn posts with engagement stats

## Instructions

1. Read all ICP PDF files from the `icp/` directory.
   - Extract the ICP name from the filename (e.g. `AI.pdf` → ICP name `AI`).

2. Read the leads CSV. Default: `data/raw_leads.csv`.
   - If user passes `--input PATH`, use that path instead.

3. For each lead, score 0–100 against EACH ICP — a holistic judgment of how well they match.
   Use these signals (in rough order of importance):

   **Title match** (heaviest weight)
   Use `job title`. Does it match one of the ICP's target personas?
   - Core buyer (Head/VP/Director of Ops, COO, Head of Customer Success/Support, etc.) → high score
   - Adjacent buyer (CTO, VP Product, Head of Digital Transformation, etc.) → moderate
   - Not a target persona → low score regardless of other signals

   **Company size**
   Use `linkedin company employee count` (numeric). Compare to ICP's ideal/acceptable ranges.
   - In ideal range → strong positive
   - In acceptable range → moderate
   - Outside both → negative signal

   **Industry**
   Use `linkedin industry`. Compare to ICP's primary and secondary industries.
   - Primary industry match → strong positive
   - Secondary match → moderate
   - No match → weak signal

   **Location**
   Use `location`. Compare to ICP's primary/secondary/additional geographies.
   - Primary geography → strong positive
   - Secondary → moderate
   - Not listed → weak negative

   **Keyword signals**
   Scan `summary`, `headline`, `job description`, `job title`, `skills`, `linkedin description`.
   Look for ICP-relevant keywords (operations, automation, workflow, scaling, process, data-driven, etc.)
   - Many keyword matches across fields → boost
   - Zero keyword signals → slight negative

   **Recent posts** *(strong signal — use when `recent_posts` column is present and non-empty)*
   Read the `recent_posts` field. Each post is formatted as `[YYYY-MM-DD | 👍N 💬N] content`.
   - Posts explicitly about automation, AI tools, ops scaling, workflow, process pain → strong boost (+10–15)
   - Posts about team building / hiring in ops/support → moderate boost (+5–8)
   - Posts showing active LinkedIn presence in last 30 days → slight positive (+3)
   - High engagement (many likes/comments) on relevant posts → slight boost (+3)
   - Posts about unrelated topics (e.g. personal life, unrelated industry) → neutral
   - Empty `recent_posts` → no signal, do not penalise
   Always quote the most relevant post snippet in the comment when this signal fires.

   **Growth/activity signals** (minor)
   - `premium member` = true → slight positive
   - High `number of connections` (500+) → slight positive
   - Previous roles show career progression in target area → slight positive

4. Also write a short comment per lead per ICP (max 500 characters) explaining the score.
   Be specific — name which signals matched or didn't. Examples:
   - "82: VP of Customer Success at 450-person SaaS in US. Core buyer title, ideal company size, primary industry. Summary mentions automation and scaling ops team."
   - "28: Software Engineer at VC firm (11-50 employees). Wrong title, wrong company size, no relevant keywords."

5. Process in batches of 20 leads. Write results incrementally to avoid losing work.

6. Output CSV: `data/scored_leads.csv`
   All original columns PLUS for each ICP:
   - `score_<icp_name>` (integer 0–100)
   - `comment_<icp_name>` (string, max 500 chars)

7. After all leads are scored, print a summary:
   - Total leads scored
   - Per ICP: score distribution (80+, 60–79, 40–59, <40), top 5 leads by name + score

## Notes
- Default threshold for "qualified" is 60 (used later by `/segment`).
- If a field is empty, score that signal conservatively and note it in the comment.
- Write CSV with proper quoting (fields containing commas or newlines must be quoted).
