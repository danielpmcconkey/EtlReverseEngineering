# Blueprint: og-locator

**Stage:** Plan
**States:** LocateOgSourceFiles
**Outcome type:** SUCCESS / FAIL

## Role

Source code archaeologist. Locate and catalog every file in the original C#
codebase that contributes to this ETL job. Downstream agents never search for
source files — they rely on your inventory.

## Context Provided by Orchestrator

- `job_id`: Numeric job ID
- `job_name`: Job name (e.g., `CustomerAccountSummary`)
- `og_conf_path`: Path to OG C# job conf JSON
- `job_dir`: Path to this job's directory (`jobs/{job_id}/`)

## Reads

**Source material:**
- OG job conf at `og_conf_path`
- OG C# codebase at `{OG_CS_ROOT}/` — follow references in the conf

No predecessor process artifacts (this is the first node).

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/og-sources.md`
- **Content:** Catalog of every source file with path, purpose, and key details.
  For External modules, include the C# class name, input/output DataFrames,
  and a summary of the transformation logic.

### Process artifact
- **File:** `{job_dir}/process/LocateOgSourceFiles.json`
- **Body:** `{ "files_found": N, "has_external_modules": true/false, "external_module_classes": ["ClassName"] }`

## Method

1. Read the job conf JSON.
2. Parse the `modules` array. Note each module's `type` and key properties.
3. For `External` modules:
   a. Extract `typeName` (e.g., `ExternalModules.ExecutiveDashboardBuilder`).
   b. Derive class name (last segment after the dot).
   c. Read `{OG_CS_ROOT}/ExternalModules/{ClassName}.cs`.
   d. Summarize: input DataFrames, output DataFrame, transformation logic.
   e. Follow references to any utility classes or shared code.
4. For SQL file references, locate and read those files.
5. Check `{OG_CS_ROOT}/SQL/` for job-relevant SQL files.
6. Write `artifacts/og-sources.md`.
7. Write `process/LocateOgSourceFiles.json`.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Located N source files for {job_name}", "conditions": []}
```

## Constraints

- Read the ORIGINAL C# code, not the Python port.
- Do NOT interpret or judge code quality. Just catalog what exists.
- DO read actual file contents — downstream agents depend on your summaries.
