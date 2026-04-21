Fetch recent LinkedIn posts for leads and add them to the CSV as buying-intent signals. Uses Vayne's profile_posts API.

User input: $ARGUMENTS

## When to use

Run this **after `/scrape`** (and optionally after an initial `/score`) to add post content before final scoring.

Most valuable for **borderline leads** (e.g. score 40–70) where post activity can tip the decision either way. Someone actively posting about "scaling ops" or "AI automation" is a much warmer lead than their title alone suggests.

## Arguments

| Flag | Default | Description |
|---|---|---|
| `--input PATH` | `data/scored_leads.csv` (falls back to `data/raw_leads.csv`) | Input CSV |
| `--output PATH` | `data/post_enriched_leads.csv` | Output CSV |
| `--min-score N` | none | Only process leads with max ICP score ≥ N |
| `--max-score N` | none | Only process leads with max ICP score ≤ N |
| `--post-limit N` | 10 | Posts per lead (1–20) |
| `--time-limit` | `month` | Post window: `1h`, `24h`, `week`, `month` |
| `--no-estimate` | off | Skip credit estimation (faster, less transparent) |

## Instructions

1. Parse the arguments from user input.

2. Before running, explain to the user:
   - What input file will be used
   - How many leads will be processed (based on filters)
   - That cost is **1 credit per person who reacted** to each post (variable, unused credits are refunded)
   - Rough time estimate: ~2–3 min per 10 leads (jobs are async and polled in parallel)

3. **Recommended usage patterns:**

   - "Run post-enrich on borderline leads only":
     ```
     python pipeline/post_enrich.py --min-score 40 --max-score 70
     ```

   - "Run on all leads before scoring":
     ```
     python pipeline/post_enrich.py --input data/raw_leads.csv --output data/post_enriched_leads.csv
     ```

   - "Run on top leads only (high confidence check)":
     ```
     python pipeline/post_enrich.py --min-score 70 --post-limit 5 --time-limit week
     ```

4. Run the chosen command and wait for completion.

5. The script will:
   - For each lead: estimate credits → create a `profile_posts` job → poll until done → extract post content
   - Jobs run in parallel polling (all created first, then polled together)
   - Add a `recent_posts` column: concatenated posts formatted as `[YYYY-MM-DD | 👍N 💬N] post content || [next post]…`
   - All leads without post data get an empty `recent_posts` field

6. Report results:
   - How many leads were enriched with post data
   - Output file location
   - Suggest next step: run `/score --input data/post_enriched_leads.csv`

## What the `recent_posts` column looks like

```
[2024-03-15 | 👍45 💬12] We just hit 1M support tickets processed this year — 
and honestly, our team is drowning. Looking at AI tools to help triage... || 
[2024-03-08 | 👍23 💬5] Automation isn't about replacing people, it's about 
giving them better tools. Here's what we did at Acme to cut ops overhead by 40%…
```

## Scoring impact

After post-enrichment, run `/score` pointing at `data/post_enriched_leads.csv`. The scoring skill will automatically use `recent_posts` as a strong signal:
- Posts about automation, AI, ops scaling, process improvement → boost score
- Posts about unrelated topics → neutral
- No posts / empty field → no signal (score conservatively)
