# Blueprint: proofmark-executor

**Stage:** Validate
**States:** ExecuteProofmark
**Outcome type:** SUCCESS / FAIL

## Role

Coordinate Proofmark validation: queue comparison tasks for all effective
dates, monitor results, produce a consolidated report. Proofmark runs on the
host — you queue tasks into the database and read results after the host-side
service processes them.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `effective_dates`: Dates to validate
- `db_connection`: Postgres connection details

## Reads

**Process artifacts:**
- `{job_dir}/process/ExecuteJobRuns.json` — which dates produced output

**Product artifacts:**
- `{job_dir}/artifacts/proofmark-config.yaml`

**Source material:**
- OG output at `{OG_CURATED}/{job_dir_name}/`
- RE output (produced by job-executor)

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/proofmark-results.md`
- **Content:** Per-date pass/fail, column-level mismatch details for failures,
  overall pass rate.

### Process artifact
- **File:** `{job_dir}/process/ExecuteProofmark.json`
- **Body:** `{ "dates_compared": N, "dates_passed": N, "dates_failed": N, "pass_rate": "100%", "failed_dates": [], "failure_summary": "" }`

## Method

1. Read proofmark config for path patterns and match rules.
2. For each date that produced output (per ExecuteJobRuns process artifact):
   a. Construct OG and RE file paths.
   b. Insert comparison task into `control.proofmark_test_queue`.
3. Poll for results until all tasks complete.
4. Read results from database.
5. For failures: extract column-level mismatch details.
6. Write consolidated results.
7. Return SUCCESS if all dates pass, FAIL if any fail.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "31/31 dates passed Proofmark validation", "conditions": []}
```
or
```json
{"outcome": "FAIL", "reason": "28/31 passed, 3 failed — row count mismatch on Oct 15, 22, 29", "conditions": []}
```

## Constraints

- Use the `claude` database role.
- Only compare dates with both OG and RE output.
- Capture enough failure detail for triage — column-level mismatches essential.
