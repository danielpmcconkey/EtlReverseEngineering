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

### Process artifact (only on APPROVED or CONDITIONAL)
- **File:** `{job_dir}/process/ReviewProofmarkConfig.json` (or `FBR_ProofmarkCheck.json`)
- **Body:** `{ "columns_covered": N, "columns_in_output": N, "relaxations_justified": true, "sort_deterministic": true }`

## Method

1. Read proofmark config and output inventory.
2. Verify every output column is in the config. Flag gaps.
3. For each non-strict/fuzzy rule: verify justification cites real evidence,
   tolerance is reasonable.
4. Check sort columns produce deterministic ordering.

## stdout contract

```json
{"outcome": "APPROVED", "reason": "All columns covered, relaxations justified", "conditions": []}
```

## Verdict Criteria

- **APPROVED:** All columns covered, relaxations justified, sort deterministic.
- **CONDITIONAL:** Missing column or weak justification.
- **REJECTED:** Multiple gaps, unjustified relaxations that mask real differences.
