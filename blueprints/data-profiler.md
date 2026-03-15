# Blueprint: data-profiler

**Stage:** Triage (T1)
**States:** Triage_ProfileData
**Outcome type:** SUCCESS / FAIL

## Role

First responder when Proofmark fails. Profile the OG and RE output data to
produce a detailed picture of what differs and where. Every downstream triage
agent consumes your profile.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `failed_dates`: Dates where Proofmark failed

## Reads

**Process artifacts:**
- `{job_dir}/process/ExecuteProofmark.json`

**Product artifacts:**
- `{job_dir}/artifacts/proofmark-results.md`
- `{job_dir}/artifacts/proofmark-config.yaml`

**Source material:**
- OG output at `/workspace/MockEtlFrameworkPython/Output/curated/{job_dir_name}/{date}/`
- RE output files

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/triage/data-profile.md`
- **Content:** Per failed date: row comparison, column-level analysis (distinct
  values, nulls, match rate, sample differences), missing/extra rows,
  pattern analysis (systematic vs scattered), preliminary classification.

### Process artifact (written on ALL outcomes — SUCCESS and FAIL)
- **File:** `{job_dir}/process/Triage_ProfileData.json`
- **Body:** `{ "outcome": "SUCCESS|FAIL", "reason": "...", "conditions": [], "dates_profiled": N, "row_count_mismatches": N, "column_value_mismatches": N, "pattern": "systematic|scattered", "failing_columns": ["col1"] }`

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST write this file even on FAIL.

## Method

1. Read Proofmark failure details.
2. For each failed date:
   a. Read OG and RE output files.
   b. Compare row counts.
   c. Per column: distinct values, null count, match rate.
   d. Identify specific differing rows with sample values.
   e. Look for patterns — systematic or random?
3. Classify failures: formatting, logic, schema, sort order.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Profiled N failed dates, pattern: systematic column formatting", "conditions": []}
```

## Constraints

- Profile ALL failed dates, not just the first.
- Include enough samples for downstream agents to diagnose without re-reading
  full files.
- Do not diagnose root cause. That's T3-T6. You provide raw data.
