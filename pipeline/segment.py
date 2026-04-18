"""Step 4: Segment scored leads into per-ICP CSVs, keeping only those above the score threshold."""
import argparse
import csv
import re
import sys
from pathlib import Path

from config import DATA_DIR, SCORE_THRESHOLD


def main():
    parser = argparse.ArgumentParser(description="Segment scored leads by ICP")
    parser.add_argument("--input", default=None, help="Scored CSV (default: data/scored_leads.csv)")
    parser.add_argument("--output-dir", default=None, help="Output dir (default: data/segments)")
    parser.add_argument("--threshold", type=int, default=SCORE_THRESHOLD,
                        help=f"Min ICP fit score to qualify (default: {SCORE_THRESHOLD})")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else DATA_DIR / "scored_leads.csv"
    output_dir = Path(args.output_dir) if args.output_dir else DATA_DIR / "segments"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    with input_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    print(f"Read {len(rows)} leads from {input_path}")

    # Detect score columns: score_<icp_name>
    score_cols = [c for c in fieldnames if re.match(r"^score_", c)]
    if not score_cols:
        print(f"No score columns found (expected 'score_*'). Columns: {fieldnames}")
        sys.exit(1)

    print(f"Score columns: {score_cols}")
    print(f"Threshold: >= {args.threshold}")

    total_qualified = 0
    for col in score_cols:
        icp_name = col.replace("score_", "") if col.startswith("score_") else "all"
        qualified = []
        for row in rows:
            try:
                score = float(row.get(col, 0) or 0)
            except (ValueError, TypeError):
                continue
            if score >= args.threshold:
                qualified.append(row)

        if not qualified:
            print(f"  {icp_name}: 0 qualified leads (skipped)")
            continue

        out_path = output_dir / f"{icp_name}.csv"
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(qualified)

        print(f"  {icp_name}: {len(qualified)} qualified leads -> {out_path}")
        total_qualified += len(qualified)

    print(f"\nDone! {total_qualified} total qualified leads across {len(score_cols)} ICP(s)")


if __name__ == "__main__":
    main()
