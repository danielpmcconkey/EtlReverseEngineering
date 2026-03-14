# Blueprint: test-writer

**Stage:** Build
**States:** BuildUnitTests, BuildUnitTestsResponse
**Outcome type:** SUCCESS / FAIL

## Role

Write unit tests implementing the BDD scenarios. Each test exercises a specific
behavior with concrete fixture data. When invoked as BuildUnitTestsResponse,
rewrite incorporating reviewer feedback.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `rejection_reason`: (BuildUnitTestsResponse only)
- `rejection_conditions`: (BuildUnitTestsResponse only)

## Reads

**Process artifacts:**
- `{job_dir}/process/ReviewProofmarkConfig.json`

**Product artifacts:**
- `{job_dir}/artifacts/bdd_specs/bdd.md`
- `{job_dir}/artifacts/fsd.md`
- `{job_dir}/artifacts/code/jobconf.json`
- `{job_dir}/artifacts/code/transforms/` (if applicable)

**Source material:**
- Existing tests at `/workspace/MockEtlFrameworkPython/tests/` — patterns only
- Framework docs at `{FW_DOCS}/testing.md`

## Writes

### Product artifacts
- **Test file:** `{job_dir}/artifacts/tests/test_{job_name}.py`
- **Test plan:** `{job_dir}/artifacts/tests/test-plan.md` — BDD-to-test mapping

### Process artifact
- **File:** `{job_dir}/process/BuildUnitTests.json`
- **Body:** `{ "test_count": N, "bdd_scenarios_covered": N, "bdd_scenarios_total": N, "fixtures": ["standard_data", "empty_input"] }`

## Method

1. Read BDD scenarios and fixture definitions.
2. Read FSD for implementation details.
3. Read existing test files for project testing patterns.
4. For each BDD scenario:
   a. Create descriptive test function with BDD ID in docstring.
   b. Set up fixtures per BDD specification.
   c. Execute transformation logic.
   d. Assert expected outcomes per BDD Then clause.
5. Write test-plan.md mapping tests to BDD scenarios.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Wrote N tests covering all BDD scenarios", "conditions": []}
```

## Constraints

- Every test docstring must reference its BDD scenario ID.
- Use exact fixture data from BDD — don't invent different test data.
- Tests exercise transformation logic, not framework I/O.
- Tests go in `{job_dir}/artifacts/tests/`, not MockEtlFrameworkPython.
- No shared mutable state between tests.
