"""Step 1: Create a Vayne scraping order from a Sales Navigator URL and download results as CSV."""
import argparse
import sys
import time

import requests

from config import DATA_DIR, VAYNE_BASE_URL, require_vayne_token, vayne_headers


def check_url(url: str) -> dict:
    """Validate the Sales Navigator URL and return prospect count."""
    resp = requests.post(
        f"{VAYNE_BASE_URL}/api/url_checks",
        headers=vayne_headers(),
        json={"url": url},
    )
    resp.raise_for_status()
    return resp.json()


def create_order(url: str, name: str | None = None, limit: int | None = None) -> dict:
    """Create a Vayne scraping order."""
    payload = {"url": url, "export_format": "advanced"}
    if name:
        payload["name"] = name
    if limit and limit > 0:
        payload["limit"] = limit

    resp = requests.post(
        f"{VAYNE_BASE_URL}/api/orders",
        headers=vayne_headers(),
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


def poll_order(order_id: int, poll_interval: int = 15, timeout: int = 1800) -> dict:
    """Poll until the order reaches 'finished' or 'failed'."""
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
        print(f"  Status: {status} | {scraped}/{total} scraped")

        if status == "finished":
            return order
        if status == "failed":
            print("Order failed!")
            sys.exit(1)

        time.sleep(poll_interval)

    print("Timeout waiting for order to finish.")
    sys.exit(1)


def ensure_export(order: dict, fmt: str = "advanced") -> str:
    """Return the CSV download URL, triggering an export if needed."""
    exports = order.get("exports", {})
    export = exports.get(fmt, {})
    if export.get("status") == "completed" and export.get("file_url"):
        return export["file_url"]

    # Trigger export generation
    order_id = order["id"]
    print(f"Triggering {fmt} export...")
    resp = requests.post(
        f"{VAYNE_BASE_URL}/api/orders/{order_id}/export",
        headers=vayne_headers(),
        json={"export_format": fmt},
    )
    resp.raise_for_status()

    # Poll for export
    for _ in range(120):
        time.sleep(10)
        resp = requests.get(
            f"{VAYNE_BASE_URL}/api/orders/{order_id}",
            headers=vayne_headers(),
        )
        resp.raise_for_status()
        export = resp.json().get("order", resp.json()).get("exports", {}).get(fmt, {})
        if export.get("status") == "completed" and export.get("file_url"):
            return export["file_url"]

    print("Timeout waiting for export.")
    sys.exit(1)


def download_csv(file_url: str, output_path):
    """Download the CSV from Vayne S3."""
    print(f"Downloading CSV...")
    resp = requests.get(file_url)
    resp.raise_for_status()
    output_path.write_bytes(resp.content)
    print(f"Saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Scrape Sales Navigator search via Vayne API")
    parser.add_argument("url", help="Sales Navigator search URL")
    parser.add_argument("--name", help="Order name (must be unique)")
    parser.add_argument("--limit", type=int, default=0, help="Max number of leads to scrape (0 = all)")
    parser.add_argument("--output", default=None, help="Output CSV path")
    args = parser.parse_args()

    require_vayne_token()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = args.output if args.output else str(DATA_DIR / "raw_leads.csv")

    # 1. Validate URL
    print("Checking URL...")
    info = check_url(args.url)
    print(f"Found {info['total']} {info['type']}")

    # 2. Create order
    limit = args.limit if args.limit > 0 else None
    order_name = args.name or f"pipeline-{time.strftime('%Y%m%d-%H%M%S')}"
    print(f"Creating order '{order_name}'...")
    result = create_order(args.url, name=order_name, limit=limit)
    order = result.get("order", result)
    order_id = order["id"]
    print(f"Order #{order_id} created (status: {order.get('scraping_status')})")

    # 3. Poll until finished
    print("Waiting for scraping to complete...")
    order = poll_order(order_id)

    # 4. Download CSV
    file_url = ensure_export(order)
    from pathlib import Path
    download_csv(file_url, Path(output))

    print(f"\nDone! {order.get('scraped', '?')} leads saved to {output}")


if __name__ == "__main__":
    main()
