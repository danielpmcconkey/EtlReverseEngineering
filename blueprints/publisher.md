# Blueprint: publisher

**Stage:** Build
**States:** Publish
**Outcome type:** SUCCESS / FAIL

## Role

Deploy the completed job artifacts into MockEtlFrameworkPython so the ETL
framework can find and execute them, then register the job in the control
schema. The framework expects job confs and external modules at standard
locations under `{ETL_ROOT}` — you copy them there from the working
directory in EtlReverseEngineering.

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

### Deployed files
- **Job conf:** Copy `{job_dir}/artifacts/code/jobconf.json`
  → `{ETL_ROOT}/JobExecutor/Jobs/{job_name}.json`
- **External modules (if applicable):** Copy each `.py` from
  `{job_dir}/artifacts/code/transforms/`
  → `{ETL_ROOT}/src/etl/modules/externals/`

### Process artifact
- **File:** `{job_dir}/process/Publish.json`
- **Body:** `{ "registered_path": "{ETL_ROOT}/JobExecutor/Jobs/{job_name}.json", "deployed_to": "{ETL_ROOT}/JobExecutor/Jobs/", "external_modules_deployed": N, "control_table": "control.jobs", "verified": true }`

No separate product artifact — deployment + registration is the deliverable.

## Method

1. Verify job conf exists and is valid JSON.
2. If conf references External modules, verify `.py` files exist in
   `artifacts/code/transforms/`.
3. Verify test results show all tests passed (from process artifact).
4. **Deploy artifacts into MockEtlFrameworkPython:**
   a. Copy job conf to `{ETL_ROOT}/JobExecutor/Jobs/{job_name}.json`.
   b. Copy any external modules to `{ETL_ROOT}/src/etl/modules/externals/`.
5. **Register in `control.jobs`:**
   ```sql
   INSERT INTO control.jobs (job_name, job_conf_path, is_active)
   VALUES ('{job_name}', '{ETL_ROOT}/JobExecutor/Jobs/{job_name}.json', true)
   ON CONFLICT (job_name) DO UPDATE SET
     job_conf_path = EXCLUDED.job_conf_path, is_active = true;
   ```
6. Verify registration by querying the table.
7. Verify deployed files are readable at the target paths.

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
{"outcome": "SUCCESS", "reason": "Job conf and 1 external module deployed to MockEtlFrameworkPython, registered in control.jobs", "conditions": []}
```

## Constraints

- Do NOT publish if unit tests failed. Return FAIL.
- Use `{ETL_ROOT}` tokenized paths in `control.jobs` — never absolute paths.
- Use the `claude` database role via `172.18.0.1`.
- Do not modify `control.jobs` schema.
- Do not overwrite OG artifacts — RE job names should not collide with
  existing OG job names in `JobExecutor/Jobs/`.
