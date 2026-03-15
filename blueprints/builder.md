# Blueprint: builder

**Stage:** Build
**States:** BuildJobArtifacts, BuildJobArtifactsResponse
**Outcome type:** SUCCESS / FAIL

## Role

Build the Python job artifacts: job conf JSON and any external modules. Follow
the FSD line by line. Do not improvise. The FSD is the spec; you build exactly
what it says.

When invoked as BuildJobArtifactsResponse, rebuild incorporating reviewer
feedback.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `rejection_reason`: (BuildJobArtifactsResponse only)
- `rejection_conditions`: (BuildJobArtifactsResponse only)

## Reads

**Process artifacts:**
- `{job_dir}/process/WriteFsd.json` (or `ReviewFsd.json`)

**Product artifacts:**
- `{job_dir}/artifacts/fsd.md`
- `{job_dir}/artifacts/brd.md`

**Source material:**
- Python framework docs at `{FW_DOCS}/` — module reference
- Existing external modules at `{ETL_ROOT}/src/etl/modules/externals/`
  — reference for code style and module interface patterns

## Writes

### Product artifacts
- **Job conf:** `{job_dir}/artifacts/code/jobconf.json`
- **External modules (if applicable):** `{job_dir}/artifacts/code/{module_name}.py`

### Process artifact
- **File:** `{job_dir}/process/BuildJobArtifacts.json`
- **Body:** `{ "artifacts_produced": ["code/jobconf.json"], "module_count": N, "has_external_module": false, "fsd_items_implemented": N }`

## Method

1. Read the FSD. Section 6 has the target job conf JSON.
2. Read Python framework docs for module configuration schemas.
3. Build the job conf JSON per FSD. Ensure all required properties present.
4. If the FSD specifies an External module:
   a. Read 2-3 existing external modules for style and interface patterns.
   b. Implement using the `execute(shared_state) -> shared_state` interface.
   c. Use pandas for DataFrame operations.
5. Verify every FSD item is implemented.
6. **Code quality gate:** Before returning SUCCESS, invoke your `code-reviewer`
   sub-agent. Pass it the files you wrote. If it finds issues, fix them. Do not
   return SUCCESS with unresolved code quality findings.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Built job conf and N external modules per FSD", "conditions": []}
```

## Constraints

- Build EXACTLY what the FSD specifies. No features, optimizations, or
  "improvements" beyond the spec.
- All generated code lives in `{job_dir}/artifacts/code/`. NOT in
  MockEtlFrameworkPython directly. The publisher handles deployment.
- **RE naming convention:** All RE artifacts must be distinguishable from OG:
  - `jobName` in the job conf: `{job_name}_re` (e.g., `DansTransactionSpecial_re`)
  - `typeName` for external modules: append `_re` (e.g., `ExternalModules.MyClassName_re`)
  - External module `.py` filename: `{module_name}_re.py`
  - The `register()` call inside the module must use the `_re` typeName
- **Output directory:** Job confs must set `outputDirectory` to `Output/re-curated`
  (NOT `Output/curated` — that's OG output, read-only). This is a relative path
  the framework resolves against `{ETL_ROOT}` at runtime.
- **External modules:** The job conf uses `typeName` to reference external modules.
  The framework discovers modules by scanning its externals directories at import
  time — no file path in the conf. Write the `.py` file to `{job_dir}/artifacts/code/`.
  The publisher handles deployment to `RE/externals/`.
- The publisher handles all deployment — no cross-repo writes from the builder.
- If the FSD specifies preserving a load-bearing anti-pattern (one where
  remediation would change output), implement it as specified. The FSD's
  anti-pattern decisions have already been reviewed — the builder's job is
  faithful implementation of the spec, not second-guessing remediation choices.
