"""Step 1: Scrape a Sales Navigator search via the Vayne API.

The Vayne API does not expose paging or offsets for orders. The documented
flow is:

1. Validate the Sales Navigator URL.
2. Create one order with the requested limit.
3. Poll the order until scraping is finished.
4. Generate or reuse the CSV export.
5. Download the export file_url.
"""

import argparse
import csv
import io
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

from config import DATA_DIR, VAYNE_BASE_URL, require_vayne_token, vayne_headers

DEFAULT_EXPORT_FORMAT = "advanced"
HTTP_TIMEOUT = 60


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def order_from_response(resp: requests.Response) -> dict[str, Any]:
    """Return the order object from a Vayne response."""
    data = resp.json()
    return data.get("order", data)


def raise_for_vayne_error(resp: requests.Response) -> None:
    """Raise with Vayne's JSON error details when available."""
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        try:
            body = resp.json()
            details = body.get("details") or body.get("error") or body
        except ValueError:
            details = resp.text.strip()
        raise RuntimeError(f"Vayne API error {resp.status_code}: {details}") from exc


def check_url(url: str) -> dict[str, Any]:
    """Validate the Sales Navigator URL and return prospect count."""
    resp = requests.post(
        f"{VAYNE_BASE_URL}/api/url_checks",
        headers=vayne_headers(),
        json={"url": url},
        timeout=HTTP_TIMEOUT,
    )
    raise_for_vayne_error(resp)
    return resp.json()


def create_order(
    url: str,
    name: str,
    limit: int,
    export_format: str = DEFAULT_EXPORT_FORMAT,
    webhook: str | None = None,
) -> dict[str, Any]:
    """Create a single Vayne scraping order."""
    payload: dict[str, Any] = {
        "url": url,
        "name": name,
        "export_format": export_format,
    }
    if limit > 0:
        payload["limit"] = limit
    if webhook:
        payload["secondary_webhook"] = webhook

    resp = requests.post(
        f"{VAYNE_BASE_URL}/api/orders",
        headers=vayne_headers(),
        json=payload,
        timeout=HTTP_TIMEOUT,
    )
    raise_for_vayne_error(resp)
    return order_from_response(resp)


def get_order(order_id: int) -> dict[str, Any]:
    """Fetch a Vayne order by id."""
    resp = requests.get(
        f"{VAYNE_BASE_URL}/api/orders/{order_id}",
        headers=vayne_headers(),
        timeout=HTTP_TIMEOUT,
    )
    raise_for_vayne_error(resp)
    return order_from_response(resp)


def poll_order(
    order_id: int,
    poll_interval: int = 15,
    timeout: int = 1800,
) -> dict[str, Any]:
    """Poll an order until scraping finishes or fails."""
    start = time.time()
    while time.time() - start < timeout:
        order = get_order(order_id)
        status = order.get("scraping_status", "unknown")
        scraped = order.get("scraped", 0)
        target = order.get("limit") or order.get("total") or "?"
        print(f"  scraping: {status} | {scraped}/{target} scraped")

        if status == "finished":
            return order
        if status == "failed":
            raise RuntimeError(f"Vayne order #{order_id} failed")

        time.sleep(poll_interval)

    raise TimeoutError(f"Timed out waiting for Vayne order #{order_id}")


def export_file_url(order: dict[str, Any], export_format: str) -> str | None:
    """Return the completed export URL from an order, if present."""
    if order.get("file_url"):
        return order["file_url"]

    export = order.get("exports", {}).get(export_format, {})
    if export.get("status") == "completed" and export.get("file_url"):
        return export["file_url"]

    return None


def export_status(order: dict[str, Any], export_format: str) -> str:
    """Return a displayable export status for an order."""
    export = order.get("exports", {}).get(export_format, {})
    return export.get("status") or order.get("export_status") or "not_started"


def trigger_export(order_id: int, export_format: str) -> dict[str, Any]:
    """Ask Vayne to generate an export for a completed order."""
    resp = requests.post(
        f"{VAYNE_BASE_URL}/api/orders/{order_id}/export",
        headers=vayne_headers(),
        json={"export_format": export_format},
        timeout=HTTP_TIMEOUT,
    )

    # A different export may already be running. In that case the documented
    # recovery path is simply to keep polling the order until a file_url appears.
    if resp.status_code == 409:
        print("  export: another export is already in progress; waiting for it")
        return get_order(order_id)

    raise_for_vayne_error(resp)
    return order_from_response(resp)


