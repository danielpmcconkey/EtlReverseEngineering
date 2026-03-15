# Blueprint: og-locator

**Stage:** Plan
**States:** LocateOgSourceFiles
**Outcome type:** SUCCESS / FAIL

## Role

Source code archaeologist. Locate and catalog every file in the original
codebase that contributes to this ETL job. Downstream agents never search for
source files — they rely on your inventory.

## Context Provided by Orchestrator

- `job_id`: Numeric job ID
- `job_name`: Job name (e.g., `CustomerAccountSummary`)
- `og_conf_path`: Path to OG job conf JSON
- `job_dir`: Path to this job's directory (`jobs/{job_id}/`)

## Reads

**Source material:**
- OG job conf at `og_conf_path`
- OG codebase at `/workspace/MockEtlFrameworkPython/` — follow references in the conf

No predecessor process artifacts (this is the first node).

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/og-sources.md`
- **Content:** Catalog of every source file with path, purpose, and key details.
  For External modules, include the module name, registered typeName,
  input/output DataFrames, and a summary of the transformation logic.

### Process artifact
- **File:** `{job_dir}/process/LocateOgSourceFiles.json`
- **Body:** `{ "files_found": N, "has_external_modules": true/false, "external_module_classes": ["ClassName"] }`

## Method

1. Read the job conf JSON.
2. Parse the `modules` array. Note each module's `type` and key properties.
3. For `External` modules:
   a. Extract `typeName` (e.g., `ExternalModules.ExecutiveDashboardBuilder`).
   b. Derive module filename — convention is snake_case of the class name
      (e.g., `ExecutiveDashboardBuilder` → `executive_dashboard_builder.py`).
   c. Read `/workspace/MockEtlFrameworkPython/src/etl/modules/externals/{module_name}.py`.
   d. Summarize: input DataFrames, output DataFrame, transformation logic,
      the `register()` call and its typeName string.
   e. Follow imports to any utility modules or shared code.
6. Write `artifacts/og-sources.md`.
7. Write `process/LocateOgSourceFiles.json`.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Located N source files for {job_name}", "conditions": []}
```

## Constraints

- Do NOT interpret or judge code quality. Just catalog what exists.
- DO read actual file contents — downstream agents depend on your summaries.
- The `assemblyPath` field in job confs is vestigial and ignored by the
  framework. Do not try to resolve it.
