# Roadmap: ETL Reverse Engineering

## Overview

Reverse engineer 105 production ETL jobs across 6 complexity tiers, starting with 3 trivial jobs to validate the full pipeline, then escalating through multi-source joins, Append mode, external module conversion, combined challenges, and boss-level complexity. Each phase establishes or extends patterns that inform subsequent phases. The per-job deliverable workflow and anti-pattern remediation process are established in Phase 1 and applied uniformly from that point forward.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Tier 1 - Pipeline Validation** - Establish full RE workflow on 3 trivial jobs; validate all deliverables and tooling end-to-end
- [ ] **Phase 2: Tier 2 - Simple Multi-Source** - Scale to 10 jobs with multi-source joins; prove batch execution works
- [ ] **Phase 3: Tier 3 - Append Mode** - 13 Append mode jobs requiring chronological date execution and cumulative output validation
- [ ] **Phase 4: Tier 4 - External Module Conversion** - The bulk: ~67 jobs requiring C# analysis and SQL-first conversion
- [ ] **Phase 5: Tier 5 - External + Append** - 6 jobs combining external module conversion with Append mode constraints
- [ ] **Phase 6: Tier 6 - Boss Level** - 4 high-complexity jobs with high data source counts and complex logic

## Phase Details

### Phase 1: Tier 1 - Pipeline Validation
**Goal**: The full RE workflow is proven end-to-end on the simplest possible jobs, producing a repeatable pattern for all subsequent phases
**Depends on**: Nothing (first phase)
**Requirements**: DELIV-01, DELIV-02, DELIV-03, DELIV-04, DELIV-05, DELIV-06, DELIV-07, DELIV-08, PROC-01, PROC-02, PROC-03, ANTI-01, ANTI-02, ANTI-03, COMP-01
**Success Criteria** (what must be TRUE):
  1. All 3 Tier 1 jobs (BranchDirectory, ComplianceResolutionTime, OverdraftFeeSummary) produce 92/92 Proofmark PASS
  2. Each job has a complete doc set (BRD, FSD, test strategy, output manifesto) with numbered requirements, traceability, and evidence
  3. Each `_re` job conf remediates identified anti-patterns with documented justification
  4. The full 13-step workflow executed autonomously with zero human input
  5. Lessons learned from Tier 1 are captured and available to inform Tier 2 approach
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Infrastructure setup + BranchDirectory full RE workflow (template-setter)
- [ ] 01-02-PLAN.md — ComplianceResolutionTime full RE workflow (trailer handling, AP4/AP8 remediation)
- [ ] 01-03-PLAN.md — OverdraftFeeSummary full RE workflow + phase completion + lessons learned

### Phase 2: Tier 2 - Simple Multi-Source
**Goal**: The RE workflow scales to multi-source join complexity at batch size, proving the pattern holds beyond trivial jobs
**Depends on**: Phase 1
**Requirements**: COMP-02
**Success Criteria** (what must be TRUE):
  1. All 10 Tier 2 jobs produce 92/92 Proofmark PASS with complete doc sets
  2. Multi-source join patterns (2+ data sources) are handled correctly across all jobs
  3. Dependency chain Job 22 -> Job 24 -> Job 26 and Job 22 -> Job 25 executed in correct order
  4. Batch execution at 10-job scale completes autonomously without human intervention
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD
- [ ] 02-03: TBD

### Phase 3: Tier 3 - Append Mode
**Goal**: Append mode jobs are RE'd with correct chronological execution and cumulative output matching
**Depends on**: Phase 2
**Requirements**: COMP-03
**Success Criteria** (what must be TRUE):
  1. All 13 Tier 3 jobs produce 92/92 Proofmark PASS with complete doc sets
  2. Append mode execution runs dates in strict chronological order (Oct 1 through Dec 31)
  3. Cumulative output files grow correctly across successive dates (each date's file contains all prior data)
  4. Any Append-specific Proofmark config accommodations are documented with evidence
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: Tier 4 - External Module Conversion
**Goal**: The majority of jobs (~67) are RE'd with SQL-first approach, converting C# external modules to SQL where possible
**Depends on**: Phase 3
**Requirements**: COMP-04
**Success Criteria** (what must be TRUE):
  1. All ~67 Tier 4 jobs produce 92/92 Proofmark PASS with complete doc sets
  2. AP3 (Unnecessary External Module) assessed for every job; external modules retained only with documented evidence of SQL deficiency
  3. AP6 (Row-by-Row Iteration) converted to SQL set operations wherever the C# uses foreach loops
  4. Dependency chain Job 2 -> Job 5 -> Job 6 executed in correct order
  5. Iterative learning from Tiers 1-3 visibly applied (refined templates, known gotchas addressed proactively)
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD
- [ ] 04-04: TBD
- [ ] 04-05: TBD

### Phase 5: Tier 5 - External + Append
**Goal**: Jobs requiring both external module conversion and Append mode execution are RE'd successfully
**Depends on**: Phase 4
**Requirements**: COMP-05
**Success Criteria** (what must be TRUE):
  1. All 6 Tier 5 jobs produce 92/92 Proofmark PASS with complete doc sets
  2. Combined constraints (SQL-first conversion + chronological Append execution) handled correctly
  3. No new external modules created unless FSD documents why SQL is insufficient
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Tier 6 - Boss Level
**Goal**: The 4 most complex jobs in the system are RE'd, completing the full 105-job scope
**Depends on**: Phase 5
**Requirements**: COMP-06
**Success Criteria** (what must be TRUE):
  1. All 4 Tier 6 jobs produce 92/92 Proofmark PASS with complete doc sets
  2. High data source counts and complex logic handled without shortcuts (all anti-patterns assessed and remediated)
  3. All 105 jobs across all tiers confirmed complete with 92/92 PASS
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Tier 1 - Pipeline Validation | 1/3 | In progress | - |
| 2. Tier 2 - Simple Multi-Source | 0/3 | Not started | - |
| 3. Tier 3 - Append Mode | 0/3 | Not started | - |
| 4. Tier 4 - External Module Conversion | 0/5 | Not started | - |
| 5. Tier 5 - External + Append | 0/2 | Not started | - |
| 6. Tier 6 - Boss Level | 0/2 | Not started | - |
