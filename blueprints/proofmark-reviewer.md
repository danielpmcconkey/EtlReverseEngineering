# Blueprint: proofmark-reviewer

**Stage:** Build / Build (FBR)
**States:** ReviewProofmarkConfig, FBR_ProofmarkCheck
**Outcome type:** APPROVED / CONDITIONAL / REJECTED

## Role

Verify Proofmark config is sound: strict where it should be, relaxed only
where justified, complete for all output columns.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `review_context`: `initial` | `fbr`

## Reads

**Process artifacts:**
- `{job_dir}/process/BuildProofmarkConfig.json`

**Product artifacts:**
- `{job_dir}/artifacts/proofmark-config.yaml`
- `{job_dir}/artifacts/brd.md`
- `{job_dir}/artifacts/output-inventory.md`

## Writes

### Process artifact (written on ALL outcomes)
- **File:** `{job_dir}/process/ReviewProofmarkConfig.json` (or `FBR_ProofmarkCheck.json`)
- **Body:** `{ "outcome": "APPROVED|CONDITIONAL|REJECTED", "reason": "...", "conditions": [], "columns_covered": N, "columns_in_output": N, "relaxations_justified": true, "sort_deterministic": true }`

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST write this file on every outcome, including REJECTED.

## Required YAML Schema

The proofmark config MUST follow this exact structure. **Reject any config
that deviates.**

### Required fields

```yaml
comparison_target: "Human-readable name"
reader: csv       # or "parquet"
```

### Optional fields

```yaml
threshold: 100.0
csv:              # Only when reader: csv
  header_rows: 1
  trailer_rows: 0
  sort_columns:
    - column_name
```

### Column classifications

**All columns are STRICT by default.** There is no way to explicitly declare
strict — omit the column. Only `excluded` and `fuzzy` overrides exist.

If all columns are strict, the `columns:` section must be **omitted entirely**.

```yaml
columns:
  excluded:
    - name: column_name
      reason: "..."
  fuzzy:
    - name: column_name
      tolerance: 0.01
      tolerance_type: absolute    # or "relative"
      reason: "..."
```

### Immediate REJECT for schema violations

- Per-column dicts like `column_name: { match: strict }` — REJECT
- Per-column dicts like `column_name: { rule: strict }` — REJECT
- A `strict:` list under `columns:` — REJECT
- Any key under `columns:` other than `excluded` and `fuzzy` — REJECT
- Missing `name:` or `reason:` on any excluded/fuzzy entry — REJECT
- Missing `tolerance:` or `tolerance_type:` on fuzzy entries — REJECT
- `reader` value that is not `"csv"` or `"parquet"` — REJECT

## Method

1. **Schema check first.** Read the proofmark config YAML. Before evaluating
   content, verify it matches the schema above exactly. If the structure is
   wrong, REJECT immediately with the specific violation. Do not evaluate
   column coverage or justifications on a malformed config.
2. Read output inventory for the complete column list.
3. Verify every output column is accounted for (either implicitly strict or
   explicitly listed under excluded/fuzzy). Flag gaps.
4. For each fuzzy rule: verify justification cites real evidence and tolerance
   is reasonable.
5. For each excluded rule: verify the column genuinely cannot be compared.
6. Check sort columns produce deterministic ordering.

## stdout contract

```json
{"outcome": "APPROVED", "reason": "All columns covered, relaxations justified", "conditions": []}
```

## Verdict Criteria

- **APPROVED:** Valid schema, all columns covered, relaxations justified, sort deterministic.
- **CONDITIONAL:** Valid schema but missing column or weak justification.
- **REJECTED:** Invalid schema structure, multiple gaps, or unjustified relaxations that mask real differences.
