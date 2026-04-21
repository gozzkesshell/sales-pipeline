Enrich leads with additional LinkedIn profile data via Vayne API batch scraping.

User input: $ARGUMENTS

## When to use this

The Vayne advanced CSV export (`data/raw_leads.csv`) already contains:
summary, headline, job title, job description, company size, industry, skills, connections, etc.

**This step is optional.** It adds only these extra fields not in the advanced export:
- `followerCount`
- `openToWork`
- `hiring` (is the person actively hiring)

Run `/enrich` only if you specifically want those signals. For most scoring runs, skip straight to `/score`.

## Instructions

1. Parse optional arguments: `[--input PATH] [--output PATH]`
   - Default input: `data/raw_leads.csv`
   - Default output: `data/enriched_leads.csv`

2. Verify the input file exists. If not, tell the user to run `/scrape` first.

3. Warn the user: each profile costs **18 Vayne credits**. Show how many profiles will be scraped and the total credit cost. Ask for confirmation before proceeding.

4. Run the enrichment script from the project root:
   ```
   python pipeline/enrich.py [--input PATH] [--output PATH]
   ```

5. The script will:
   - Find the LinkedIn URL column in the CSV
   - Submit a batch scraping job to Vayne API
   - Poll until complete
   - Merge `followerCount`, `openToWork`, `hiring` into the CSV
   - Save to `data/enriched_leads.csv`

6. Report: how many leads were enriched, credits used, output file location.
