# Roadmap: POC6 Workflow Engine

## Overview

Three phases that build a deterministic workflow engine from the ground up. Phase 1 gets a running engine with happy-path-only routing, stubs, and structured logging -- proving the loop works before adding branching. Phase 2 adds the core complexity: three-outcome review branching, fail-rewind with replay-forward, conditional counters with auto-promotion, and counter reset semantics. Phase 3 layers the two advanced sub-systems (FBR gauntlet and triage pipeline) on top of the review branching mechanics, then runs N jobs to exercise all paths.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation and Happy Path Engine** - State model, transition table, stubs, engine loop, happy-path routing, and structured logging
- [ ] **Phase 2: Review Branching and Counter Mechanics** - Three-outcome review dispatch, fail-rewind, conditional counters, response nodes, and DEAD_LETTER on retry exhaustion
- [ ] **Phase 3: FBR Gauntlet, Triage, and Validation Run** - FBR 6-gate gauntlet with restart semantics, triage sub-pipeline with earliest-fault routing, and full N-job validation run

## Phase Details

### Phase 1: Foundation and Happy Path Engine
**Goal**: A running engine that drives jobs through 27 happy-path nodes with stubbed outcomes and structured logging
**Depends on**: Nothing (first phase)
**Requirements**: SM-01, SM-02, SM-03, HP-01, HP-02, HP-03, HP-04, ENG-01, ENG-02, ENG-03, ENG-04, LOG-01, LOG-02, LOG-03, PS-01, PS-02
**Success Criteria** (what must be TRUE):
  1. A job can traverse all 27 happy-path nodes from LocateOgSourceFiles through FinalSignOff to COMPLETE when all stubs return success/approve
  2. Transition table is a declarative data structure (dict-based) that can be inspected without reading procedural code
  3. Every node transition is logged as structured JSON with job ID, node name, outcome, and counter values
  4. N and M retry limits are configurable and default to sensible values
  5. Running N jobs sequentially produces distinct per-job logs with no state bleed between jobs
**Plans:** 2 plans

Plans:
- [ ] 01-01-PLAN.md — Data layer: project scaffolding, models, transition table, node stubs, structlog config
- [ ] 01-02-PLAN.md — Engine: main loop, CLI entry point, integration tests, end-to-end smoke test

### Phase 2: Review Branching and Counter Mechanics
**Goal**: The engine correctly handles all three review outcomes -- approve advances, conditional routes to response node and back, fail rewinds to origin write node and replays forward -- with counter semantics that prevent infinite loops
**Depends on**: Phase 1
**Requirements**: SM-04, SM-05, SM-06, SM-07, SM-08, SM-09, RB-01, RB-02, RB-03, RB-04, RB-05
**Success Criteria** (what must be TRUE):
  1. A Conditional outcome at a review node routes to the correct response node, then back to the same reviewer, without invalidating downstream work
  2. A Fail outcome at a review node rewinds to the original write node and replays the full pipeline forward from there
  3. The Mth consecutive Conditional at the same review node auto-promotes to Fail (incrementing the main retry counter and rewinding)
  4. A job reaching N total Fails is sent to DEAD_LETTER instead of rewinding again
  5. Per-node conditional counters reset to 0 on success at that node AND on rewind past that node
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: FBR Gauntlet, Triage, and Validation Run
**Goal**: The FBR 6-gate gauntlet and 7-step triage sub-pipeline both work correctly, and a batch of N jobs with RNG outcomes exercises all major transition paths
**Depends on**: Phase 2
**Requirements**: FBR-01, FBR-02, FBR-03, FBR-04, TR-01, TR-02, TR-03, TR-04, TR-05, TR-06, TR-07
**Success Criteria** (what must be TRUE):
  1. All 6 FBR gates execute in serial after Publish; any gate failure restarts the gauntlet from FBR_BrdCheck (not from the failed gate)
  2. FBR Conditional routes to response node, then review, then back to FBR_BrdCheck (not to the next gate)
  3. FBR Fail rewinds to original write node and replays forward, naturally arriving back at FBR_BrdCheck through the pipeline
  4. Triage sub-pipeline enters on ExecuteProofmark failure, runs T1-T7, and routes to the earliest fault found
  5. Running 100+ jobs with RNG outcomes produces logs showing rewinds, conditional loops, FBR restarts, triage routing, and DEAD_LETTER exhaustion all occurred
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation and Happy Path Engine | 0/2 | Not started | - |
| 2. Review Branching and Counter Mechanics | 0/2 | Not started | - |
| 3. FBR Gauntlet, Triage, and Validation Run | 0/3 | Not started | - |
