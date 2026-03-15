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

### Process artifact (written on ALL outcomes — SUCCESS and FAIL)
- **File:** `{job_dir}/process/BuildProofmarkConfig.json`
- **Body:** `{ "outcome": "SUCCESS|FAIL", "reason": "...", "conditions": [], "column_count": N, "strict_columns": N, "fuzzy_columns": N, "non_strict_columns": N }`

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST write this file even on FAIL.

## Proofmark Config YAML Schema

**You MUST follow this exact schema. Do NOT invent fields or structures.**

### Required fields

```yaml
comparison_target: "Human-readable name for this comparison"
reader: csv       # or "parquet" — match the OG output format
```

### Optional fields

```yaml
threshold: 100.0  # Minimum match percentage for PASS (default 100.0)
csv:              # Only when reader: csv
  header_rows: 1
  trailer_rows: 0
  sort_columns:
    - column_name
```

### Column classifications

**All columns are STRICT by default.** There is NO way to explicitly declare
a column as strict — you simply omit it. Only list columns that need
`excluded` or `fuzzy` treatment.

If all columns are strict, **omit the `columns:` section entirely.**

```yaml
columns:
  excluded:
    - name: run_id
      reason: "Non-deterministic UUID assigned at runtime"
  fuzzy:
    - name: interest_accrued
      tolerance: 0.01
      tolerance_type: absolute    # or "relative"
      reason: "Rounding variance between ROUND_HALF_UP and ROUND_HALF_EVEN"
```

**DO NOT use any other format.** Specifically:
- Do NOT create per-column dicts like `column_name: { match: strict }`
- Do NOT create per-column dicts like `column_name: { rule: strict }`
- Do NOT create a `strict:` list — strict is the implicit default
- The `columns:` section contains ONLY `excluded:` and `fuzzy:` lists
- Each list entry MUST have `name:` and `reason:` fields
- Fuzzy entries MUST also have `tolerance:` and `tolerance_type:`

### Complete example (CSV, all strict)

```yaml
comparison_target: "MyJob OG vs RE"
reader: csv
threshold: 100.0
csv:
  header_rows: 1
  trailer_rows: 0
  sort_columns:
    - primary_key_column
```

### Complete example (CSV, with fuzzy column)

```yaml
comparison_target: "MyJob OG vs RE"
reader: csv
threshold: 100.0
csv:
  header_rows: 1
  trailer_rows: 0
  sort_columns:
    - primary_key_column
columns:
  fuzzy:
    - name: balance
      tolerance: 0.01
      tolerance_type: absolute
      reason: "Float accumulation order differs between OG iterrows and RE vectorized groupby"
```

## Method

1. Read BRD output schemas and anti-patterns.
2. Read output inventory for actual OG column list and sample values.
3. For each column, determine match classification:
   - **strict** (default) — omit from config. Values must match exactly.
   - **fuzzy** — add to `columns.fuzzy` list with tolerance and reason.
     Use for float columns where OG and RE may produce precision differences.
   - **excluded** — add to `columns.excluded` list with reason.
     Use only for non-deterministic columns (UUIDs, timestamps).
4. Every fuzzy/excluded rule must cite BRD anti-pattern or output inventory
   evidence.
5. Determine sort columns for deterministic row ordering.
6. **Code quality gate:** Before returning SUCCESS, invoke your `code-reviewer`
   sub-agent. Pass it the proofmark config YAML you wrote. If it finds issues
   (malformed YAML, missing columns, unjustified relaxations), fix them. Do not
   return SUCCESS with unresolved findings.
7. **Schema validation:** Before returning, verify your YAML matches the schema
   above EXACTLY. If you have a `columns:` section, it must contain only
   `excluded:` and/or `fuzzy:` lists. No other keys.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Proofmark config: N strict, M fuzzy, K non-strict columns", "conditions": []}
```

## Constraints

- Default is strict. Every relaxation requires cited justification.
- Proofmark only supports `excluded` and `fuzzy` overrides. There is no
  `non_strict` classification. If you need to handle formatting differences,
  use `fuzzy` with an appropriate tolerance, or rely on strict and let the
  triage pipeline handle genuine mismatches.
- Known formatting differences from Python port:
  - Trailing zero suppression (`1.50` vs `1.5`)
  - Date format (`M/d/yyyy` vs `yyyy-MM-dd`)
  - Timestamp format (`10/8/2024 3:35:35 AM` vs `2024-10-08 03:35:35`)
  - Integer-as-float (`.0` suffix)
- When unsure, default to strict. Proofmark failures surface real issues
  for the triage pipeline.
- **If all columns are strict, do NOT include a `columns:` section at all.**
