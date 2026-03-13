# Requirements: POC6 Workflow Engine

**Defined:** 2026-03-13
**Core Value:** The state machine correctly implements the transition table — rewinds, conditional loops, FBR gauntlet restarts, triage routing, and DEAD_LETTER on retry exhaustion all behave as designed.

## v1 Requirements

Requirements for v0.1 release. Each maps to roadmap phases.

### State Model

- [ ] **SM-01**: Job state tracks current node, main retry counter, and per-node conditional counters
- [ ] **SM-02**: Transition table is declarative data (dict-based), not procedural if/else
- [ ] **SM-03**: Main retry counter (N) and conditional limit (M) are configurable with sensible defaults
- [ ] **SM-04**: Main retry counter increments on any full Fail at any review node
- [ ] **SM-05**: Main retry counter reaching N sends job to DEAD_LETTER
- [ ] **SM-06**: Per-node conditional counter increments on Conditional outcome at that review node
- [ ] **SM-07**: Per-node conditional counter reaching M auto-promotes to Fail (incrementing main retry)
- [ ] **SM-08**: Per-node conditional counter resets to 0 on success at that node
- [ ] **SM-09**: Per-node conditional counters reset to 0 for all nodes downstream of a rewind target

### Happy Path

- [ ] **HP-01**: 27 happy-path nodes execute in order from LocateOgSourceFiles through FinalSignOff → COMPLETE
- [ ] **HP-02**: Each node is a stub with a comment describing what the real agent will do
- [ ] **HP-03**: Non-review stubs return Success/Failure via RNG
- [ ] **HP-04**: Review stubs return Approve/Conditional/Fail via RNG

### Review Branching

- [ ] **RB-01**: Approve routes to next node in happy path
- [ ] **RB-02**: Conditional routes to response node → same reviewer (no downstream invalidation)
- [ ] **RB-03**: Fail rewinds to original write node and replays the full pipeline forward from there
- [ ] **RB-04**: Writer/response nodes receive only the most recent rejection reason — no errata accumulation
- [ ] **RB-05**: 7 response nodes exist (WriteBrdResponse, WriteBddResponse, WriteFsdResponse, BuildJobArtifactsResponse, BuildProofmarkResponse, BuildUnitTestsResponse, TriageProofmarkFailures)

### FBR Gauntlet

- [ ] **FBR-01**: 6 serial gates (FBR_BrdCheck → FBR_UnitTestCheck) execute after Publish
- [ ] **FBR-02**: FBR gate Conditional routes to response node → review → approve → restart gauntlet from FBR_BrdCheck
- [ ] **FBR-03**: FBR gate Fail rewinds to original write node, replays forward (naturally arriving back at FBR_BrdCheck)
- [ ] **FBR-04**: Engine tracks fbr_return_pending flag so post-fix review approval routes back to FBR_BrdCheck instead of happy path

### Triage Sub-Pipeline

- [ ] **TR-01**: ExecuteProofmark failure enters 7-step triage (T1-T7)
- [ ] **TR-02**: T1-T2 are context-gathering stubs (data profiling, OG flow analysis)
- [ ] **TR-03**: T3-T6 are diagnostic stubs returning clean/fault via RNG
- [ ] **TR-04**: T7 is pure orchestrator logic — routes to earliest fault found
- [ ] **TR-05**: Multiple faults route to the earliest (highest up the pipeline)
- [ ] **TR-06**: No faults found → DEAD_LETTER
- [ ] **TR-07**: Triage routing triggers a rewind (which increments main retry counter)

### Engine

- [ ] **ENG-01**: Engine main loop: pick job, resolve transition, execute stub, advance state, repeat
- [ ] **ENG-02**: Run N configurable jobs through the full pipeline
- [ ] **ENG-03**: In-memory job state (no Postgres)
- [ ] **ENG-04**: Single-threaded sequential execution

### Logging

- [ ] **LOG-01**: Structured JSON logging via structlog
- [ ] **LOG-02**: Every transition logged: job ID, node name, outcome, main retry count, conditional counts
- [ ] **LOG-03**: Logs are sufficient for post-hoc agent analysis of workflow correctness

### Project Structure

- [ ] **PS-01**: Source lives at src/workflow_engine/
- [ ] **PS-02**: Pure Python — no external frameworks (structlog is the one runtime dependency)

## v2 Requirements

### Validation Tooling

- **VAL-01**: Transition table static validation at startup (reachability, dead states, missing edges)
- **VAL-02**: Path coverage reporting — which transition paths were exercised across a run
- **VAL-03**: Automated assertions that key behaviors occurred (rewinds, dead letters, gauntlet restarts)

### Infrastructure Integration

- **INF-01**: Postgres task queue with thread-safe claiming
- **INF-02**: Multi-threaded worker pool with configurable concurrency
- **INF-03**: Claude CLI agent invocation replacing stubs

## Out of Scope

| Feature | Reason |
|---------|--------|
| Postgres task queue | v0.1 validates mechanics with in-memory state |
| Real agent invocation | Stubs only — no Claude CLI, no cost |
| Agent blueprints | Stubs have comments, not real prompts |
| Parallelism / concurrency | Single-threaded for v0.1, multi-threaded in v2 |
| Proofmark integration | Triage sub-pipeline is stubbed |
| MockEtlFrameworkPython integration | No real artifact production |
| Automated test assertions | Logs are the v0.1 validation artifact |
| Errata accumulation | Explicitly rejected — writer gets only most recent rejection |
| Generic workflow DSL | One pipeline, not a framework |
| Compensation/saga pattern | Artifacts are overwritten, not rolled back |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SM-01 | TBD | Pending |
| SM-02 | TBD | Pending |
| SM-03 | TBD | Pending |
| SM-04 | TBD | Pending |
| SM-05 | TBD | Pending |
| SM-06 | TBD | Pending |
| SM-07 | TBD | Pending |
| SM-08 | TBD | Pending |
| SM-09 | TBD | Pending |
| HP-01 | TBD | Pending |
| HP-02 | TBD | Pending |
| HP-03 | TBD | Pending |
| HP-04 | TBD | Pending |
| RB-01 | TBD | Pending |
| RB-02 | TBD | Pending |
| RB-03 | TBD | Pending |
| RB-04 | TBD | Pending |
| RB-05 | TBD | Pending |
| FBR-01 | TBD | Pending |
| FBR-02 | TBD | Pending |
| FBR-03 | TBD | Pending |
| FBR-04 | TBD | Pending |
| TR-01 | TBD | Pending |
| TR-02 | TBD | Pending |
| TR-03 | TBD | Pending |
| TR-04 | TBD | Pending |
| TR-05 | TBD | Pending |
| TR-06 | TBD | Pending |
| TR-07 | TBD | Pending |
| ENG-01 | TBD | Pending |
| ENG-02 | TBD | Pending |
| ENG-03 | TBD | Pending |
| ENG-04 | TBD | Pending |
| LOG-01 | TBD | Pending |
| LOG-02 | TBD | Pending |
| LOG-03 | TBD | Pending |
| PS-01 | TBD | Pending |
| PS-02 | TBD | Pending |

**Coverage:**
- v1 requirements: 38 total
- Mapped to phases: 0
- Unmapped: 38 ⚠️

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-13 after initial definition*
