Scrape leads from a LinkedIn Sales Navigator search URL using the Vayne API.

User input: $ARGUMENTS

## Instructions

1. Parse the user input. Expected: `<sales_navigator_url> [--limit N] [--name NAME]`
   - If no URL is provided, ask for it.
   - `--limit` is optional (max leads to scrape, 0 = all).
   - `--name` is optional (unique order name).

2. Run the scraping script using the Python command from CLAUDE.md (no detection needed — use it directly):
   ```
   PYTHONIOENCODING=utf-8 <PYTHON> pipeline/scrape.py "<url>" [--limit N] [--name NAME]
   ```

3. The script validates the URL, creates Vayne orders, polls until complete, deduplicates, and writes `data/raw_leads.csv`.

4. Report results: how many unique leads were scraped and where the file is saved.

If the script fails, read the error message and help the user fix it. Common issues:
- **VAYNE_API_TOKEN not set** → guide user to create `.env` from `.env.example`
- **Order name already exists** → add `--name` with a unique value
- **Duplicate results warning** → Vayne plan is returning the same page for each order; user needs to upgrade plan or use a different search URL
