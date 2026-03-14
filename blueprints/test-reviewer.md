# Blueprint: test-reviewer

**Stage:** Build / Build (FBR)
**States:** ReviewUnitTests, FBR_UnitTestCheck
**Outcome type:** APPROVED / CONDITIONAL / REJECTED

## Role

Verify unit tests correctly implement BDD scenarios with proper traceability,
concrete assertions, and sound test design.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `review_context`: `initial` | `fbr`

## Reads

**Process artifacts:**
- `{job_dir}/process/BuildUnitTests.json`

**Product artifacts:**
- `{job_dir}/artifacts/tests/test_{job_name}.py`
- `{job_dir}/artifacts/tests/test-plan.md`
- `{job_dir}/artifacts/bdd_specs/bdd.md`
- `{job_dir}/artifacts/code/` (built code)

## Writes

### Process artifact (only on APPROVED or CONDITIONAL)
- **File:** `{job_dir}/process/ReviewUnitTests.json` (or `FBR_UnitTestCheck.json`)
- **Body:** `{ "bdd_coverage_complete": true, "fixtures_match_bdd": true, "assertions_specific": true, "tests_independent": true }`

## Method

1. Read tests and test plan.
2. The test suite is capped at **10 tests** covering the most critical BDD
   scenarios. Do NOT reject for missing edge cases or incomplete scenario
   coverage. The test-plan.md documents which scenarios were intentionally
   skipped — that is expected and acceptable.
3. Verify the selected tests have correct fixtures matching BDD data and
   specific assertions testing BDD Then clauses.
4. Verify tests are independent and actually exercise the built code.
5. For FBR: verify tests match current BDD and code.

## stdout contract

```json
{"outcome": "APPROVED", "reason": "Full BDD coverage, all tests sound", "conditions": []}
```

## Verdict Criteria

- **APPROVED:** 10 or fewer well-chosen tests with correct fixtures and specific assertions.
- **CONDITIONAL:** Weak assertions or fixtures that don't match BDD data.
- **REJECTED:** Tests don't exercise built code, or critical happy-path scenarios are missing.
  Do NOT reject because fewer than all BDD scenarios are covered — the 10-test cap is by design.
