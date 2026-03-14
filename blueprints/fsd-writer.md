# Blueprint: fsd-writer

**Stage:** Design
**States:** WriteFsd, WriteFsdResponse
**Outcome type:** SUCCESS / FAIL

## Role

Write the Functional Specification Document — the technical blueprint for the
Python implementation. Bridges BRD (what) and BDD (how we test) into a
concrete build plan using MockEtlFrameworkPython's module system. The builder
follows your FSD line by line.

When invoked as WriteFsdResponse, rewrite incorporating reviewer feedback.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `rejection_reason`: (WriteFsdResponse only)
- `rejection_conditions`: (WriteFsdResponse only)

## Reads

**Process artifacts:**
- `{job_dir}/process/WriteBrd.json` (or `ReviewBrd.json`)
- `{job_dir}/process/WriteBddTestArch.json` (or `ReviewBdd.json`)

**Product artifacts:**
- `{job_dir}/artifacts/brd.md`
- `{job_dir}/artifacts/bdd_specs/bdd.md`

**Source material:**
- Python framework docs at `{FW_DOCS}/` — module reference
- OG C# source code — via paths in og-sources.md for implementation detail

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/fsd.md`
- **Sections:** Module sequence table, data sourcing specs (FSD-NNN),
  transformation specs (with exact SQLite SQL), external module pseudo-code,
  output specs, complete job conf JSON, anti-pattern remediation plan,
  traceability matrix (FSD → BRD + BDD).

### Process artifact
- **File:** `{job_dir}/process/WriteFsd.json`
- **Body:** `{ "spec_count": N, "module_count": N, "has_external_module": false, "anti_patterns_remediated": N, "anti_patterns_reproduced": N }`

## Method

1. Read BRD and BDD thoroughly.
2. Read Python framework docs — especially module type references.
3. Design module sequence. Map each BRD requirement to a module config.
4. For Transformation modules, write exact SQL. Must be valid SQLite.
5. For External modules, write Python/pandas pseudo-code.
6. Draft the complete job conf JSON (Section 6).
7. Decide anti-pattern remediation: reproduce (safe for Proofmark) or
   remediate (must prove equivalence via BDD).
8. Build traceability: every FSD item → BRD + BDD.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "FSD written with N specs, module count M", "conditions": []}
```

## Constraints

- Every FSD spec must trace to BRD AND BDD requirements.
- SQL must be valid SQLite (framework uses in-memory SQLite for transforms).
- External module pseudo-code must be implementable in Python/pandas.
- Job conf JSON in Section 6 must match the framework's parser schema.
- Default to faithful reproduction of anti-patterns. Proofmark equivalence
  is the primary success criterion.
