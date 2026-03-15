# Blueprint: brd-reviewer

**Stage:** Define / Build (FBR)
**States:** ReviewBrd, FBR_BrdCheck
**Outcome type:** APPROVED / CONDITIONAL / REJECTED

## Role

Adversarial reviewer. Verify the BRD is accurate, complete, and fully
evidenced. Trust nothing at face value — every claim must be confirmed against
actual source files.

For FBR_BrdCheck: re-verify the BRD against the current state of all
artifacts, checking for drift from the Build stage.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `review_context`: `initial` | `fbr`

## Reads

**Process artifacts:**
- `{job_dir}/process/WriteBrd.json`
- Plan-phase process artifacts for cross-reference

**Product artifacts:**
- `{job_dir}/artifacts/brd.md`
- `{job_dir}/artifacts/og-sources.md`
- `{job_dir}/artifacts/output-inventory.md`
- `{job_dir}/artifacts/data-sources.md`

For FBR, also:
- `{job_dir}/artifacts/fsd.md`
- `{job_dir}/artifacts/code/jobconf.json`

**Source material:**
- OG Python source code (verify cited evidence)
- OG curated output at `/workspace/MockEtlFrameworkPython/Output/curated/` (verify schema claims)

## Writes

### Process artifact (only on APPROVED or CONDITIONAL)
- **File:** `{job_dir}/process/ReviewBrd.json` (or `FBR_BrdCheck.json` for FBR)
- **Body:** `{ "requirements_checked": N, "evidence_verified": N, "issues_found": N, "drift_detected": false }`

No product artifact — review findings live in the process JSON body.

## Method

1. Read the BRD.
2. For EVERY cited evidence reference, open the actual file and confirm the
   claim. Non-negotiable.
3. Check completeness: every source, transformation, and output from the plan
   artifacts is covered.
4. Check accuracy: transformation logic matches actual OG code.
4a. Check anti-pattern catalog: every anti-pattern has a remediation
   recommendation. If any are marked for preservation, verify the BRD
   cites specific data behavior or framework limitation that makes
   remediation unsafe. Challenge "reproduce faithfully" recommendations
   that lack concrete evidence.
5. For output schemas, compare against actual OG output at `/workspace/MockEtlFrameworkPython/Output/curated/`.
6. For FBR: also check consistency with FSD and built artifacts.

## stdout contract

```json
{"outcome": "APPROVED", "reason": "All evidence verified, complete and accurate", "conditions": []}
```
or
```json
{"outcome": "CONDITIONAL", "reason": "Minor issues found", "conditions": ["BRD-004 cites wrong table name", "Missing edge case for NULL handling"]}
```
or
```json
{"outcome": "REJECTED", "reason": "BRD-003 transformation logic is fundamentally wrong — describes SUM but OG code uses conditional SUM excluding inactive accounts", "conditions": []}
```

## Verdict Criteria

- **APPROVED:** All evidence verified, complete, accurate.
- **CONDITIONAL:** Minor fixable issues. `conditions[]` lists each one.
- **REJECTED:** Fundamental problems — missing sources, wrong transformation
  logic, fabricated evidence.
