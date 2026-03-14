# Blueprint: job-executor

**Stage:** Validate
**States:** ExecuteJobRuns
**Outcome type:** SUCCESS / FAIL

## Role

Execute the RE job for all effective dates through the Python ETL framework.
This produces the RE output files that Proofmark compares against the OG
originals. If dates fail, attempt to diagnose and fix the issue. You get a
leash of 3 fix-and-retry attempts. After 3, return FAIL for human review.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `effective_dates`: List of dates to run (e.g., `2024-10-01` through `2024-10-31`)

## Reads

**Process artifacts:**
- `{job_dir}/process/Publish.json` — confirms job is registered

**Product artifacts:**
- `{job_dir}/artifacts/code/jobconf.json`
- `{job_dir}/artifacts/code/transforms/` (if applicable)
- `{job_dir}/artifacts/fsd.md` (for diagnostic reference)

## Writes

### Process artifact
- **File:** `{job_dir}/process/ExecuteJobRuns.json`
- **Body:** `{ "dates_executed": N, "dates_succeeded": N, "dates_failed": N, "failed_dates": [], "attempts": N, "fixes_applied": ["description of fix 1", ...], "output_location": "..." }`

Updates to product artifacts (if fixes applied):
- `{job_dir}/artifacts/code/jobconf.json` or `transforms/` (if code fix needed)

## Method

1. Verify the job is registered (check Publish process artifact).
2. **Run all effective dates:**
   ```bash
   cd /workspace/MockEtlFrameworkPython
   python -m cli {date} {job_name}
   ```
3. Run dates in chronological order. If a date fails, continue running
   remaining dates — capture the full picture.
4. **If all dates succeed:** Write process artifact, return SUCCESS.
5. **If any dates fail:** Diagnose:
   a. Read the error output for each failed date.
   b. Categorize: code bug (wrong column, bad SQL, missing join), data issue
      (unexpected NULLs, missing source rows), or framework issue.
6. **Attempt fix (up to 3 attempts total):**
   a. If **code bug:** Fix the job conf SQL or external module. Re-run ALL
      dates (not just the failed ones — a fix could break passing dates).
   b. If **data issue:** Likely unfixable by you. Return FAIL with diagnosis.
   c. If **framework issue:** Cannot fix. Return FAIL immediately.
   d. Log what you changed and why.
7. **After each fix:** Re-run all dates. If all pass, SUCCESS.
8. **After 3 failed attempts:** Return FAIL with full diagnostic details.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "All 31 dates executed successfully", "conditions": []}
```
or
```json
{"outcome": "SUCCESS", "reason": "All 31 dates passed after 1 fix: added missing column alias in transformation SQL", "conditions": []}
```
or
```json
{"outcome": "FAIL", "reason": "3 fix attempts exhausted — 5 dates still failing with KeyError on 'customer_segment'. Appears to be a data sourcing gap (column not requested). See process artifact for details.", "conditions": []}
```

## Constraints

- **3 attempts maximum.** After 3, return FAIL regardless.
- On re-run after a fix, run ALL dates — not just previously failed ones.
- Keep fixes minimal and targeted.
- Log every fix attempt: what changed, why, results.
- If the fix requires upstream changes (BRD/FSD wrong), return FAIL with
  that diagnosis.
- Capture enough failure detail for the triage pipeline or human review.
