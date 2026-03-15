# Blueprint: bdd-writer

**Stage:** Design
**States:** WriteBddTestArch, WriteBddResponse
**Outcome type:** SUCCESS / FAIL

## Role

Write the BDD test architecture. Your scenarios define acceptance criteria
the implementation must satisfy. Tests drive the spec — the FSD writer will
use your scenarios as requirements.

When invoked as WriteBddResponse, rewrite incorporating reviewer feedback.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `rejection_reason`: (WriteBddResponse only)
- `rejection_conditions`: (WriteBddResponse only)

## Reads

**Process artifacts:**
- `{job_dir}/process/WriteBrd.json` (or `ReviewBrd.json` for context)

**Product artifacts:**
- `{job_dir}/artifacts/brd.md`

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/bdd_specs/bdd.md`
- **Sections:** Numbered Given/When/Then scenarios (BDD-001, ...), data fixtures
  with concrete values, edge cases, negative cases, traceability matrix
  (every BRD requirement mapped to at least one scenario).

### Process artifact
- **File:** `{job_dir}/process/WriteBddTestArch.json`
- **Body:** `{ "scenario_count": N, "brd_coverage": "complete", "edge_cases": N, "fixture_tables": ["customers", "accounts"] }`

## Method

1. Read the BRD. Understand every numbered requirement.
2. For each BRD requirement, write at least one Given/When/Then scenario.
3. Design data fixtures — small, deterministic. Concrete values, not placeholders.
   "3 customers with IDs 1, 2, 3" not "some customers."
4. Write edge cases: empty tables, NULLs, boundary dates, single rows.
5. Write negative cases: malformed or missing data.
6. Build traceability matrix. Verify every BRD requirement has coverage.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "BDD written with N scenarios covering all BRD requirements", "conditions": []}
```

## Constraints

- Every scenario must trace to a BRD requirement via `[BRD-NNN]`.
- Fixtures must be concrete: actual values, actual row counts.
- Scenarios test BEHAVIOR, not implementation. Don't specify SQL.
- If the BRD documents a load-bearing anti-pattern (one where remediation
  would change output), test the current behavior — that behavior is correct
  for equivalence purposes. If the BRD marks an anti-pattern for remediation,
  test the remediated behavior. The BDD tests what the RE job SHOULD do, which
  may differ from what the OG job does when anti-patterns are being fixed.
