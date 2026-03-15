# Blueprint: triage-pm-checker

**Stage:** Triage (T6)
**States:** Triage_CheckProofmark
**Outcome type:** SUCCESS (with clean/fault in body)

## Role

Check whether the Proofmark config itself is causing false failures. Only
meaningful when T3-T5 all came back clean. If the pipeline correctly implements
a correct spec, the comparison rules must be wrong.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`

## Reads

**Process artifacts:**
- `{job_dir}/process/Triage_ProfileData.json`
- `{job_dir}/process/Triage_CheckBrd.json`
- `{job_dir}/process/Triage_CheckFsd.json`
- `{job_dir}/process/Triage_CheckCode.json`

**Product artifacts:**
- `{job_dir}/artifacts/triage/data-profile.md`
- `{job_dir}/artifacts/proofmark-config.yaml`
- `{job_dir}/artifacts/brd.md`
- `{job_dir}/artifacts/output-inventory.md`

## Writes

### Process artifact (written on ALL outcomes)
- **File:** `{job_dir}/process/Triage_CheckProofmark.json`
- **Body:** `{ "outcome": "SUCCESS", "reason": "Proofmark config check — verdict: clean|fault", "conditions": [], "verdict": "clean|fault", "fault_reason": "column 'balance' should be fuzzy(0.01) not strict — trailing zero formatting difference", "recommended_fix": "change 'balance' from strict to fuzzy with tolerance 0.01", "confidence": "high|medium|low" }`

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST always write this file.

## Method

1. Read data profile for specific mismatches.
2. Read proofmark config.
3. For each failing column:
   a. Check configured match rule.
   b. Examine actual OG vs RE values from data profile.
   c. Determine if difference is formatting/precision that the rule should
      accommodate.
4. Check sort columns for deterministic ordering.
5. Check column completeness.
6. Return `clean` or `fault`.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Proofmark config check — verdict: fault, strict column should be fuzzy", "conditions": []}
```

## Constraints

- Only `fault` if you can clearly show the config is wrong.
- If data profile shows genuine logic differences, config is probably correct
  — return `clean` (upstream checks missed something).
- Recommended fix must be specific: "change 'balance' from strict to fuzzy
  with tolerance 0.01."
