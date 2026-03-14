# Requirements: POC6 Workflow Engine

**Defined:** 2026-03-14
**Core Value:** A constant swarm of worker threads processes jobs concurrently through the validated state machine — no worker ever blocks waiting on another.

## v0.2 Requirements

Requirements for v0.2 release. Each maps to roadmap phases.

### Task Queue

- [x] **TQ-01**: Postgres `re_task_queue` table exists in `control` schema with FIFO ordering
- [x] **TQ-02**: Tasks are claimed via `SELECT ... FOR UPDATE SKIP LOCKED` — no two workers claim the same task
- [x] **TQ-03**: Node completion enqueues the next task (determined by transition lookup) rather than directly invoking the next node
- [x] **TQ-04**: Loading a job manifest JSON enqueues the first node task for every job in the manifest

### Job State

- [x] **JS-01**: Job state is persisted in Postgres (replaces in-memory `JobState`)
- [x] **JS-02**: Any worker thread can read/write any job's state
- [x] **JS-03**: Only one active task per job exists on the queue at a time (parallelism across jobs, not within)

### Workers

- [x] **WK-01**: N worker threads monitor the queue, default 6
- [x] **WK-02**: Worker count is externally configurable (config file or environment variable)
- [x] **WK-03**: Each worker loops: claim task → execute callback → enqueue next step → claim next task
- [x] **WK-04**: Workers are fungible — any worker can process any job's task

### State Machine

- [x] **SM-10**: All existing transition logic (transitions, counters, rewinds, FBR, triage) is preserved and invoked per-step through the queue
- [x] **SM-11**: State machine produces the same outcomes as v0.1 (same node visit sequences, same counter behavior, same terminal states)

### Tests

- [x] **TS-01**: Transition table data tests remain unchanged
- [x] **TS-02**: Engine integration tests are rewritten to validate behavior through queue-based execution
- [x] **TS-03**: No synchronous `run_job()` test harness exists in the final codebase

## v0.3 Requirements

### Agent Integration

- [x] **AG-01**: Node stubs replaced with Claude CLI agent invocations (behind config flag)
- [x] **AG-02**: Per-agent blueprints as system prompts (28 blueprints written)
- [x] **AG-03**: Agent cost caps per invocation (`--max-budget-usd`)
- [x] **AG-04**: Structured JSON process artifact chain (agent-to-agent communication)
- [x] **AG-05**: FBR_EvidenceAudit terminal gate (Pat persona, REJECTED → DEAD_LETTER)
- [ ] **AG-06**: End-to-end single-job run with real agents
- [ ] **AG-07**: Cost tracking per job visible in logs

### Validation Tooling (Future)

- **VAL-01**: Transition table static validation at startup (reachability, dead states, missing edges)
- **VAL-02**: Path coverage reporting — which transition paths were exercised across a run

## Out of Scope

| Feature | Reason |
|---------|--------|
| Within-job parallelism | Jobs are serial pipelines; parallelism is across jobs only |
| Generic workflow DSL | One pipeline, not a framework |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TQ-01 | Phase 4 | Done |
| TQ-02 | Phase 4 | Done |
| JS-01 | Phase 4 | Done |
| JS-02 | Phase 4 | Done |
| JS-03 | Phase 4 | Done |
| TQ-03 | Phase 5 | Done |
| TQ-04 | Phase 5 | Done |
| WK-01 | Phase 6 | Done |
| WK-02 | Phase 6 | Done |
| WK-03 | Phase 6 | Done |
| WK-04 | Phase 6 | Done |
| SM-10 | Phase 7 | Done |
| SM-11 | Phase 7 | Done |
| TS-01 | Phase 7 | Done |
| TS-02 | Phase 7 | Done |
| TS-03 | Phase 7 | Done |
| AG-01 | Phase 8 | Done |
| AG-02 | Phase 8 | Done |
| AG-03 | Phase 8 | Done |
| AG-04 | Phase 8 | Done |
| AG-05 | Phase 8 | Done |
| AG-06 | Phase 9 | Pending |
| AG-07 | Phase 9 | Pending |

**Coverage:**
- v0.2 requirements: 16 done
- v0.3 requirements: 5 done, 2 pending
- Total: 23 mapped, 0 unmapped

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-14 — v0.2 complete, v0.3 phase 8 complete*
