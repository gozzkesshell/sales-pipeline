"""Step 2: Enrich leads by batch-scraping their LinkedIn profiles via Vayne API."""
import argparse
import csv
import sys
import time

import requests

from config import DATA_DIR, VAYNE_BASE_URL, require_vayne_token, vayne_headers

# LinkedIn URL column name candidates (order = priority)
_URL_CANDIDATES = [
    "linkedinUrl", "linkedin_url", "LinkedIn URL", "profile_url",
    "Profile URL", "LinkedIn", "LinkedIn Profile URL",
]


def find_url_column(fieldnames: list[str]) -> str | None:
    for c in _URL_CANDIDATES:
        if c in fieldnames:
            return c
    for f in fieldnames:
        if "linkedin" in f.lower() and "company" not in f.lower():
            return f
    return None


def read_csv(path) -> tuple[list[str], list[dict]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, list(reader)


def submit_batch(urls: list[str], name: str) -> dict:
    resp = requests.post(
        f"{VAYNE_BASE_URL}/api/linkedin_scrapings/batch",
        headers=vayne_headers(),
        json={"urls": urls, "name": name},
    )
    resp.raise_for_status()
    return resp.json()


def poll_batch(batch_id: int, interval: int = 15, timeout: int = 3600) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(
            f"{VAYNE_BASE_URL}/api/linkedin_scrapings/{batch_id}",
            headers=vayne_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        processed = data.get("processed_urls", 0)
        total = data.get("total_urls", "?")
        print(f"  Status: {status} | {processed}/{total} processed")

        if status == "completed":
            return data
        if status == "failed":
            print("Batch scraping failed!")
            sys.exit(1)

        time.sleep(interval)

    print("Timeout waiting for batch scraping.")
    sys.exit(1)


def fetch_all_results(batch_id: int, total: int) -> list[dict]:
    results = []
    per_page = 500
    pages = max(1, (total + per_page - 1) // per_page)
    for page in range(1, pages + 1):
        resp = requests.get(
            f"{VAYNE_BASE_URL}/api/linkedin_scrapings/{batch_id}",
            headers=vayne_headers(),
            params={"page": page, "per_page": per_page},
        )
        resp.raise_for_status()
        results.extend(resp.json().get("results", []))
    return results


def build_enrichment_lookup(results: list[dict]) -> dict:
    """Map normalized LinkedIn URL -> profile data."""
    lookup = {}
    for r in results:
        if r.get("status") != "success" or not r.get("data"):
            continue
        url = r.get("linkedin_url", "").rstrip("/").lower()
        if url:
            lookup[url] = r["data"]
    return lookup


ENRICH_EXTRA_FIELDS = [
    "headline", "about", "location", "connectionsCount", "followerCount",
    "openToWork", "hiring", "premium",
    "current_position", "current_company", "current_description",
    "current_start_date", "company_website",
    "experience_json",
    "education_1", "education_1_degree",
]


def enrich_row(row: dict, profile: dict) -> dict:
    """Merge profile data into a lead row."""
    import json as _json

    for key in ("headline", "about", "location", "connectionsCount",
                "followerCount", "openToWork", "hiring", "premium"):
        row[key] = profile.get(key, "")

    experiences = profile.get("experience", [])
    if experiences:
        first = experiences[0]
        row["current_position"] = first.get("position", "")
        row["current_company"] = first.get("companyName", "")
        row["current_description"] = first.get("description", "")
        row["current_start_date"] = first.get("startDate", "")
        row["company_website"] = first.get("website", "")
    row["experience_json"] = _json.dumps(experiences, ensure_ascii=False)

    education = profile.get("education", [])
    if education:
        row["education_1"] = education[0].get("schoolName", "")
        row["education_1_degree"] = education[0].get("degree", "")

    return row


def main():
    parser = argparse.ArgumentParser(description="Enrich leads with full LinkedIn profile data via Vayne")
    parser.add_argument("--input", default=None, help="Input CSV (default: data/raw_leads.csv)")
    parser.add_argument("--output", default=None, help="Output CSV (default: data/enriched_leads.csv)")
    parser.add_argument("--name", default=None, help="Batch job name")
    args = parser.parse_args()

    require_vayne_token()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    input_path = args.input or str(DATA_DIR / "raw_leads.csv")
    output_path = args.output or str(DATA_DIR / "enriched_leads.csv")

    # Read CSV
    print(f"Reading {input_path}...")
    fieldnames, rows = read_csv(input_path)
    print(f"Found {len(rows)} leads")
    if not rows:
        print("No leads to enrich.")
        sys.exit(0)

    url_col = find_url_column(fieldnames)
    if not url_col:
        print(f"Cannot find LinkedIn URL column. Columns: {fieldnames}")
        sys.exit(1)
    print(f"Using column '{url_col}'")

    # Collect valid LinkedIn profile URLs
    urls = []
    for row in rows:
        u = (row.get(url_col) or "").strip()
        if u and "linkedin.com/in/" in u:
            urls.append(u)
    print(f"Found {len(urls)} valid LinkedIn profile URLs")
    if not urls:
        print("Nothing to scrape.")
        sys.exit(0)

    # Submit batch
    batch_name = args.name or f"enrich-{time.strftime('%Y%m%d-%H%M%S')}"
    print(f"Submitting batch job '{batch_name}' ({len(urls)} profiles)...")
    result = submit_batch(urls, name=batch_name)
    batch_id = result["id"]
    print(f"Batch #{batch_id} created | credits used: {result.get('credits_used', '?')}")

    # Poll
    print("Waiting for batch scraping...")
    data = poll_batch(batch_id)

    # Fetch & merge
    print("Fetching results...")
    results = fetch_all_results(batch_id, data.get("total_urls", len(urls)))
    lookup = build_enrichment_lookup(results)
    print(f"Successfully enriched {len(lookup)} profiles")

    # Merge into rows
    out_fields = fieldnames[:]
    for f in ENRICH_EXTRA_FIELDS:
        if f not in out_fields:
            out_fields.append(f)

    matched = 0
    for row in rows:
        key = (row.get(url_col) or "").rstrip("/").lower()
        profile = lookup.get(key)
        if profile:
            enrich_row(row, profile)
            matched += 1

    # Write
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nEnriched {matched}/{len(rows)} leads -> {output_path}")


if __name__ == "__main__":
    main()
