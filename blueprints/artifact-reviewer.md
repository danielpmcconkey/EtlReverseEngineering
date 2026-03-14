# Blueprint: artifact-reviewer

**Stage:** Build / Build (FBR)
**States:** ReviewJobArtifacts, FBR_ArtifactCheck
**Outcome type:** APPROVED / CONDITIONAL / REJECTED

## Role

Verify built job conf and external modules correctly implement every FSD
specification. Read actual code and check it against the spec — structurally
and logically.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `review_context`: `initial` | `fbr`

## Reads

**Process artifacts:**
- `{job_dir}/process/BuildJobArtifacts.json`

**Product artifacts:**
- `{job_dir}/artifacts/fsd.md`
- `{job_dir}/artifacts/code/jobconf.json`
- `{job_dir}/artifacts/code/transforms/` (if applicable)

**Source material:**
- Python framework docs at `{FW_DOCS}/`

## Writes

### Process artifact (only on APPROVED or CONDITIONAL)
- **File:** `{job_dir}/process/ReviewJobArtifacts.json` (or `FBR_ArtifactCheck.json`)
- **Body:** `{ "json_valid": true, "module_count_matches": true, "sql_correct": true, "fsd_compliance": "full", "issues": [] }`

## Method

1. Read the FSD and the built artifacts.
2. Verify job conf: valid JSON, module count/sequence matches FSD, each
   module's properties match FSD specification.
3. Verify Transformation SQL is valid SQLite.
4. If external modules exist: verify they follow `execute(shared_state)`
   interface, logic matches FSD pseudo-code, pandas usage is correct.
5. Cross-reference build process artifact's FSD compliance claim.

## stdout contract

```json
{"outcome": "APPROVED", "reason": "All FSD items correctly implemented", "conditions": []}
```

## Verdict Criteria

- **APPROVED:** All FSD items implemented correctly, valid JSON, clean code.
- **CONDITIONAL:** Minor — typo in column name, missing property with obvious value.
- **REJECTED:** Wrong SQL logic, missing modules, JSON won't parse.
