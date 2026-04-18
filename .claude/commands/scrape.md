Scrape leads from a LinkedIn Sales Navigator search URL using the Vayne API.

User input: $ARGUMENTS

## Instructions

1. Parse the user input. Expected: `<sales_navigator_url> [--limit N] [--name NAME]`
   - If no URL is provided, ask the user for the Sales Navigator search URL.
   - `--limit` is optional (max leads to scrape, 0 or omitted = scrape all).
   - `--name` is optional (unique order name).

2. Run the scraping script from the project root:
   ```
   cd /c/Users/gozzk/projects/innotechfy/ai-automation && python pipeline/scrape.py "<url>" [--limit N] [--name NAME]
   ```

3. The script will:
   - Validate the URL with Vayne API
   - Create a scraping order
   - Poll until complete
   - Download the CSV to `data/raw_leads.csv`

4. Report results to the user: how many leads were scraped and where the file is saved.

If the script fails, read the error and help the user fix it (common issues: missing .env, invalid URL, not enough credits).
