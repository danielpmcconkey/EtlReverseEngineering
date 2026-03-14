# Roadmap: POC6 Workflow Engine

## Milestones

- ✅ **v0.1 State Machine Mechanics** - Phases 1-3 (shipped 2026-03-13)
- ✅ **v0.2 Parallel Execution Infrastructure** - Phases 4-7 (shipped 2026-03-13)
- 🚧 **v0.3 Agent Integration** - Phase 8+ (in progress)

## Phases

<details>
<summary>✅ v0.1 State Machine Mechanics (Phases 1-3) - SHIPPED 2026-03-13</summary>

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation and Happy Path Engine** - State model, transition table, stubs, engine loop, happy-path routing, and structured logging (completed 2026-03-13)
- [x] **Phase 2: Review Branching and Counter Mechanics** - Three-outcome review dispatch, fail-rewind, conditional counters, response nodes, and DEAD_LETTER on retry exhaustion
- [x] **Phase 3: FBR Gauntlet, Triage, and Validation Run** - FBR 6-gate gauntlet with restart semantics, triage sub-pipeline with earliest-fault routing, and full N-job validation run

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
**Plans:** 2/2 plans complete

Plans:
- [x] 01-01-PLAN.md — Data layer: project scaffolding, models, transition table, node stubs, structlog config
- [x] 01-02-PLAN.md — Engine: main loop, CLI entry point, integration tests, end-to-end smoke test

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
**Plans:** 2/2 plans complete

Plans:
- [x] 02-01-PLAN.md — Data layer: REVIEW_ROUTING dict, transition table expansion with Conditional/Fail/response edges, 7 response node stubs
- [x] 02-02-PLAN.md — Engine logic: counter semantics, auto-promotion, DEAD_LETTER, rewind counter reset, integration tests

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
**Plans:** 2/2 plans complete

Plans:
- [x] 03-01-PLAN.md — FBR gauntlet: FBR_ROUTING dict, CONDITIONAL/FAIL edges, fbr_return_pending flag, response node FAILURE edges
- [x] 03-02-PLAN.md — Triage pipeline: TRIAGE_NODES, DiagnosticStubNode, TriageRouterNode, TRIAGE_ROUTE engine handling, 200-job validation run

</details>

### ✅ v0.2 Parallel Execution Infrastructure (Shipped 2026-03-13)

**Milestone Goal:** Replace the synchronous single-threaded engine with a Postgres task queue and multi-threaded worker pool that processes jobs concurrently.

- [x] **Phase 4: Postgres Foundations** - Task queue schema, SKIP LOCKED claiming, and Postgres-backed job state (completed 2026-03-13)
- [x] **Phase 5: Queue Write Paths** - Enqueue-next-on-completion and manifest ingestion (completed 2026-03-13)
- [x] **Phase 6: Worker Pool** - N configurable worker threads running the claim-execute-enqueue loop (completed 2026-03-13)
- [x] **Phase 7: State Machine Wiring and Tests** - Wire existing SM logic into queue execution, rewrite engine integration tests (completed 2026-03-13)

### 🚧 v0.3 Agent Integration (In Progress)

**Milestone Goal:** Replace stub nodes with real Claude CLI agent invocations. Each node maps to a blueprint file, agents communicate via structured JSON process artifacts, and the orchestrator routes deterministically on outcome enums.

- [x] **Phase 8: Agent Invocation Layer** - AgentNode class, CLI invocation, outcome parsing, agent/stub registry toggle, FBR_EvidenceAudit terminal gate (completed 2026-03-14)
- [ ] **Phase 9: Integration Testing** - End-to-end run with real agents, validate outcome parsing, cost tracking

## Phase Details

<details>
<summary>✅ v0.2 Phase Details (Phases 4-7) - SHIPPED 2026-03-13</summary>

### Phase 4: Postgres Foundations
**Goal**: The queue table and job state storage exist in Postgres and work correctly in isolation
**Requirements**: TQ-01, TQ-02, JS-01, JS-02, JS-03 — ALL DONE

### Phase 5: Queue Write Paths
**Goal**: Tasks flow through the queue automatically
**Requirements**: TQ-03, TQ-04 — ALL DONE

### Phase 6: Worker Pool
**Goal**: N worker threads run concurrently
**Requirements**: WK-01, WK-02, WK-03, WK-04 — ALL DONE

### Phase 7: State Machine Wiring and Tests
**Goal**: Full state machine logic runs through queue-based execution
**Requirements**: SM-10, SM-11, TS-01, TS-02, TS-03 — ALL DONE

</details>

### Phase 8: Agent Invocation Layer (Completed 2026-03-14)
**Goal**: Replace stub nodes with real Claude CLI agent invocations via a config flag
**Depends on**: Phase 7
**Requirements**: AG-01, AG-02, AG-03, AG-04, AG-05
**Delivered**:
  1. `AgentNode` class — shells out to `claude -p` with blueprint as system prompt
  2. Structured JSON outcome parsing from agent stdout (SUCCESS/FAIL/APPROVED/CONDITIONAL/REJECTED)
  3. Process artifact chain — agents write JSON for downstream agents on success
  4. `EngineConfig.use_agents` flag toggles stub vs real agent registry
  5. FBR_EvidenceAudit terminal gate (28th node, Pat persona, REJECTED → DEAD_LETTER)
  6. Artifact cleanup on rewinds
  7. 28 agent blueprints written by Hobson (separate commits)
  8. 158 tests passing

### Phase 9: Integration Testing (Not Started)
**Goal**: End-to-end run with real agents on a single job
**Depends on**: Phase 8 + Hobson's blueprints finalized
**Requirements**: AG-06, AG-07
**Success Criteria** (what must be TRUE):
  1. A single job runs through the real pipeline with real Claude CLI agents
  2. Agent outputs parse to valid Outcomes
  3. Process artifact chain works end-to-end (each agent reads its predecessor's JSON)
  4. Cost tracking per job is visible in logs

## Progress

**Execution Order:** 4 → 5 → 6 → 7

| Phase | Milestone | Status | Completed |
|-------|-----------|--------|-----------|
| 1. Foundation and Happy Path Engine | v0.1 | Complete | 2026-03-13 |
| 2. Review Branching and Counter Mechanics | v0.1 | Complete | 2026-03-13 |
| 3. FBR Gauntlet, Triage, and Validation Run | v0.1 | Complete | 2026-03-13 |
| 4. Postgres Foundations | v0.2 | Complete | 2026-03-13 |
| 5. Queue Write Paths | v0.2 | Complete | 2026-03-13 |
| 6. Worker Pool | v0.2 | Complete | 2026-03-13 |
| 7. State Machine Wiring and Tests | v0.2 | Complete | 2026-03-13 |
| 8. Agent Invocation Layer | v0.3 | Complete | 2026-03-14 |
| 9. Integration Testing | v0.3 | Not started | - |
