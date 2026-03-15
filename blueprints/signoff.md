# Blueprint: signoff

**Stage:** Validate
**States:** FinalSignOff
**Outcome type:** APPROVED / FAIL

## Role

Final quality gate. Review the complete evidence trail from plan through
validation. Either sign off the job as COMPLETE or flag remaining concerns.
Last stop before the job is declared done.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`

## Reads

**Process artifacts:** ALL process JSONs in `{job_dir}/process/`

**Product artifacts:**
- `{job_dir}/artifacts/og-sources.md`
- `{job_dir}/artifacts/output-inventory.md`
- `{job_dir}/artifacts/data-sources.md`
- `{job_dir}/artifacts/dependencies.md`
- `{job_dir}/artifacts/brd.md`
- `{job_dir}/artifacts/bdd_specs/bdd.md`
- `{job_dir}/artifacts/fsd.md`
- `{job_dir}/artifacts/proofmark-config.yaml`
- `{job_dir}/artifacts/proofmark-results.md`

**Source material:**
- OG output at `/workspace/MockEtlFrameworkPython/Output/curated/` — for spot-checks
- RE output — for spot-checks

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/final-signoff.md`
- **Content:** Proofmark summary, non-strict column justification review,
  fuzzy match spot-check (actual values from real files), anti-pattern summary,
  artifact trail completeness, final assessment.

### Process artifact (written on ALL outcomes — APPROVED and FAIL)
- **File:** `{job_dir}/process/FinalSignOff.json`
- **Body:** `{ "outcome": "APPROVED|FAIL", "reason": "...", "conditions": [], "proofmark_pass_rate": "100%", "non_strict_columns_justified": true, "fuzzy_columns_spot_checked": true, "artifact_trail_complete": true, "verdict": "COMPLETE" }`

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST write this file even on FAIL.

## Method

1. Read Proofmark results. Confirm all dates pass on a single artifact version.
2. Review each non-strict Proofmark column — confirm justification is valid.
3. For each fuzzy column: read actual OG and RE output files for 3 sample
   dates. Compare values manually. Verify differences are precision-related.
4. Review BRD anti-patterns — verify each was either remediated or retained
   with concrete justification. Remediation is the expected default; retention
   requires evidence that remediation would change output.
5. Check artifact trail: every required artifact exists, every review APPROVED.
6. Write sign-off.

## stdout contract

```json
{"outcome": "APPROVED", "reason": "All checks pass — job signed off as COMPLETE", "conditions": []}
```
or
```json
{"outcome": "FAIL", "reason": "BLOCKED: fuzzy column 'balance' shows non-precision difference on Oct 15", "conditions": []}
```

## Constraints

- Do NOT rubber-stamp. If something looks off, flag it.
- Spot-check fuzzy columns by reading ACTUAL files — don't trust Proofmark's
  "within tolerance" without verifying the tolerance is appropriate.
- If triage cycles occurred, review triage artifacts for soundness of fixes.
