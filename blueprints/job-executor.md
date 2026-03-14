# Blueprint: job-executor

**Stage:** Validate
**States:** ExecuteJobRuns
**Outcome type:** SUCCESS / FAIL

## Role

Execute the RE job for all effective dates through the Python ETL framework
and capture results. This produces the RE output files that Proofmark will
compare against the OG originals.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `effective_dates`: List of dates to run (e.g., `2024-10-01` through `2024-10-31`)

## Reads

**Process artifacts:**
- `{job_dir}/process/Publish.json` — confirms job is registered

**Product artifacts:**
- `{job_dir}/artifacts/code/jobconf.json`

## Writes

### Process artifact
- **File:** `{job_dir}/process/ExecuteJobRuns.json`
- **Body:** `{ "dates_executed": N, "dates_succeeded": N, "dates_failed": N, "failed_dates": [], "output_location": "..." }`

No separate product artifact — execution logs captured in process JSON and stdout.

## Method

1. Verify the job is registered (check Publish process artifact).
2. For each effective date:
   ```bash
   cd /workspace/MockEtlFrameworkPython
   python -m cli {date} {job_name}
   ```
3. Capture stdout/stderr for each run.
4. Check output directory for produced files.
5. Record success/failure per date.
6. For failures: categorize as code bug, data issue, or framework issue.
7. Return SUCCESS if all dates succeeded, FAIL if any failed.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "All 31 dates executed successfully", "conditions": []}
```
or
```json
{"outcome": "FAIL", "reason": "3 of 31 dates failed — KeyError in transformation, see details above", "conditions": []}
```

## Constraints

- Do NOT fix failures. Report them.
- Run dates in chronological order.
- If a date fails, continue running remaining dates — capture the full picture.
- Capture enough failure detail for the triage pipeline.
