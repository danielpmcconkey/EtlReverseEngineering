# Blueprint: publisher

**Stage:** Build
**States:** Publish
**Outcome type:** SUCCESS / FAIL

## Role

Deploy the completed job artifacts into MockEtlFrameworkPython so the ETL
framework can find and execute them, then register the job in the control
schema. RE artifacts deploy to `RE/Jobs/` and `RE/externals/` — these are
symlinked to the host framework at runtime.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `db_connection`: Postgres connection details (host: `172.18.0.1`, port: `5432`,
  user: `claude`, database: `atc`)

## Reads

**Process artifacts:**
- `{job_dir}/process/ExecuteUnitTests.json` — must show all tests passed

**Product artifacts:**
- `{job_dir}/artifacts/code/jobconf.json`
- `{job_dir}/artifacts/code/{module_name}.py` (if applicable)
- `{job_dir}/artifacts/tests/test-plan.md`

## Writes

### Deployed files
- **Job conf:** Copy `{job_dir}/artifacts/code/jobconf.json`
  → `/workspace/MockEtlFrameworkPython/RE/Jobs/{job_name}/jobconf.json`
- **External modules (if applicable):** Copy each `.py` from
  `{job_dir}/artifacts/code/`
  → `/workspace/MockEtlFrameworkPython/RE/externals/{module_name}.py`

### Process artifact (written on ALL outcomes — SUCCESS and FAIL)
- **File:** `{job_dir}/process/Publish.json`
- **Body:** `{ "outcome": "SUCCESS|FAIL", "reason": "...", "conditions": [], "registered_name": "{job_name}_re", "registered_path": "{ETL_ROOT}/RE/Jobs/{job_name}/jobconf.json", "deployed_to": "RE/Jobs/{job_name}/", "external_modules_deployed": N, "control_table": "control.jobs", "verified": true }`

No separate product artifact — deployment + registration is the deliverable.

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST write this file even on FAIL.

## Method

1. Verify job conf exists and is valid JSON.
2. If conf references External modules, verify `.py` files exist in
   `{job_dir}/artifacts/code/`.
3. Verify test results show all tests passed (from process artifact).
4. **Deploy artifacts into MockEtlFrameworkPython:**
   a. Create directory `/workspace/MockEtlFrameworkPython/RE/Jobs/{job_name}/`
      if it doesn't exist.
   b. Copy job conf to `/workspace/MockEtlFrameworkPython/RE/Jobs/{job_name}/jobconf.json`.
   c. Copy any external modules to `/workspace/MockEtlFrameworkPython/RE/externals/`.
5. **Look up OG job description:**
   ```sql
   SELECT description FROM control.jobs WHERE job_name = '{job_name}';
   ```
6. **Register in `control.jobs`:**
   ```sql
   INSERT INTO control.jobs (job_name, description, job_conf_path, is_active)
   VALUES (
     '{job_name}_re',
     '{og_description}',
     '{ETL_ROOT}/RE/Jobs/{job_name}/jobconf.json',
     true
   )
   ON CONFLICT (job_name) DO UPDATE SET
     job_conf_path = EXCLUDED.job_conf_path,
     description = EXCLUDED.description,
     is_active = true,
     updated_at = now();
   ```
   `{ETL_ROOT}` is a literal string token — do NOT resolve it. The host
   framework expands it at runtime from its own environment.
7. Verify registration by querying the table.
8. Verify deployed files are readable at the target paths.

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
{"outcome": "SUCCESS", "reason": "Job conf deployed to RE/Jobs/{job_name}/, registered as {job_name}_re in control.jobs", "conditions": []}
```

## Constraints

- Do NOT publish if unit tests failed. Return FAIL.
- Use `{ETL_ROOT}` tokenized paths in `control.jobs` — never absolute paths.
  `{ETL_ROOT}` is a literal string the host resolves at runtime.
- Use the `claude` database role via `172.18.0.1`.
- Do not modify `control.jobs` schema.
- Deploy to `RE/Jobs/` and `RE/externals/`, NOT the OG directories.
- Register with `_re` suffix on job_name to avoid unique constraint collision.
