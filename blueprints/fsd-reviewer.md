# Blueprint: fsd-reviewer

**Stage:** Design / Build (FBR)
**States:** ReviewFsd, FBR_FsdCheck
**Outcome type:** APPROVED / CONDITIONAL / REJECTED

## Role

Verify the FSD is implementable, correctly traces to BRD and BDD, and will
produce output equivalent to the OG job.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `review_context`: `initial` | `fbr`

## Reads

**Process artifacts:**
- `{job_dir}/process/WriteFsd.json`

**Product artifacts:**
- `{job_dir}/artifacts/fsd.md`
- `{job_dir}/artifacts/brd.md`
- `{job_dir}/artifacts/bdd_specs/bdd.md`

**Source material:**
- Python framework docs at `{FW_DOCS}/`

For FBR, also:
- `{job_dir}/artifacts/code/jobconf.json`
- `{job_dir}/artifacts/code/transforms/` (if applicable)

## Writes

### Process artifact (only on APPROVED or CONDITIONAL)
- **File:** `{job_dir}/process/ReviewFsd.json` (or `FBR_FsdCheck.json`)
- **Body:** `{ "specs_checked": N, "traceability_complete": true, "sql_valid": true, "issues": [] }`

## Method

1. Verify traceability: every FSD item → BRD AND BDD. Flag orphans.
2. Verify implementation viability: valid SQLite SQL, correct module configs,
   implementable pseudo-code.
3. Verify job conf JSON is structurally valid.
4. Check anti-pattern decisions are justified.
5. For FBR: compare built artifacts against FSD, flag drift.

## stdout contract

```json
{"outcome": "APPROVED", "reason": "Full traceability, all specs implementable", "conditions": []}
```

## Verdict Criteria

- **APPROVED:** Full traceability, all specs implementable, JSON valid.
- **CONDITIONAL:** Minor — typo in SQL, missing property with obvious value.
- **REJECTED:** SQL won't parse, missing specs, broken traceability.
