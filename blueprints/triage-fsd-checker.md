# Blueprint: triage-fsd-checker

**Stage:** Triage (T4)
**States:** Triage_CheckFsd
**Outcome type:** SUCCESS (with clean/fault in body)

## Role

Check whether the FSD correctly specifies the implementation needed to
reproduce the OG data flow. BRD may be correct (T3 passed) but FSD may
have mistranslated requirements into wrong technical spec.

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
- `{job_dir}/artifacts/brd.md`

## Writes

### Process artifact
- **File:** `{job_dir}/process/Triage_CheckFsd.json`
- **Body:** `{ "verdict": "clean|fault", "fault_reason": "...", "faulty_specs": ["FSD-003"], "confidence": "high|medium|low" }`

## Method

1. Read T1/T2 artifacts.
2. Read FSD, focusing on specs for failing columns/rows.
3. Trace failing data through FSD specifications — would the FSD-specified
   transformations produce the correct output?
4. Return `clean` or `fault`.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "FSD check complete — verdict: clean", "conditions": []}
```

## Constraints

- Checking FSD against BRD requirements and OG reality.
- Different SQL syntax that produces same result = `clean`.
- LEFT JOIN where BRD requires INNER JOIN = `fault` (if output differs).
- FSD SQL must be valid SQLite — Postgres-only syntax is a `fault`.
