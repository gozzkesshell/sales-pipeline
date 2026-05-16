Segment scored leads into separate CSVs per ICP, keeping only high-scoring leads.

User input: $ARGUMENTS

## Instructions

1. Parse optional arguments: `[--input PATH] [--threshold N]`
   - Default input: `data/scored_leads.csv`
   - Default threshold: value from SCORE_THRESHOLD in .env (default 60)

2. Run the segmentation script using the Python command from CLAUDE.md (no detection needed — use it directly):
   ```
   PYTHONIOENCODING=utf-8 <PYTHON> pipeline/segment.py [--input PATH] [--threshold N]
   ```

3. The script filters leads by score threshold and writes one CSV per ICP to `data/segments/<icp_name>.csv`.

4. Report: how many qualified leads per ICP, output file paths.

These CSVs are ready for direct import into Linked Helper to launch campaigns.
