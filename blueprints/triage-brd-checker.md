# Blueprint: triage-brd-checker

**Stage:** Triage (T3)
**States:** Triage_CheckBrd
**Outcome type:** SUCCESS (with clean/fault in body)

## Role

Check whether the BRD correctly describes the OG data flow identified by T2.
If the BRD is wrong, everything downstream is built on a faulty spec.

Note: This agent always returns SUCCESS — the triage outcome (clean vs fault)
goes in the process artifact body for the routing logic in T7.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`

## Reads

**Process artifacts:**
- `{job_dir}/process/Triage_ProfileData.json`
- `{job_dir}/process/Triage_AnalyzeOgFlow.json`

**Product artifacts:**
- `{job_dir}/artifacts/triage/data-profile.md`
- `{job_dir}/artifacts/triage/og-flow-analysis.md`
- `{job_dir}/artifacts/brd.md`

## Writes

### Process artifact
- **File:** `{job_dir}/process/Triage_CheckBrd.json`
- **Body:** `{ "verdict": "clean|fault", "fault_reason": "BRD-004 describes SUM but OG uses conditional SUM", "faulty_requirements": ["BRD-004"], "confidence": "high|medium|low" }`

No product artifact — findings live in process JSON.

## Method

1. Read data profile (T1) and OG flow analysis (T2).
2. Read BRD.
3. If T2 found significant findings: check BRD against T2 findings.
4. If T2 found nothing notable: use data profile to step through BRD
   requirements for failing columns.
5. Return `clean` if BRD accurately describes OG behavior.
   Return `fault` if BRD is incorrect in a way that caused wrong code.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "BRD check complete — verdict: clean", "conditions": []}
```

## Constraints

- Checking BRD against OG REALITY (via T2), not against RE implementation.
- Only `fault` for substantive inaccuracies that lead to wrong code.
- Be specific: "BRD-004 says SUM but T2 shows conditional SUM excluding
  inactive accounts."
