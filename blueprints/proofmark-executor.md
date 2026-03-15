# Blueprint: proofmark-executor

**Stage:** Validate
**States:** ExecuteProofmark
**Outcome type:** SUCCESS / FAIL

## Role

Queue Proofmark comparison tasks for all effective dates, monitor results,
produce a consolidated report. Proofmark runs on the host — you insert tasks
into `control.proofmark_test_queue` and read results after the host-side
service processes them. You do NOT run Proofmark locally.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `effective_dates`: Dates to validate
- `db_connection`: Postgres connection details (host: `172.18.0.1`, port: `5432`,
  user: `claude`, database: `atc`)

## Reads

**Process artifacts:**
- `{job_dir}/process/ExecuteJobRuns.json` — which dates produced output
- `{job_dir}/process/Publish.json` — registered job name (`{job_name}_re`)

**Product artifacts:**
- `{job_dir}/artifacts/proofmark-config.yaml`

**Source material:**
- OG output at `{ETL_ROOT}/Output/curated/{job_name}/` (read-only Docker mount)
- RE output at `{ETL_ROOT}/Output/re-curated/{job_name}/` (produced by job-executor via host)

## Writes

### Deployed files
- **Proofmark config:** Copy `{job_dir}/artifacts/proofmark-config.yaml`
  → `/workspace/MockEtlFrameworkPython/RE/Jobs/{job_name}/proofmark-config.yaml`

### Product artifact
- **File:** `{job_dir}/artifacts/proofmark-results.md`
- **Content:** Per-date pass/fail, column-level mismatch details for failures,
  overall pass rate.

### Process artifact
- **File:** `{job_dir}/process/ExecuteProofmark.json`
- **Body:** `{ "dates_compared": N, "dates_passed": N, "dates_failed": N, "pass_rate": "100%", "failed_dates": [], "failure_summary": "" }`

## Method

**You cannot run Proofmark locally.** The Proofmark service runs on the host
and resolves `{ETL_ROOT}` paths from the host environment. You queue tasks
into the database and read results back.

1. Read the Proofmark config YAML for column match rules.
2. Read ExecuteJobRuns process artifact for dates that produced output.
3. **Discover the OG output directory name.** List the actual directory names
   under `Output/curated/` to find the correct case for the job's output
   directory. Do NOT assume `{job_name}` matches the filesystem directory
   name — it may differ in case or format (e.g., manifest says
   `DansTransactionSpecial` but the directory is `dans_transaction_special`).
   Use the discovered directory name for all OG path construction.
4. **Discover OG output dates.** List the date subdirectories under the OG
   output directory to discover which dates have OG output. Only queue
   comparison tasks for dates that exist in both OG and RE output directories.
5. **Deploy the proofmark config** alongside the job conf:
   Copy `{job_dir}/artifacts/proofmark-config.yaml`
   → `/workspace/MockEtlFrameworkPython/RE/Jobs/{job_name}/proofmark-config.yaml`
6. For each date that produced output, insert a comparison task:
   ```sql
   INSERT INTO control.proofmark_test_queue
     (config_path, lhs_path, rhs_path, job_key, date_key)
   VALUES (
     '{ETL_ROOT}/RE/Jobs/{job_name}/proofmark-config.yaml',
     '{ETL_ROOT}/Output/curated/{job_name}/{output_table_name}/{date}/{output_table_name}.csv',
     '{ETL_ROOT}/Output/re-curated/{job_name}/{output_table_name}/{date}/{output_table_name}.csv',
     '{job_name}_re',
     '{date}'
   );
   ```
   **Critical:** `{ETL_ROOT}` is a literal string token — do NOT resolve it.
   The host Proofmark service expands it at runtime from its own environment.
   Do NOT use absolute container paths — they mean nothing on the host.
7. Poll for results until all tasks complete:
   ```sql
   SELECT date_key, status, result, error_message
   FROM control.proofmark_test_queue
   WHERE job_key = '{job_name}_re'
     AND task_id >= {first_task_id}
   ORDER BY date_key;
   ```
   Wait until all rows are `Succeeded` or `Failed`.
8. For succeeded tasks, read `result` (`PASS` or `FAIL`) and `result_json`.
9. For failures: extract column-level mismatch details from `result_json`.
10. Write consolidated results to product artifact.
11. Return SUCCESS if all dates pass, FAIL if any fail.

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
{"outcome": "SUCCESS", "reason": "31/31 dates passed Proofmark validation", "conditions": []}
```
or
```json
{"outcome": "FAIL", "reason": "28/31 passed, 3 failed — row count mismatch on Oct 15, 22, 29", "conditions": []}
```

## Constraints

- **Do NOT run Proofmark locally.** No `proofmark serve`, no `python -m proofmark`.
  Queue via `control.proofmark_test_queue` only.
- Use `{ETL_ROOT}` tokens in all queue entry paths. `{ETL_ROOT}` is a literal
  string — the host resolves it at runtime. Never use container absolute paths.
- Use the `claude` database role via `172.18.0.1`.
- Only compare dates with both OG and RE output.
- Capture enough failure detail for triage — column-level mismatches essential.
- **Do NOT delete, update, or modify any previously inserted `proofmark_test_queue`
  rows, even if they failed.** Failed rows are audit evidence. If a batch fails
  and you need to retry, insert NEW rows with corrected paths. When polling for
  results, filter by `task_id >= {first_task_id}` of your CURRENT batch only.
