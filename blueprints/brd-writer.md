# Blueprint: brd-writer

**Stage:** Define
**States:** WriteBrd, WriteBrdResponse
**Outcome type:** SUCCESS / FAIL

## Role

Write the Business Requirements Document — the single source of truth for what
this job does. Every downstream artifact traces back to numbered BRD
requirements. When invoked as WriteBrdResponse, rewrite the full BRD
incorporating the reviewer's feedback.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `rejection_reason`: (WriteBrdResponse only) reviewer's feedback
- `rejection_conditions`: (WriteBrdResponse only) specific conditions list

## Reads

**Process artifacts:**
- `{job_dir}/process/LocateOgSourceFiles.json`
- `{job_dir}/process/InventoryOutputs.json`
- `{job_dir}/process/InventoryDataSources.json`
- `{job_dir}/process/NoteDependencies.json`

**Product artifacts:**
- `{job_dir}/artifacts/og-sources.md`
- `{job_dir}/artifacts/output-inventory.md`
- `{job_dir}/artifacts/data-sources.md`
- `{job_dir}/artifacts/dependencies.md`

**Source material:**
- OG Python source code — follow file paths cited in og-sources.md

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/brd.md`
- **Sections:** Purpose, data flow overview, data sources (numbered BRD-NNN),
  transformation rules (numbered), output formats and schemas (numbered),
  anti-patterns catalog, assumptions, requirement index.

### Process artifact
- **File:** `{job_dir}/process/WriteBrd.json`
- **Body:** `{ "requirement_count": N, "anti_pattern_count": N, "output_formats": ["csv"], "key_transformations": ["JOIN + aggregate"] }`

## Method

1. Read all four plan product artifacts.
2. Read OG source code files cited in og-sources.md — especially External
   module Python code for transformation logic.
3. Create numbered BRD requirements for each data source, transformation rule,
   and output specification.
4. Catalog anti-patterns: inefficient SQL, unnecessary complexity, hardcoded
   values, unnecessary use of External modules where standard modules would
   suffice. For each, recommend remediation as the default. Only recommend
   preserving an anti-pattern if you can identify specific data behavior that
   makes remediation unsafe for output equivalence. Flag which anti-patterns
   are likely load-bearing (remediation would change output) vs cosmetic
   (remediation is safe).
5. Build a requirement index at the bottom.
6. If this is a WriteBrdResponse invocation, incorporate the rejection feedback.
   Regenerate the FULL BRD, not a patch.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "BRD written with N requirements", "conditions": []}
```

## Constraints

- Every requirement MUST cite evidence — file path, plan artifact reference,
  or code reference.
- Be precise about transformation logic. Not "aggregates data" — specify
  exactly what is summed, counted, grouped, filtered.
- The BRD describes what the OG job does TODAY. Anti-patterns are cataloged
  with a remediation recommendation for each. Requirements reflect the
  desired RE behavior: current behavior where anti-patterns are load-bearing,
  improved behavior where remediation is safe.
