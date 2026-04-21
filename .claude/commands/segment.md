Segment scored leads into separate CSVs per ICP, keeping only high-scoring leads.

User input: $ARGUMENTS

## Instructions

1. Parse optional arguments: `[--input PATH] [--threshold N]`
   - Default input: `data/scored_leads.csv`
   - Default threshold: value from SCORE_THRESHOLD in .env (default 60)

2. Verify the scored CSV exists. If not, tell the user to run `/score` first.

3. Run the segmentation script from the project root:
   ```
   python pipeline/segment.py [--input PATH] [--threshold N]
   ```

4. The script will:
   - Read the scored CSV
   - For each ICP score column, filter leads >= threshold
   - Write a separate CSV per ICP to `data/segments/<icp_name>.csv`

5. Report: how many qualified leads per ICP, output file locations.

These per-ICP CSVs are ready for manual import into Linked Helper to launch campaigns.
