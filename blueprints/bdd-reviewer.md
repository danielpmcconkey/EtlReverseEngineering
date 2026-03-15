# Blueprint: bdd-reviewer

**Stage:** Design / Build (FBR)
**States:** ReviewBdd, FBR_BddCheck
**Outcome type:** APPROVED / CONDITIONAL / REJECTED

## Role

Verify the BDD test architecture has complete, traceable coverage of BRD
requirements with concrete, testable scenarios.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `review_context`: `initial` | `fbr`

## Reads

**Process artifacts:**
- `{job_dir}/process/WriteBddTestArch.json`

**Product artifacts:**
- `{job_dir}/artifacts/bdd_specs/bdd.md`
- `{job_dir}/artifacts/brd.md`

For FBR, also:
- `{job_dir}/artifacts/fsd.md`
- `{job_dir}/artifacts/tests/` (built unit tests)

## Writes

### Process artifact (written on ALL outcomes)
- **File:** `{job_dir}/process/ReviewBdd.json` (or `FBR_BddCheck.json`)
- **Body:** `{ "outcome": "APPROVED|CONDITIONAL|REJECTED", "reason": "...", "conditions": [], "brd_requirements_total": N, "brd_requirements_covered": N, "scenarios_concrete": true, "gaps": [] }`

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST write this file on every outcome, including REJECTED.

## Method

1. Read BDD and BRD. List every BRD requirement ID.
2. Check traceability: every BRD ID in at least one BDD scenario. Flag gaps.
3. Verify each scenario is concrete and testable — specific fixture values,
   measurable expected outcomes.
4. Check edge case coverage: empty inputs, NULLs, boundaries.
4a. If the BRD marks anti-patterns for remediation, verify the BDD tests
   the remediated behavior, not the original anti-pattern behavior. If the
   BRD marks an anti-pattern as load-bearing, verify the BDD tests the
   current behavior with a note explaining why.
5. For FBR: verify BDD matches current BRD and built tests implement scenarios.

## stdout contract

```json
{"outcome": "APPROVED", "reason": "Full coverage, all scenarios concrete", "conditions": []}
```

## Verdict Criteria

- **APPROVED:** Full BRD coverage, all scenarios concrete and testable.
- **CONDITIONAL:** Minor gaps — missing edge case, vague fixture.
- **REJECTED:** Major BRD requirements have no coverage, or scenarios untestable.
