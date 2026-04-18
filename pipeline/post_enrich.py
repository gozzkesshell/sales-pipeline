"""Step 2.5 (optional): Fetch recent LinkedIn posts for each lead via Vayne profile_posts API.

Adds a `recent_posts` column to the CSV containing concatenated post content,
engagement stats, and recency — used by /score to detect active buying signals.

Workflow:
  1. Read input CSV, find leads to process (optionally filtered by score range).
  2. For each lead, estimate credits then create a profile_posts scraping job.
  3. Poll all jobs concurrently until complete.
  4. Extract post content, merge into CSV rows.
  5. Write output CSV.
"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path

import requests

from config import DATA_DIR, VAYNE_BASE_URL, require_vayne_token, vayne_headers

# Column name for LinkedIn URL in the Vayne advanced export
_URL_CANDIDATES = [
    "linkedin url", "linkedinUrl", "linkedin_url",
    "LinkedIn URL", "profile_url", "LinkedIn",
]

# How long to wait between creating individual jobs (respect 60 req/min limit)
_CREATE_DELAY_S = 1.2
# Max seconds to wait for all jobs to finish
_POLL_TIMEOUT_S = 1800
_POLL_INTERVAL_S = 15
# Max chars to store per post in the CSV (keeps the column readable)
_POST_CONTENT_MAX = 800
# Separator between posts in the `recent_posts` column
_POST_SEP = " || "


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_url_column(fieldnames: list[str]) -> str | None:
    lower = {f.lower(): f for f in fieldnames}
    for c in _URL_CANDIDATES:
        if c.lower() in lower:
            return lower[c.lower()]
    for f in fieldnames:
        if "linkedin" in f.lower() and "company" not in f.lower():
            return f
    return None


def find_score_columns(fieldnames: list[str]) -> list[str]:
    return [c for c in fieldnames if re.match(r"^score_", c, re.IGNORECASE)]


def max_icp_score(row: dict, score_cols: list[str]) -> float:
    """Return the highest ICP score across all ICPs for this row."""
    best = 0.0
    for col in score_cols:
        try:
            best = max(best, float(row.get(col) or 0))
        except (ValueError, TypeError):
            pass
    return best


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, list(reader)


def safe_name(linkedin_url: str, ts: str) -> str:
    """Build a short unique job name from a LinkedIn URL slug + timestamp."""
    slug = linkedin_url.rstrip("/").split("/")[-1][:30]
    slug = re.sub(r"[^a-zA-Z0-9\-]", "-", slug)
    return f"post-{slug}-{ts}"


# ---------------------------------------------------------------------------
# Vayne API calls
# ---------------------------------------------------------------------------

def estimate_credits(profile_url: str, post_count_limit: int, time_limit: str | None) -> int | None:
    """Call /api/post_scrapers/estimate. Returns estimated_credits or None on failure."""
    payload: dict = {"profile_url": profile_url, "post_count_limit": post_count_limit}
    if time_limit:
        payload["time_limit"] = time_limit
    try:
        resp = requests.post(
            f"{VAYNE_BASE_URL}/api/post_scrapers/estimate",
            headers=vayne_headers(),
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"    estimate: {data.get('post_count', '?')} posts, "
              f"~{data.get('estimated_people', '?')} people, "
              f"{data.get('estimated_credits', '?')} credits")
        return data.get("estimated_credits")
    except Exception as e:
        print(f"    estimate failed ({e}), using default credit reservation")
        return None


def create_job(profile_url: str, name: str, post_count_limit: int,
               time_limit: str | None, estimated_credits: int | None) -> int | None:
    """Create a profile_posts scraping job. Returns job id or None on failure."""
    payload: dict = {
        "scrape_mode": "profile_posts",
        "name": name,
        "profile_url": profile_url,
        "post_count_limit": post_count_limit,
    }
    if time_limit:
        payload["time_limit"] = time_limit
    if estimated_credits is not None:
        payload["estimated_credits"] = estimated_credits
    try:
        resp = requests.post(
            f"{VAYNE_BASE_URL}/api/post_scrapers",
            headers=vayne_headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        job = resp.json().get("post_scraper", resp.json())
        job_id = job.get("id")
        print(f"    job #{job_id} created (status: {job.get('status')})")
        return job_id
    except requests.HTTPError as e:
        body = e.response.text if e.response else str(e)
        print(f"    failed to create job: {body}")
        return None
    except Exception as e:
        print(f"    failed to create job: {e}")
        return None


def poll_job(job_id: int) -> dict | None:
    """Return completed job data, or None if still running."""
    try:
        resp = requests.get(
            f"{VAYNE_BASE_URL}/api/post_scrapers/{job_id}",
            headers=vayne_headers(),
            timeout=30,
        )
        if resp.status_code == 202:
            return None  # still processing
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") in ("completed", "failed"):
            return data
        return None
    except Exception:
        return None


def fetch_posts(job_id: int) -> list[dict]:
    """Fetch paginated posts from a completed job."""
    posts = []
    page = 1
    per_page = 100
    while True:
        try:
            resp = requests.get(
                f"{VAYNE_BASE_URL}/api/post_scrapers/{job_id}",
                headers=vayne_headers(),
                params={"page": page, "per_page": per_page},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            page_posts = data.get("posts", [])
            posts.extend(page_posts)
            pagination = data.get("pagination", {})
            total = pagination.get("total_results", len(posts))
            if len(posts) >= total or not page_posts:
                break
            page += 1
        except Exception as e:
            print(f"    warning: error fetching page {page}: {e}")
            break
    return posts


# ---------------------------------------------------------------------------
# Post formatting
# ---------------------------------------------------------------------------

def format_posts(posts: list[dict], max_posts: int) -> str:
    """Convert a list of post objects into a compact string for the CSV column."""
    parts = []
    for post in posts[:max_posts]:
        content = (post.get("content") or "").strip()
        if not content:
            continue
        # Truncate long posts
        if len(content) > _POST_CONTENT_MAX:
            content = content[:_POST_CONTENT_MAX].rsplit(" ", 1)[0] + "…"
        likes = post.get("estimated_likes", 0) or 0
        comments = post.get("estimated_comments", 0) or 0
        posted_at = (post.get("posted_at") or "")[:10]  # YYYY-MM-DD
        header = f"[{posted_at} | 👍{likes} 💬{comments}]"
        parts.append(f"{header} {content}")
    return _POST_SEP.join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch recent LinkedIn posts for leads via Vayne profile_posts API"
    )
    parser.add_argument("--input", default=None,
                        help="Input CSV (default: data/scored_leads.csv if it exists, else data/raw_leads.csv)")
    parser.add_argument("--output", default=None,
                        help="Output CSV (default: data/post_enriched_leads.csv)")
    parser.add_argument("--min-score", type=float, default=None,
                        help="Only process leads with max ICP score >= this value")
    parser.add_argument("--max-score", type=float, default=None,
                        help="Only process leads with max ICP score <= this value")
    parser.add_argument("--post-limit", type=int, default=10,
                        help="Max posts to fetch per lead (1-20, default: 10)")
    parser.add_argument("--time-limit", default="month",
                        choices=["1h", "24h", "week", "month"],
                        help="Only fetch posts within this window (default: month)")
    parser.add_argument("--no-estimate", action="store_true",
                        help="Skip the credit estimation step (faster but may over-reserve)")
    args = parser.parse_args()

    require_vayne_token()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve input path
    if args.input:
        input_path = Path(args.input)
    elif (DATA_DIR / "scored_leads.csv").exists():
        input_path = DATA_DIR / "scored_leads.csv"
    else:
        input_path = DATA_DIR / "raw_leads.csv"

    output_path = Path(args.output) if args.output else DATA_DIR / "post_enriched_leads.csv"
    post_limit = max(1, min(20, args.post_limit))

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    print(f"Reading {input_path}...")
    fieldnames, rows = read_csv(input_path)
    print(f"Found {len(rows)} leads")

    # Find LinkedIn URL column
    url_col = find_url_column(fieldnames)
    if not url_col:
        print(f"Cannot find LinkedIn URL column. Available: {fieldnames}")
        sys.exit(1)
    print(f"Using column '{url_col}' for LinkedIn URLs")

    # Filter by score range (only relevant if scored CSV is used)
    score_cols = find_score_columns(fieldnames)
    target_rows = rows

    if score_cols and (args.min_score is not None or args.max_score is not None):
        filtered = []
        for row in rows:
            score = max_icp_score(row, score_cols)
            if args.min_score is not None and score < args.min_score:
                continue
            if args.max_score is not None and score > args.max_score:
                continue
            filtered.append(row)
        print(f"Score filter [{args.min_score}–{args.max_score}]: {len(filtered)}/{len(rows)} leads selected")
        target_rows = filtered
    elif args.min_score is not None or args.max_score is not None:
        print("Note: score filter specified but no score columns found — processing all leads")

    # Collect valid LinkedIn profile URLs
    to_process = []
    for row in target_rows:
        url = (row.get(url_col) or "").strip()
        if url and "linkedin.com/in/" in url:
            to_process.append(row)

    print(f"{len(to_process)} leads have valid LinkedIn URLs")
    if not to_process:
        print("Nothing to process.")
        sys.exit(0)

    # Credit estimate warning
    print(f"\nPost scraping plan:")
    print(f"  Profiles  : {len(to_process)}")
    print(f"  Posts/lead: up to {post_limit}")
    print(f"  Window    : {args.time_limit}")
    print(f"  Cost      : 1 credit per person who reacted to each post (variable, refunded if unused)")
    print()

    # -----------------------------------------------------------------------
    # Phase 1: Estimate + create jobs
    # -----------------------------------------------------------------------
    ts = time.strftime("%Y%m%d-%H%M%S")
    # Map: row index in `to_process` -> job_id
    job_map: dict[int, int] = {}

    print("Creating post scraper jobs...")
    for i, row in enumerate(to_process):
        profile_url = (row.get(url_col) or "").strip()
        name = row.get("first name", "") + " " + row.get("last name", "")
        print(f"  [{i+1}/{len(to_process)}] {name.strip() or profile_url}")

        # Estimate credits
        est_credits = None
        if not args.no_estimate:
            est_credits = estimate_credits(profile_url, post_limit, args.time_limit)

        # Create job
        job_name = safe_name(profile_url, f"{ts}-{i}")
        job_id = create_job(profile_url, job_name, post_limit, args.time_limit, est_credits)
        if job_id is not None:
            job_map[i] = job_id

        # Respect rate limits between creations
        if i < len(to_process) - 1:
            time.sleep(_CREATE_DELAY_S)

    print(f"\n{len(job_map)}/{len(to_process)} jobs created successfully")
    if not job_map:
        print("No jobs created. Exiting.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Phase 2: Poll all jobs until complete
    # -----------------------------------------------------------------------
    print("\nPolling jobs until complete...")
    pending = dict(job_map)   # idx -> job_id
    results: dict[int, dict] = {}  # idx -> completed job data
    start = time.time()

    while pending and (time.time() - start) < _POLL_TIMEOUT_S:
        done_this_round = []
        for idx, job_id in pending.items():
            data = poll_job(job_id)
            if data is not None:
                done_this_round.append(idx)
                results[idx] = data
                status = data.get("status", "?")
                posts_found = data.get("total_posts", 0)
                print(f"  job #{job_id} {status} — {posts_found} posts found")

        for idx in done_this_round:
            del pending[idx]

        if pending:
            print(f"  {len(pending)} jobs still running, waiting {_POLL_INTERVAL_S}s...")
            time.sleep(_POLL_INTERVAL_S)

    if pending:
        print(f"Warning: {len(pending)} jobs timed out and will be skipped")

    # -----------------------------------------------------------------------
    # Phase 3: Fetch posts and build recent_posts strings
    # -----------------------------------------------------------------------
    print("\nFetching post content...")
    post_content: dict[int, str] = {}  # idx -> formatted string

    for idx, data in results.items():
        job_id = job_map[idx]
        if data.get("status") != "completed":
            post_content[idx] = ""
            continue
        posts = fetch_posts(job_id)
        formatted = format_posts(posts, post_limit)
        post_content[idx] = formatted
        name = to_process[idx].get("first name", "") + " " + to_process[idx].get("last name", "")
        print(f"  {name.strip()}: {len(posts)} posts, {len(formatted)} chars")

    # -----------------------------------------------------------------------
    # Phase 4: Merge into all rows and write output
    # -----------------------------------------------------------------------
    # Add recent_posts column to fieldnames
    out_fields = fieldnames[:]
    if "recent_posts" not in out_fields:
        out_fields.append("recent_posts")

    # Build a lookup: row object id -> post content
    # We need to match back to_process[idx] → rows (same objects)
    processed_ids = {id(to_process[idx]): post_content.get(idx, "") for idx in post_content}

    for row in rows:
        if "recent_posts" not in row:
            row["recent_posts"] = processed_ids.get(id(row), "")

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    enriched_count = sum(1 for row in rows if row.get("recent_posts"))
    print(f"\nDone! {enriched_count}/{len(rows)} leads have post data → {output_path}")


if __name__ == "__main__":
    main()
