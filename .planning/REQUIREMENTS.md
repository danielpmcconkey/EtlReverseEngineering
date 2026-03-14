# Requirements: POC6 Workflow Engine

**Defined:** 2026-03-14
**Core Value:** A constant swarm of worker threads processes jobs concurrently through the validated state machine — no worker ever blocks waiting on another.

## v0.2 Requirements

Requirements for v0.2 release. Each maps to roadmap phases.

### Task Queue

- [ ] **TQ-01**: Postgres `re_task_queue` table exists in `control` schema with FIFO ordering
- [ ] **TQ-02**: Tasks are claimed via `SELECT ... FOR UPDATE SKIP LOCKED` — no two workers claim the same task
- [ ] **TQ-03**: Node completion enqueues the next task (determined by transition lookup) rather than directly invoking the next node
- [ ] **TQ-04**: Loading a job manifest JSON enqueues the first node task for every job in the manifest

### Job State

- [ ] **JS-01**: Job state is persisted in Postgres (replaces in-memory `JobState`)
- [ ] **JS-02**: Any worker thread can read/write any job's state
- [ ] **JS-03**: Only one active task per job exists on the queue at a time (parallelism across jobs, not within)

### Workers

- [ ] **WK-01**: N worker threads monitor the queue, default 6
- [ ] **WK-02**: Worker count is externally configurable (config file or environment variable)
- [ ] **WK-03**: Each worker loops: claim task → execute callback → enqueue next step → claim next task
- [ ] **WK-04**: Workers are fungible — any worker can process any job's task

### State Machine

- [ ] **SM-10**: All existing transition logic (transitions, counters, rewinds, FBR, triage) is preserved and invoked per-step through the queue
- [ ] **SM-11**: State machine produces the same outcomes as v0.1 (same node visit sequences, same counter behavior, same terminal states)

### Tests

- [ ] **TS-01**: Transition table data tests remain unchanged
- [ ] **TS-02**: Engine integration tests are rewritten to validate behavior through queue-based execution
- [ ] **TS-03**: No synchronous `run_job()` test harness exists in the final codebase

## Future Requirements

### Agent Integration

- **AG-01**: Node stubs replaced with Claude CLI agent invocations
- **AG-02**: Per-agent blueprints as system prompts
- **AG-03**: Agent cost caps per invocation

### Validation Tooling

- **VAL-01**: Transition table static validation at startup (reachability, dead states, missing edges)
- **VAL-02**: Path coverage reporting — which transition paths were exercised across a run

## Out of Scope

| Feature | Reason |
|---------|--------|
| Claude CLI agent invocation | Stubs only — de-stubbing is a future milestone |
| Real agent blueprints | Stubs have comments, not real prompts |
| Proofmark integration | Triage sub-pipeline is stubbed |
| MockEtlFrameworkPython integration | No real artifact production |
| Within-job parallelism | Jobs are serial pipelines; parallelism is across jobs only |
| Generic workflow DSL | One pipeline, not a framework |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TQ-01 | Phase 4 | Pending |
| TQ-02 | Phase 4 | Pending |
| JS-01 | Phase 4 | Pending |
| JS-02 | Phase 4 | Pending |
| JS-03 | Phase 4 | Pending |
| TQ-03 | Phase 5 | Pending |
| TQ-04 | Phase 5 | Pending |
| WK-01 | Phase 6 | Pending |
| WK-02 | Phase 6 | Pending |
| WK-03 | Phase 6 | Pending |
| WK-04 | Phase 6 | Pending |
| SM-10 | Phase 7 | Pending |
| SM-11 | Phase 7 | Pending |
| TS-01 | Phase 7 | Pending |
| TS-02 | Phase 7 | Pending |
| TS-03 | Phase 7 | Pending |

**Coverage:**
- v0.2 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-14 after roadmap creation — all 16 requirements mapped*
