"""Step 1: Scrape a Sales Navigator search via Vayne API.

Automatically splits large requests into multiple orders (each capped at
--batch-size leads), polls them in parallel, then merges and deduplicates
the results into a single output CSV.
"""
import argparse
import csv
import io
import os
import sys
import time
import threading
from pathlib import Path

import requests

from config import DATA_DIR, VAYNE_BASE_URL, require_vayne_token, vayne_headers

# Vayne enforces a per-order lead cap regardless of what you pass as limit.
# Set this to match your plan's actual cap.
DEFAULT_BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def check_url(url: str) -> dict:
    """Validate the Sales Navigator URL and return prospect count."""
    resp = requests.post(
        f"{VAYNE_BASE_URL}/api/url_checks",
        headers=vayne_headers(),
        json={"url": url},
    )
    resp.raise_for_status()
    return resp.json()


def create_order(url: str, name: str, limit: int, webhook: str | None = None) -> dict:
    """Create a single Vayne scraping order."""
    payload = {"url": url, "export_format": "advanced", "name": name}
    if limit > 0:
        payload["limit"] = limit
    if webhook:
        payload["secondary_webhook"] = webhook
    resp = requests.post(
        f"{VAYNE_BASE_URL}/api/orders",
        headers=vayne_headers(),
        json=payload,
    )
    resp.raise_for_status()
    result = resp.json()
    return result.get("order", result)


def poll_order(order_id: int, label: str, poll_interval: int = 15, timeout: int = 1800) -> dict:
    """Poll a single order until finished or failed. Thread-safe (prints with label)."""
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(
            f"{VAYNE_BASE_URL}/api/orders/{order_id}",
            headers=vayne_headers(),
        )
        resp.raise_for_status()
        order = resp.json().get("order", resp.json())
        status = order.get("scraping_status")
        scraped = order.get("scraped", 0)
        total = order.get("limit", "?")
        print(f"  [{label}] {status} | {scraped}/{total} scraped")

        if status == "finished":
            return order
        if status == "failed":
            print(f"  [{label}] Order failed!")
            return order  # return so other threads still finish

        time.sleep(poll_interval)

    print(f"  [{label}] Timeout — skipping this order.")
    return {}


def ensure_export(order: dict, fmt: str = "advanced") -> str | None:
    """Return the CSV download URL, trying `fmt` first then falling back to 'simple'.

    Vayne's API officially supports the 'simple' export format. The 'advanced'
    format (with full bio, job descriptions, etc.) may also work but is
    undocumented — we try it first and fall back gracefully.
    """
    # Some Vayne responses carry file_url at the top level (webhook-style)
    if order.get("file_url"):
        return order["file_url"]

    # Formats to try in order: preferred first, then 'simple' as fallback
    formats_to_try = [fmt] if fmt == "simple" else [fmt, "simple"]

    # 1. Check if already available in the order's exports dict
    exports = order.get("exports", {})
    for try_fmt in formats_to_try:
        export = exports.get(try_fmt, {})
        if export.get("status") == "completed" and export.get("file_url"):
            if try_fmt != fmt:
                print(f"  Note: '{fmt}' export not available — using '{try_fmt}' instead")
            return export["file_url"]

    order_id = order.get("id")
    if not order_id:
        return None

    # 2. Try triggering export via the /export endpoint, with fallback
    for try_fmt in formats_to_try:
        print(f"  Triggering '{try_fmt}' export for order #{order_id}...")
        try:
            resp = requests.post(
                f"{VAYNE_BASE_URL}/api/orders/{order_id}/export",
                headers=vayne_headers(),
                json={"export_format": try_fmt},
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"  Could not trigger '{try_fmt}' export: {e} — trying next format")
            continue

        for _ in range(120):
            time.sleep(10)
            resp = requests.get(
                f"{VAYNE_BASE_URL}/api/orders/{order_id}",
                headers=vayne_headers(),
            )
            resp.raise_for_status()
            order_data = resp.json().get("order", resp.json())
            # Top-level file_url (webhook-style)
            if order_data.get("file_url"):
                return order_data["file_url"]
            # Nested exports dict
            export = order_data.get("exports", {}).get(try_fmt, {})
            if export.get("status") == "completed" and export.get("file_url"):
                if try_fmt != fmt:
                    print(f"  Note: '{fmt}' export not available — using '{try_fmt}' instead")
                return export["file_url"]

        print(f"  Timeout waiting for '{try_fmt}' export on order #{order_id}.")

    return None


def fetch_rows(file_url: str) -> list[dict]:
    """Download a CSV from Vayne S3 and return rows as a list of dicts."""
    resp = requests.get(file_url)
    resp.raise_for_status()
    text = resp.content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


# ---------------------------------------------------------------------------
# Multi-order orchestration
# ---------------------------------------------------------------------------

