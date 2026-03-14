# Blueprint: proofmark-builder

**Stage:** Build
**States:** BuildProofmarkConfig, BuildProofmarkResponse
**Outcome type:** SUCCESS / FAIL

## Role

Build the Proofmark comparison configuration. Define column-level match rules:
strict, fuzzy, or non-strict. Every relaxation from strict requires evidence.
Default is strict.

When invoked as BuildProofmarkResponse, rebuild incorporating reviewer feedback.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `rejection_reason`: (BuildProofmarkResponse only)
- `rejection_conditions`: (BuildProofmarkResponse only)

## Reads

**Process artifacts:**
- `{job_dir}/process/ReviewJobArtifacts.json`

**Product artifacts:**
- `{job_dir}/artifacts/brd.md` — output schemas, anti-patterns
- `{job_dir}/artifacts/fsd.md` — implementation details
- `{job_dir}/artifacts/output-inventory.md` — actual OG output characteristics
- `{job_dir}/artifacts/code/jobconf.json`

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/proofmark-config.yaml`
- **Content:** Per-column match rules with justifications for any non-strict
  rules. Sort columns. Header/trailer comparison flags.

### Process artifact
- **File:** `{job_dir}/process/BuildProofmarkConfig.json`
- **Body:** `{ "column_count": N, "strict_columns": N, "fuzzy_columns": N, "non_strict_columns": N }`

## Method

1. Read BRD output schemas and anti-patterns.
2. Read output inventory for actual OG column list and sample values.
3. For each column, determine match rule:
   - **strict** — default. Values must match exactly.
   - **fuzzy** — numeric tolerance. Use for float columns where Python/C#
     precision may differ.
   - **non_strict** — known formatting differences only (date formats,
     timestamp formats, trailing zeros).
4. Every non-strict/fuzzy rule must cite BRD anti-pattern or output inventory
   evidence.
5. Determine sort columns for deterministic row ordering.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Proofmark config: N strict, M fuzzy, K non-strict columns", "conditions": []}
```

## Constraints

- Default is strict. Every relaxation requires cited justification.
- Known formatting differences from Python port:
  - Trailing zero suppression (`1.50` vs `1.5`)
  - Date format (`M/d/yyyy` vs `yyyy-MM-dd`)
  - Timestamp format (`10/8/2024 3:35:35 AM` vs `2024-10-08 03:35:35`)
  - Integer-as-float (`.0` suffix)
- When unsure, default to strict. Proofmark failures surface real issues
  for the triage pipeline.
