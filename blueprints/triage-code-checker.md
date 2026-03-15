# Blueprint: triage-code-checker

**Stage:** Triage (T5)
**States:** Triage_CheckCode
**Outcome type:** SUCCESS (with clean/fault in body)

## Role

Check whether built code (job conf + external modules) correctly implements
the FSD. BRD and FSD may be correct (T3, T4 passed) but builder may have
implemented it wrong.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`

## Reads

**Process artifacts:**
- `{job_dir}/process/Triage_ProfileData.json`
- `{job_dir}/process/Triage_AnalyzeOgFlow.json`

**Product artifacts:**
- `{job_dir}/artifacts/triage/data-profile.md`
- `{job_dir}/artifacts/triage/og-flow-analysis.md`
- `{job_dir}/artifacts/fsd.md`
- `{job_dir}/artifacts/code/jobconf.json`
- `{job_dir}/artifacts/code/transforms/` (if applicable)

## Writes

### Process artifact (written on ALL outcomes)
- **File:** `{job_dir}/process/Triage_CheckCode.json`
- **Body:** `{ "outcome": "SUCCESS", "reason": "Code check complete — verdict: clean|fault", "conditions": [], "verdict": "clean|fault", "fault_reason": "...", "fault_location": "code/jobconf.json:module[2].sql", "confidence": "high|medium|low" }`

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST always write this file.

## Method

1. Read T1/T2 artifacts.
2. Read FSD and built artifacts.
3. Compare code against FSD module by module.
4. For failing columns, trace computation through actual code vs FSD spec.
5. Return `clean` or `fault`.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Code check complete — verdict: fault in transformation SQL", "conditions": []}
```

## Constraints

- Checking CODE against FSD. If FSD is wrong, that's T4's problem.
- Minor style differences = `clean`.
- Logic differences affecting output = `fault`.
