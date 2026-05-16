Fetch recent LinkedIn posts for leads and add them as buying-intent signals. Uses Vayne's profile_posts API.

User input: $ARGUMENTS

## When to use

Run after `/scrape` (and optionally after an initial `/score`) to add post content before final scoring.

Most valuable for **borderline leads** (score 40–70) where post activity can tip the decision. Someone posting about "scaling ops" or "AI automation" is a much warmer lead than their title alone suggests.

## Arguments

| Flag | Default | Description |
|---|---|---|
| `--input PATH` | `data/scored_leads.csv` (falls back to `data/raw_leads.csv`) | Input CSV |
| `--output PATH` | `data/post_enriched_leads.csv` | Output CSV |
| `--min-score N` | none | Only process leads with max ICP score ≥ N |
| `--max-score N` | none | Only process leads with max ICP score ≤ N |
| `--post-limit N` | 10 | Posts per lead (1–20) |
| `--time-limit` | `month` | Post window: `1h`, `24h`, `week`, `month` |
| `--no-estimate` | off | Skip credit estimation |

## Instructions

1. Parse the arguments from user input.

2. Briefly explain what will happen: input file, lead count estimate, cost model (1 credit per post reactor, unused refunded), time estimate (~2–3 min per 10 leads).

3. Run using the Python command from CLAUDE.md (no detection needed — use it directly):
   ```
   PYTHONIOENCODING=utf-8 <PYTHON> pipeline/post_enrich.py [flags]
   ```

   Common patterns:
   ```
   # Borderline leads only (saves credits — most common)
   PYTHONIOENCODING=utf-8 <PYTHON> pipeline/post_enrich.py --min-score 40 --max-score 70

   # All leads before scoring
   PYTHONIOENCODING=utf-8 <PYTHON> pipeline/post_enrich.py --input data/raw_leads.csv --output data/post_enriched_leads.csv

   # Top leads, quick window
   PYTHONIOENCODING=utf-8 <PYTHON> pipeline/post_enrich.py --min-score 70 --post-limit 5 --time-limit week
   ```

4. Report results: how many leads enriched, output file path.

5. Suggest next step: `/score --input data/post_enriched_leads.csv`
