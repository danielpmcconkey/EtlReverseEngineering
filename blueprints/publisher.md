# Blueprint: publisher

**Stage:** Build
**States:** Publish
**Outcome type:** SUCCESS / FAIL

## Role

Register the completed job in the control schema so the ETL framework can
find and execute it. Verify all artifacts are in place. The framework accesses
generated code via tokenized paths — you register the tokenized path, not an
absolute path.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `db_connection`: Postgres connection details (host: `172.18.0.1`, port: `5432`,
  user: `claude`, database: `atc`)

## Reads

**Process artifacts:**
- `{job_dir}/process/ExecuteUnitTests.json` — must show all tests passed

**Product artifacts:**
- `{job_dir}/artifacts/code/jobconf.json`
- `{job_dir}/artifacts/code/transforms/` (if applicable)
- `{job_dir}/artifacts/tests/test-plan.md`

## Writes

### Process artifact
- **File:** `{job_dir}/process/Publish.json`
- **Body:** `{ "registered_path": "{token}/EtlReverseEngineering/jobs/{job_id}/artifacts/code/jobconf.json", "control_table": "control.jobs", "verified": true }`

No separate product artifact — registration is a DB operation.

## Method

1. Verify job conf exists and is valid JSON.
2. If conf references External modules, verify .py files exist in
   `artifacts/code/transforms/`.
3. Verify test results show all tests passed (from process artifact).
4. Register in `control.jobs`:
   ```sql
   INSERT INTO control.jobs (job_name, job_conf_path, is_active)
   VALUES ('{job_name}', '{token}/EtlReverseEngineering/jobs/{job_id}/artifacts/code/jobconf.json', true)
   ON CONFLICT (job_name) DO UPDATE SET
     job_conf_path = EXCLUDED.job_conf_path, is_active = true;
   ```
5. Verify registration by querying the table.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Job registered in control.jobs", "conditions": []}
```

## Constraints

- Do NOT publish if unit tests failed. Return FAIL.
- Use tokenized paths in control.jobs — never absolute paths.
- Use the `claude` database role.
- Do not modify control.jobs schema.
