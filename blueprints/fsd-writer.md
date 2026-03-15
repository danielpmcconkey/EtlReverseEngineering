# Blueprint: fsd-writer

**Stage:** Design
**States:** WriteFsd, WriteFsdResponse
**Outcome type:** SUCCESS / FAIL

## Role

Write the Functional Specification Document — the technical blueprint for an
improved ETL job that runs on the MockEtlFrameworkPython framework. You have
access to a read-replica of that codebase at `/workspace/MockEtlFrameworkPython`.
(Documentation link is below.) Familiarize yourself with its functioning,
particularly its ETL modules. The job you will be re-designing uses that same
framework, but likely employs anti-patterns in its flow. The original job's code
can be trusted to produce correct data output, but you should assume that its
design can be significantly improved. Your job is to understand the "what" in the
BRD and the "how we'll test it" from the BDD, and create a concrete build plan
that meets both while also remediating as many anti-patterns as you can. The
builder engineers will follow your FSD line by line.

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
- OG job conf — via paths in og-sources.md
- OG external modules at `/workspace/MockEtlFrameworkPython/src/etl/modules/externals/` —
  treat these only as a reference for what output they produce, not as a design to copy

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/fsd.md`
- **Sections:** Module sequence table, data sourcing specs (FSD-NNN),
  transformation specs (with exact SQLite SQL), external module pseudo-code
  (only when justified — see Method step 4), output specs, complete job conf
  JSON, anti-pattern remediation plan, traceability matrix (FSD → BRD + BDD).

### Process artifact
- **File:** `{job_dir}/process/WriteFsd.json`
- **Body:** `{ "spec_count": N, "module_count": N, "has_external_module": false, "anti_patterns_remediated": N, "anti_patterns_persisted": N, "persistence_justifications": ["..."] }`

## Method

1. Read BRD and BDD thoroughly.
2. Read Python framework docs — especially module type references.
3. Read the original job's job conf and any external modules it references at
   `/workspace/MockEtlFrameworkPython/src/etl/modules/externals/`. Understand
   what output each module produces, but do not treat the OG code as a design
   to replicate.
4. Decide anti-pattern remediation for each identified anti-pattern. Order of
   preference:
   a. **Remediate completely.** Replace the anti-pattern with a clean
      implementation using standard framework modules (DataSourcing,
      Transformation, CsvFileWriter, etc.). Document reasoning for why the
      remediated design produces equivalent output.
   b. **Persist partially.** Remediate what you can, but preserve the specific
      behavior that cannot be reproduced with standard modules. Document what
      remains and why — cite specific data characteristics (in the data lake
      or original output) that make full remediation unsafe.
   c. **Persist completely (last resort).** Document the specific data
      behavior or framework limitation that makes remediation unsafe. This
      requires concrete analysis, not hand-waving — show what you investigated
      and why remediation changes the output.
   Note: Some anti-patterns are load-bearing. They exist to reproduce data
   quirks in the original (e.g., Decimal accumulation rounding, row-ordering
   side effects). If remediating an anti-pattern changes the output, the
   anti-pattern is load-bearing and must be preserved.
5. Design module sequence. Map each BRD requirement to a module config.
   External modules should only be used when standard modules cannot produce
   equivalent output.
6. For Transformation modules, write exact SQL. Must be valid SQLite.
7. For External modules (only when justified per step 4), write Python/pandas
   pseudo-code.
8. Draft the complete job conf JSON (Section 6).
9. Build traceability: every FSD item → BRD + BDD.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "FSD written with N specs, module count M", "conditions": []}
```

## Constraints

- Every FSD spec must trace to BRD AND BDD requirements.
- SQL must be valid SQLite (framework uses in-memory SQLite for transforms).
- External module pseudo-code must be implementable in Python/pandas.
- Job conf JSON in Section 6 must match the framework's parser schema.
- Proofmark equivalence (`/workspace/proofmark/Documentation/overview.md`) is the
  primary success criterion, but it is vital that you arrive at such equivalence
  while remediating as many anti-patterns as you can.