def ensure_export(
    order: dict[str, Any],
    export_format: str = DEFAULT_EXPORT_FORMAT,
    poll_interval: int = 10,
    timeout: int = 1200,
) -> str:
    """Generate the requested export if needed and return its CSV URL."""
    file_url = export_file_url(order, export_format)
    if file_url:
        return file_url

    order_id = order.get("id")
    if not order_id:
        raise RuntimeError("Vayne response did not include an order id")

    print(f"Generating '{export_format}' export for order #{order_id}...")
    order = trigger_export(order_id, export_format)
    file_url = export_file_url(order, export_format)
    if file_url:
        return file_url

    start = time.time()
    while time.time() - start < timeout:
        time.sleep(poll_interval)
        order = get_order(order_id)
        status = export_status(order, export_format)
        print(f"  export: {status}")

        file_url = export_file_url(order, export_format)
        if file_url:
            return file_url
        if status == "failed":
            raise RuntimeError(f"Vayne '{export_format}' export failed for order #{order_id}")

    raise TimeoutError(f"Timed out waiting for '{export_format}' export on order #{order_id}")


def fetch_rows(file_url: str) -> list[dict[str, str]]:
    """Download a CSV from Vayne's export URL and return rows."""
    resp = requests.get(file_url, timeout=120)
    raise_for_vayne_error(resp)
    text = resp.content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def deduplicate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Deduplicate rows by LinkedIn URL, preserving first occurrence."""
    if not rows:
        return rows

    url_col = next(
        (
            col
            for col in rows[0].keys()
            if "linkedin url" in col.lower() and "company" not in col.lower()
        ),
        None,
    )
    if not url_col:
        return rows

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        key = row.get(url_col, "").strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(row)
    return out


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write rows while preserving all columns returned by Vayne."""
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row.keys():
            if field not in seen:
                seen.add(field)
                fieldnames.append(field)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Sales Navigator via Vayne API")
    parser.add_argument("url", help="Sales Navigator search URL")
    parser.add_argument("--name", help="Vayne order name")
    parser.add_argument("--limit", type=int, default=0, help="Max leads to scrape (0 = all)")
    parser.add_argument(
        "--export-format",
        choices=("advanced", "simple"),
        default=DEFAULT_EXPORT_FORMAT,
        help=f"CSV export format to download (default: {DEFAULT_EXPORT_FORMAT})",
    )
    parser.add_argument("--output", default=None, help="Output CSV path")
    parser.add_argument(
        "--webhook",
        default=os.getenv("VAYNE_WEBHOOK_URL"),
        help="Optional webhook URL for Vayne to POST the completed CSV URL",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    require_vayne_token()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = Path(args.output) if args.output else DATA_DIR / "raw_leads.csv"

    print("Checking URL...")
    info = check_url(args.url)
    total_available = int(info["total"])
    prospect_type = info["type"]
    print(f"Found {total_available} {prospect_type}")

    if total_available <= 0:
        print("No leads available for this search URL.")
        sys.exit(1)

    requested = args.limit if args.limit > 0 else total_available
    if requested > total_available:
        print(f"  Capping at {total_available} (search only has {total_available} leads)")
        requested = total_available

    if args.batch_size is not None:
        print("  Ignoring --batch-size: Vayne orders do not support paging/offsets.")

    order_name = args.name or f"pipeline-{time.strftime('%Y%m%d-%H%M%S')}"

    print(f"\nCreating one Vayne order for {requested} lead(s)")
    print(f"Order name: {order_name}")
    print(f"Export format: {args.export_format}")
    if args.webhook:
        print(f"Webhook: results will also be POSTed to {args.webhook}")

    try:
        order = create_order(
            args.url,
            name=order_name,
            limit=requested,
            export_format=args.export_format,
            webhook=args.webhook,
        )
        order_id = order["id"]
        print(f"\nOrder #{order_id} created (status: {order.get('scraping_status')})")
        print("Waiting for scraping to complete...")

        order = poll_order(order_id)
        file_url = ensure_export(order, args.export_format)
        rows = fetch_rows(file_url)
    except Exception as exc:
        print(f"\nScrape failed: {exc}")
        sys.exit(1)

    raw_count = len(rows)
    rows = deduplicate(rows)

    if not rows:
        print("No leads collected.")
        sys.exit(1)

    write_csv(output, rows)

    if len(rows) != raw_count:
        print(f"Removed {raw_count - len(rows)} duplicate row(s) by LinkedIn URL.")

    print(f"\nDone! {len(rows)} lead(s) saved to {output}")


if __name__ == "__main__":
    main()
