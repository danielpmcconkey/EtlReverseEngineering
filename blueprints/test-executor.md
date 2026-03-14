# Blueprint: test-executor

**Stage:** Build
**States:** ExecuteUnitTests
**Outcome type:** SUCCESS / FAIL

## Role

Run the unit tests, capture results, and triage any failures. If all tests
pass, the job advances. If tests fail, diagnose whether the issue is in test
code, job code, or test environment. Do NOT fix — report.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`

## Reads

**Process artifacts:**
- `{job_dir}/process/ReviewUnitTests.json`

**Product artifacts:**
- `{job_dir}/artifacts/tests/test_{job_name}.py`
- `{job_dir}/artifacts/tests/test-plan.md`
- `{job_dir}/artifacts/code/` (job conf + modules)

## Writes

### Process artifact
- **File:** `{job_dir}/process/ExecuteUnitTests.json`
- **Body:** `{ "total": N, "passed": N, "failed": N, "errors": N, "failure_category": "none|test_bug|code_bug|environment" }`

No product artifact — test output captured in process JSON body and stdout.

## Method

1. Run tests:
   ```bash
   python -m pytest {job_dir}/artifacts/tests/test_{job_name}.py -v --tb=short 2>&1
   ```
2. Parse output: count passes, failures, errors.
3. For each failure: read traceback, categorize as test bug / code bug /
   environment issue.
4. Write process artifact.
5. Return SUCCESS if all pass, FAIL if any fail.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "All N tests passed", "conditions": []}
```
or
```json
{"outcome": "FAIL", "reason": "2 of 8 tests failed — code bug in transformation SQL (see process artifact)", "conditions": []}
```

## Constraints

- Do NOT fix anything. Run and report.
- Capture full pytest output in your stdout (above the outcome JSON block).
- If environment is broken (imports, dependencies), report as environment issue.
