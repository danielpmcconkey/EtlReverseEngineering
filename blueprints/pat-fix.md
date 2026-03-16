# Blueprint: pat-fix

**Stage:** Validate (response to FBR_EvidenceAudit CONDITIONAL)
**Outcome type:** SUCCESS / FAIL

## Role

Pat (the evidence auditor) approved the job conditionally. The Proofmark
results are clean — the code works. But the evidence chain has drift:
documentation, tests, or artifacts don't match the deployed code because
triage or ExecuteJobRuns rewrote the implementation without updating
upstream artifacts.

Your job is to resolve every fatal finding and concern Pat identified.
This is mechanical work — Pat's findings are specific. Trust them.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`

## Reads

**Your primary input:**
- `{job_dir}/process/FBR_EvidenceAudit.json` — Pat's findings. Read this FIRST.
  The `fatal_findings` array is your checklist. The `concerns` array has
  secondary issues that should also be addressed where possible.

**Deployed code (ground truth):**
- `/workspace/MockEtlFrameworkPython/RE/Jobs/{job_name}_re/jobconf.json`
  (or similar path — check the Publish process artifact for the actual
  deployed location)
- `/workspace/MockEtlFrameworkPython/RE/externals/` — deployed external
  modules (if any)

**Job artifacts (what you're fixing):**
- `{job_dir}/artifacts/fsd.md` — Functional Specification Document
- `{job_dir}/artifacts/code/jobconf.json` — artifact job configuration
- `{job_dir}/artifacts/code/*.py` — artifact external modules
- `{job_dir}/artifacts/tests/` — unit tests
- `{job_dir}/artifacts/brd.md` — Business Requirements Document
- `{job_dir}/artifacts/bdd_specs/` — BDD test specifications
- `{job_dir}/artifacts/proofmark-config.yaml` — Proofmark configuration
- `{job_dir}/process/Publish.json` — deployment details

## Method

1. Read Pat's `FBR_EvidenceAudit.json`. Every fatal finding is a mandatory
   fix. Every concern should be addressed if feasible.

2. Read the **deployed jobconf** to understand what's actually running.
   This is ground truth. Everything else aligns to this.

3. For each finding, determine what needs to change. Common patterns:
   - **FSD describes architecture that doesn't exist:** Update FSD to
     match deployed code. Remove references to dead modules. Update
     module sequence, SQL specs, traceability matrix.
   - **Artifact jobconf doesn't match deployed:** Copy deployed jobconf
     to `{job_dir}/artifacts/code/jobconf.json`.
   - **Unit tests validate dead code:** Rewrite tests against the actual
     deployed SQL. Load SQL from jobconf at import time so tests can't
     drift. Remove imports of dead external modules.
   - **Stale anti-pattern documentation:** Update AP remediation status
     to reflect what actually happened.
   - **Stale review process artifacts:** Note in your summary but don't
     fabricate new review artifacts.

4. Run unit tests:
   ```
   cd /workspace/EtlReverseEngineering && python -m pytest {job_dir}/artifacts/tests/ -v
   ```

5. If all tests pass, write your process artifact with outcome SUCCESS.
   If tests fail or a finding is truly unfixable, write FAIL.

## Writes

### Process artifact (written on ALL outcomes)
- **File:** `{job_dir}/process/PatFix.json`
- **Body:**
  ```json
  {
    "outcome": "SUCCESS|FAIL",
    "reason": "...",
    "conditions": [],
    "findings_resolved": ["F1: ...", "F2: ..."],
    "concerns_resolved": ["C1: ..."],
    "files_modified": ["fsd.md", "jobconf.json", "tests/..."],
    "unit_test_results": "N passed, M failed"
  }
  ```

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "All N fatal findings resolved, M concerns addressed, K/K unit tests pass", "conditions": []}
```

## Constraints

- **Trust Pat's findings.** The evidence chain issues are real. Fix them.
- **The deployed code is ground truth.** Align everything to it. Never
  modify deployed code.
- **Load SQL from jobconf in tests.** This is the #1 cause of drift —
  tests with hardcoded SQL constants that don't match deployed code.
  Always load from the artifact jobconf at import time.
- **Don't test dead code.** If an External module isn't referenced by
  the deployed jobconf, don't write tests for it. Note it as dead code.
- **Update everything your changes invalidate.** If you change the FSD
  module sequence, update the traceability matrix. If you update AP
  remediation status, update the relevant FSD section.
- **Write to artifacts, not deployed paths.** The pipeline handles
  deployment.
