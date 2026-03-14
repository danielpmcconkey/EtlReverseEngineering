# Blueprint: test-executor

**Stage:** Build
**States:** ExecuteUnitTests
**Outcome type:** SUCCESS / FAIL

## Role

Run the unit tests, capture results, and if tests fail, attempt to diagnose
and fix the issue. You get a leash of 3 fix-and-retry attempts. If you can't
get all tests passing in 3 attempts, return FAIL for human review.

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
- **Body:** `{ "total": N, "passed": N, "failed": N, "errors": N, "attempts": N, "fixes_applied": ["description of fix 1", ...] }`

Updates to product artifacts (if fixes applied):
- `{job_dir}/artifacts/tests/test_{job_name}.py` (if test bug)
- `{job_dir}/artifacts/code/jobconf.json` or `transforms/` (if code bug)

## Method

1. **Run tests:**
   ```bash
   python -m pytest {job_dir}/artifacts/tests/test_{job_name}.py -v --tb=short 2>&1
   ```
2. **If all pass:** Write process artifact, return SUCCESS. Done.
3. **If any fail:** Diagnose each failure:
   a. Read the traceback.
   b. Categorize: test bug (fixture or assertion error), code bug
      (transformation produces wrong result), or environment issue.
4. **Attempt fix (up to 3 attempts total):**
   a. If **test bug:** Fix the test code. Re-run.
   b. If **code bug:** Fix the job conf SQL or external module. Re-run.
   c. If **environment issue:** Cannot fix. Return FAIL immediately.
   d. Log what you changed and why.
5. **After each fix:** Re-run the full test suite. If all pass, SUCCESS.
   If failures remain, attempt next fix (up to 3 total).
6. **After 3 failed attempts:** Return FAIL with full diagnostic details.
   Include all fix attempts and their results so a human can pick up
   where you left off.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "All 8 tests passed (after 1 fix: corrected typo in SQL column name)", "conditions": []}
```
or
```json
{"outcome": "FAIL", "reason": "3 fix attempts exhausted — 2 tests still failing. Root cause appears to be date filtering logic mismatch. See process artifact for fix history.", "conditions": []}
```

## Constraints

- **3 attempts maximum.** Do not exceed this. After 3, return FAIL regardless.
- Keep fixes minimal and targeted. Don't rewrite the entire job — fix the
  specific failing logic.
- Log every fix attempt: what you changed, why, and the test result after.
- If the fix requires understanding you don't have (e.g., the BRD or FSD
  seems wrong), return FAIL with that diagnosis — don't guess.
- Capture full pytest output in your stdout for every run.
