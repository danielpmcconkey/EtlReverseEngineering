# Blueprint: job-executor

**Stage:** Validate
**States:** ExecuteJobRuns
**Outcome type:** SUCCESS / FAIL

## Role

Queue ETL job execution for all effective dates through the host-side Python
ETL framework. You do NOT run the framework locally — you insert tasks into
`control.task_queue` and the host service picks them up. If dates fail,
attempt to diagnose and fix the issue. You get a leash of 3 fix-and-retry
attempts. After 3, return FAIL for human review.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `effective_dates`: List of dates to run (e.g., `2024-10-01` through `2024-10-31`)
- `db_connection`: Postgres connection details (host: `172.18.0.1`, port: `5432`,
  user: `claude`, database: `atc`)

## Reads

**Process artifacts:**
- `{job_dir}/process/Publish.json` — confirms job is registered in `control.jobs`

**Product artifacts:**
- `{job_dir}/artifacts/code/jobconf.json`
- `{job_dir}/artifacts/code/{module_name}.py` (if applicable)
- `{job_dir}/artifacts/fsd.md` (for diagnostic reference)

## Writes

### Process artifact (written on ALL outcomes — SUCCESS and FAIL)
- **File:** `{job_dir}/process/ExecuteJobRuns.json`
- **Body:** `{ "outcome": "SUCCESS|FAIL", "reason": "...", "conditions": [], "dates_executed": N, "dates_succeeded": N, "dates_failed": N, "failed_dates": [], "attempts": N, "fixes_applied": ["description of fix 1", ...], "output_location": "{ETL_ROOT}/Output/re-curated/{job_name}/" }`

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST write this file even on FAIL (with diagnostic details).

Updates to product artifacts (if fixes applied):
- `{job_dir}/artifacts/code/jobconf.json` or `transforms/` (if code fix needed)

## Method

**You cannot run the ETL framework locally.** The framework's DB host is
`localhost`, which does not resolve inside the container. All job execution
goes through `control.task_queue` on the host.

1. Verify the job is registered (check Publish process artifact).
2. **Read the registered job name from the Publish process artifact.** The
   publisher registers the job as `{job_name}_re` in `control.jobs`. Use
   that `_re` name in all task_queue inserts.
3. **Queue all effective dates:**
   ```sql
   INSERT INTO control.task_queue (job_name, effective_date)
   VALUES ('{job_name}_re', '{date}');
   ```
   Insert one row per effective date. You can batch them in a single INSERT:
   ```sql
   INSERT INTO control.task_queue (job_name, effective_date)
   VALUES
     ('{job_name}_re', '2024-10-01'),
     ('{job_name}_re', '2024-10-02'),
     ...
     ('{job_name}_re', '2024-10-31');
   ```
4. **Poll for completion.** The host service processes tasks asynchronously.
   Poll periodically (e.g., every 30 seconds):
   ```sql
   SELECT effective_date, status, error_message
   FROM control.task_queue
   WHERE job_name = '{job_name}_re'
     AND task_id >= {first_task_id}
   ORDER BY effective_date;
   ```
   Wait until all rows are `Succeeded` or `Failed`. Do NOT re-insert tasks
   that are still `Pending` or `Running`.
5. **If all dates succeed:** Verify output exists at
   `/workspace/MockEtlFrameworkPython/Output/re-curated/{job_name}/`.
   Write process artifact, return SUCCESS.
6. **If any dates fail:** Read the `error_message` for each failed date.
   Diagnose:
   a. Categorize: code bug (wrong column, bad SQL, missing join), data issue
      (unexpected NULLs, missing source rows), or framework issue.
7. **Attempt fix (up to 3 attempts total):**
   a. If **code bug:** Fix the job conf SQL or external module. Re-queue ALL
      dates (not just the failed ones — a fix could break passing dates).
   b. If **data issue:** Likely unfixable by you. Return FAIL with diagnosis.
   c. If **framework issue:** Cannot fix. Return FAIL immediately.
   d. Log what you changed and why.
8. **After each fix:** Re-queue all dates. If all pass, SUCCESS.
9. **After 3 failed attempts:** Return FAIL with full diagnostic details.

## Database Connection

Connect via the Docker bridge gateway — NOT `localhost`:
```
Host: 172.18.0.1
Port: 5432
User: claude
Database: atc
Password: (ETL_DB_PASSWORD env var)
```

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

- **Do NOT run the ETL framework locally.** No `python -m cli`, no
  `python cli.py`. Queue via `control.task_queue` only.
- **3 attempts maximum.** After 3, return FAIL regardless.
- On re-run after a fix, queue ALL dates — not just previously failed ones.
- Keep fixes minimal and targeted.
- Log every fix attempt: what changed, why, results.
- If the fix requires upstream changes (BRD/FSD wrong), return FAIL with
  that diagnosis.
- Capture enough failure detail for the triage pipeline or human review.