def scrape_batch(url: str, name: str, limit: int, results: list, lock: threading.Lock, idx: int, webhook: str | None = None):
    """Create one order, poll it, download rows, and append to shared results list."""
    label = f"batch-{idx + 1}"
    try:
        order = create_order(url, name=name, limit=limit, webhook=webhook)
        order_id = order["id"]
        print(f"  [{label}] Order #{order_id} created")
        order = poll_order(order_id, label=label)
        if not order:
            return
        file_url = ensure_export(order)
        if not file_url:
            return
        rows = fetch_rows(file_url)
        with lock:
            results.extend(rows)
            print(f"  [{label}] +{len(rows)} leads downloaded")
    except Exception as e:
        print(f"  [{label}] Error: {e}")


def deduplicate(rows: list[dict]) -> list[dict]:
    """Deduplicate rows by LinkedIn URL, preserving first occurrence."""
    seen = set()
    out = []
    url_col = next(
        (c for c in (rows[0].keys() if rows else []) if "linkedin url" in c.lower() and "company" not in c.lower()),
        None,
    )
    for row in rows:
        key = row.get(url_col, "") if url_col else str(row)
        if key and key not in seen:
            seen.add(key)
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scrape Sales Navigator via Vayne API (multi-order)")
    parser.add_argument("url", help="Sales Navigator search URL")
    parser.add_argument("--name", help="Base order name (batches get a -1, -2 … suffix)")
    parser.add_argument("--limit", type=int, default=0, help="Total leads to scrape (0 = all)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Leads per order (default: {DEFAULT_BATCH_SIZE}, set to match your Vayne plan cap)")
    parser.add_argument("--output", default=None, help="Output CSV path")
    parser.add_argument(
        "--webhook",
        default=os.getenv("VAYNE_WEBHOOK_URL"),
        help="Optional webhook URL — Vayne will POST the completed CSV URL here (overrides VAYNE_WEBHOOK_URL in .env)",
    )
    args = parser.parse_args()

    require_vayne_token()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = Path(args.output) if args.output else DATA_DIR / "raw_leads.csv"

    # 1. Validate URL
    print("Checking URL...")
    info = check_url(args.url)
    total_available = info["total"]
    print(f"Found {total_available} {info['type']}")

    # 2. Work out how many orders to create
    requested = args.limit if args.limit > 0 else total_available
    # Never request more than what the search actually has
    if requested > total_available:
        print(f"  Capping at {total_available} (search only has {total_available} leads)")
        requested = total_available
    batch_size = args.batch_size
    num_batches = (requested + batch_size - 1) // batch_size  # ceil division
    base_name = args.name or f"pipeline-{time.strftime('%Y%m%d-%H%M%S')}"

    print(f"\nTarget: {requested} leads → {num_batches} order(s) of up to {batch_size} each")
    print(f"Base order name: {base_name}\n")

    if args.webhook:
        print(f"Webhook: results will also be POSTed to {args.webhook}")

    if num_batches == 1:
        # Fast path — single order, no threading needed
        order = create_order(args.url, name=base_name, limit=batch_size, webhook=args.webhook)
        order_id = order["id"]
        print(f"Order #{order_id} created (status: {order.get('scraping_status')})")
        print("Waiting for scraping to complete...")
        order = poll_order(order_id, label="batch-1")
        file_url = ensure_export(order)
        if not file_url:
            print("Export failed.")
            sys.exit(1)
        rows = fetch_rows(file_url)
    else:
        # Multi-order: create and poll all batches concurrently
        results: list[dict] = []
        lock = threading.Lock()
        threads = []

        for i in range(num_batches):
            batch_limit = min(batch_size, requested - i * batch_size)
            name = f"{base_name}-{i + 1}"
            t = threading.Thread(
                target=scrape_batch,
                args=(args.url, name, batch_limit, results, lock, i),
                kwargs={"webhook": args.webhook},
                daemon=True,
            )
            threads.append(t)
            t.start()
            time.sleep(1)  # small stagger to avoid hammering the API

        for t in threads:
            t.join()

        rows = results

    # 3. Deduplicate and write
    raw_count = len(rows)
    rows = deduplicate(rows)

    if not rows:
        print("No leads collected.")
        sys.exit(1)

    # Warn if Vayne returned mostly duplicate results across batches
    if num_batches > 1:
        duplicate_rate = (raw_count - len(rows)) / raw_count if raw_count else 0
        if duplicate_rate > 0.5:
            print(
                f"\n⚠️  Duplicate results warning: {raw_count} rows fetched across {num_batches} orders, "
                f"only {len(rows)} unique after deduplication ({duplicate_rate:.0%} duplicates).\n"
                f"   Vayne is returning the same leads for every order on this search URL.\n"
                f"   To get more unique leads: upgrade your Vayne plan for a higher per-order cap,\n"
                f"   or use multiple different Sales Navigator search URLs.\n"
            )

    fieldnames = list(rows[0].keys())
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone! {len(rows)} unique leads saved to {output}")


if __name__ == "__main__":
    main()
