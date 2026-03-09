# Requirements: ETL Reverse Engineering

**Defined:** 2026-03-09
**Core Value:** Output is king. Every RE'd job must produce byte-identical output across all 92 effective dates.

## v1 Requirements

### Per-Job Deliverables

- [ ] **DELIV-01**: BRD with numbered requirements and evidence citing original code/data
- [ ] **DELIV-02**: FSD with numbered specs, traceability to BRD numbers, evidence for each spec
- [ ] **DELIV-03**: Test strategy with traceability to FSD/BRD numbers
- [ ] **DELIV-04**: `_re` JSON job conf based on FSD, anti-patterns remediated
- [ ] **DELIV-05**: External modules created ONLY when standard modules can't match output (FSD must cite evidence)
- [ ] **DELIV-06**: Output manifesto listing every output (some jobs produce multiple)
- [ ] **DELIV-07**: Proofmark config YAML per output with evidence for any non-strict column matching
- [ ] **DELIV-08**: 92/92 Proofmark PASS across all effective dates

### Process

- [ ] **PROC-01**: Zero human input after planning — fully autonomous execution
- [ ] **PROC-02**: Proofmark failure triggers triage → RCA → fix → doc update → retry (max 5 attempts)
- [ ] **PROC-03**: Iterative learning — early tier results refine approach for later tiers

### Anti-Pattern Remediation

- [ ] **ANTI-01**: Every job assessed against all 10 anti-patterns (AP1–AP10)
- [ ] **ANTI-02**: AP3 (Unnecessary External Module) — SQL-first, external modules justified with evidence
- [ ] **ANTI-03**: AP6 (Row-by-Row Iteration) — C# foreach converted to SQL set operations where possible

### Completion

- [ ] **COMP-01**: Tier 1 complete — 3 trivial jobs (pipeline validation)
- [ ] **COMP-02**: Tier 2 complete — 10 simple multi-source jobs
- [ ] **COMP-03**: Tier 3 complete — 13 Append mode jobs
- [ ] **COMP-04**: Tier 4 complete — ~67 external module jobs
- [ ] **COMP-05**: Tier 5 complete — 6 external module + Append jobs
- [ ] **COMP-06**: Tier 6 complete — 4 boss-level jobs

## v2 Requirements

None — this project has a fixed scope of 105 jobs. Future work is a separate production prototype.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Modifying ETL Framework code | Read-only access; we work within its constraints |
| Modifying V1 job confs or output | Those are the source of truth |
| Performance optimization beyond anti-pattern remediation | Matching output is the goal, not beating it |
| Fixing upstream data quality issues | We reproduce what exists, warts and all |
| Production prototype blueprint | Nice side effect, not a deliverable. Artifacts should be reusable but that's not a gate. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (populated by roadmapper) | | |

**Coverage:**
- v1 requirements: 17 total
- Mapped to phases: 0
- Unmapped: 17 ⚠️

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after initial definition*
