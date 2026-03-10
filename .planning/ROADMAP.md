# Roadmap: ETL Reverse Engineering Orchestrator

## Overview

Build a deterministic C# CLI orchestrator bottom-up: database task queue first (the single source of truth), then the state machine that defines workflow transitions, then the worker pool that runs the loops, then agent integration that adds real Claude CLI intelligence, then the rewind cascade logic that handles review failures, and finally the production run of all 105 jobs. Each layer is independently testable before the next begins. Deterministic before non-deterministic, cheap before expensive.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Database Foundation** - Postgres task queue with thread-safe claiming, crash recovery, and dead letter support
- [ ] **Phase 2: State Machine and Pipeline Definition** - Deterministic transition table and full waterfall pipeline skeleton
- [ ] **Phase 3: Worker Infrastructure** - 6-thread worker pool with graceful shutdown and structured logging
- [ ] **Phase 4: Agent Integration** - Claude CLI subprocess invocation with structured JSON parsing and blueprint system
- [ ] **Phase 5: Rewind Cascade and Review Logic** - Severity-classified reviews with cosmetic fix-ups and substantive rewrites
- [ ] **Phase 6: Production Pipeline** - All 105 jobs seeded and processed through the complete pipeline

## Phase Details

### Phase 1: Database Foundation
**Goal**: The orchestrator has a durable, thread-safe task queue that survives crashes and prevents double-processing
**Depends on**: Nothing (first phase)
**Requirements**: QUEUE-01, QUEUE-02, QUEUE-03, QUEUE-04, QUEUE-05
**Success Criteria** (what must be TRUE):
  1. Multiple threads can claim tasks concurrently without any thread receiving another thread's task
  2. Killing the process mid-run and restarting it results in orphaned tasks being reclaimed and reprocessed
  3. A task that has been claimed, processed, and completed cannot be claimed again
  4. Tasks that exceed retry limits appear in a dead letter state queryable via SQL
  5. Re-running a reclaimed task produces the same end state as a fresh run (idempotent writes)
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: State Machine and Pipeline Definition
**Goal**: The orchestrator can determine the next step for any job given its current state and the outcome of its last task
**Depends on**: Phase 1
**Requirements**: SM-01, SM-02, PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07
**Success Criteria** (what must be TRUE):
  1. Given any (current_state, outcome) pair, the transition table returns exactly one deterministic next state (or set of next states for fan-out)
  2. A job can be queried for its current position in the waterfall pipeline (which stage, which step)
  3. Every leaf node in the pipeline taxonomy (LocateOgSourceFiles, WriteBrd, ReviewBdd, etc.) has a discrete C# method that can be invoked
  4. Circuit breakers prevent a job from retrying the same stage more than the configured maximum
  5. A job that starts at Plan and receives Success outcomes at every step reaches FinalSignOff
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Worker Infrastructure
**Goal**: The orchestrator runs 6 concurrent workers that claim tasks, execute them, and advance job state in a continuous loop
**Depends on**: Phase 2
**Requirements**: WORK-01, WORK-02, WORK-03, WORK-04
**Success Criteria** (what must be TRUE):
  1. 6 worker threads run concurrently, each independently claiming and processing tasks from the queue
  2. Pressing Ctrl+C causes all workers to finish their current task, update DB state, and exit cleanly (no orphaned tasks)
  3. Log files contain structured entries with job ID, step name, worker ID, current state, and attempt count
  4. Running with --dry-run flag exercises the full orchestration loop (claim, transition, advance) without spawning any Claude CLI subprocesses
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Agent Integration
**Goal**: Workers invoke real Claude CLI agents per task, with fresh context isolation, structured responses, and blueprint-driven prompts
**Depends on**: Phase 3
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04
**Success Criteria** (what must be TRUE):
  1. Each task spawns a fresh `claude -p` subprocess with no state carried from previous invocations
  2. Agent JSON responses are parsed into typed C# objects, with non-JSON preamble/stderr stripped without failure
  3. Each agent type loads its constraints from a dedicated blueprint.md file used as the system prompt
  4. A subprocess that hangs beyond its timeout is killed and the task transitions to a failure state with appropriate retry logic
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: Rewind Cascade and Review Logic
**Goal**: Review agents classify failures by severity, triggering targeted fix-ups or full rewrites with cascade depth protection
**Depends on**: Phase 4
**Requirements**: SM-03, SM-04, SM-05, SM-06
**Success Criteria** (what must be TRUE):
  1. Review agents return structured severity classification (cosmetic vs substantive) in their JSON response
  2. A cosmetic review failure enqueues a targeted fix-up task that addresses only the flagged issues without rewriting the full artifact
  3. A substantive review failure rewinds the job to the Write step for that artifact, re-queuing all downstream steps
  4. Rewind cascades triggered by final build review cannot loop more than the configured depth cap
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Production Pipeline
**Goal**: All 105 ETL jobs are seeded and processed through the complete pipeline with zero cross-job contamination
**Depends on**: Phase 5
**Requirements**: PIPE-08
**Success Criteria** (what must be TRUE):
  1. All 105 jobs are seeded into the task queue with their initial Plan-stage tasks
  2. Jobs process concurrently without any job's artifacts, state, or context contaminating another job
  3. Jobs that complete the full pipeline reach FinalSignOff status with all artifacts produced
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Database Foundation | 0/? | Not started | - |
| 2. State Machine and Pipeline Definition | 0/? | Not started | - |
| 3. Worker Infrastructure | 0/? | Not started | - |
| 4. Agent Integration | 0/? | Not started | - |
| 5. Rewind Cascade and Review Logic | 0/? | Not started | - |
| 6. Production Pipeline | 0/? | Not started | - |
