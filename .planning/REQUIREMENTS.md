# Requirements: ETL Reverse Engineering Orchestrator

**Defined:** 2026-03-10
**Core Value:** Every job completes its full pipeline with deterministic orchestration that cannot context-rot, fabricate results, or forget its constraints.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Task Queue

- [ ] **QUEUE-01**: Orchestrator uses Postgres task queue with `SELECT ... FOR UPDATE SKIP LOCKED` for thread-safe task claiming
- [ ] **QUEUE-02**: All task state persists in Postgres — process crashes do not lose progress
- [ ] **QUEUE-03**: Task execution is idempotent — re-running a reclaimed task produces correct state (atomic file writes, transactional DB updates)
- [ ] **QUEUE-04**: On startup, orchestrator reclaims orphaned tasks (status = processing with stale timestamps)
- [ ] **QUEUE-05**: Tasks that exhaust circuit breaker retries move to a dead letter state for post-mortem analysis

### State Machine

- [ ] **SM-01**: Workflow is a deterministic transition table mapping (current_state, outcome) → next_state, tracked per-job — orchestrator can query any job's current position in the workflow
- [ ] **SM-02**: Circuit breakers enforce max retry limits per stage as guard conditions on transitions
- [ ] **SM-03**: Review agents return severity classification (cosmetic vs substantive) in structured response
- [ ] **SM-04**: Cosmetic review failures enqueue a targeted fix-up task for the artifact
- [ ] **SM-05**: Substantive review failures rewind the job to the Write step for that artifact, re-queuing downstream steps
- [ ] **SM-06**: Rewind cascades (triggered by final build review) have depth caps to prevent infinite loops

### Pipeline

- [ ] **PIPE-01**: Each job follows the full waterfall: Plan → Define → Design → Build → Validate
- [ ] **PIPE-02**: Every leaf node in the taxonomy tree has a discrete C# method — for v1, each method logs that it was entered and returns success
- [ ] **PIPE-03**: Plan stage methods: LocateOgSourceFiles, InventoryOutputs, InventoryDataSources, NoteDependencies
- [ ] **PIPE-04**: Define stage methods: WriteBrd, ReviewBrd, ReReviewBrd
- [ ] **PIPE-05**: Design stage methods: WriteBddTestArchitecture, ReviewBdd, WriteFsd, ReviewFsd, ReReviewBdd, ReReviewFsd
- [ ] **PIPE-06**: Build stage methods: BuildJobArtifacts, ReviewJobArtifacts, BuildProofmarkConfig, ReviewProofmarkConfig, BuildUnitTests, ReviewUnitTests, ExecuteUnitTests, Publish, FinalBuildReview
- [ ] **PIPE-07**: Validate stage methods: ExecuteJobRuns, ExecuteProofmark, TriageProofmarkFailures, FinalSignOff
- [ ] **PIPE-08**: 105 independent job pipelines with zero cross-job contamination

### Workers

- [ ] **WORK-01**: 6 concurrent worker threads process tasks from the FIFO queue
- [ ] **WORK-02**: Graceful shutdown on Ctrl+C — workers finish current tasks, update DB state, then exit
- [ ] **WORK-03**: Structured logging via Serilog to file sinks with job ID, step, state, and attempt count per log entry
- [ ] **WORK-04**: Dry-run mode flag that validates orchestration logic without invoking Claude CLI agents

### Agent Integration

- [ ] **AGENT-01**: Each task invokes a fresh Claude CLI subprocess via `claude -p` with zero state carried between invocations
- [ ] **AGENT-02**: Agents return structured JSON responses parsed by the orchestrator with resilient error handling
- [ ] **AGENT-03**: Each agent type has a `blueprint.md` file defining RE-specific constraints, used as the system prompt
- [ ] **AGENT-04**: Blueprints define the RE-specific guardrails; generic capabilities (writing BRDs, designing tests, etc.) leverage Claude's inherent knowledge

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Observability

- **OBS-01**: Job-level progress tracking via CLI command (where is job N in the pipeline?)
- **OBS-02**: Aggregate pipeline metrics (success rates, failure hotspots, duration per stage)
- **OBS-03**: Token/cost tracking per task and per job

### Operational

- **OPS-01**: Pause/resume per job without affecting other pipelines
- **OPS-02**: Artifact versioning — keep previous versions when rewrites occur
- **OPS-03**: Heartbeat/liveness monitoring for long-running agent tasks
- **OPS-04**: Configurable model tier per skill (some skills Opus, some Sonnet)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web dashboard / real-time UI | Over-engineering for a CLI batch tool. Log files + SQL queries suffice. |
| Priority queue / weighted scheduling | All 105 jobs are equally important. FIFO is correct. |
| Cross-job dependencies | Jobs are independent by design. Shared concerns handled outside orchestrator. |
| Dynamic agent routing / LLM-decided workflow | This is the POC5 anti-pattern. Orchestrator decides, always. |
| Distributed workers across machines | 6 threads on one machine is the constraint. Distributed coordination is massive complexity for zero gain. |
| Event-driven / pub-sub architecture | Pull-based SKIP LOCKED already solves work distribution. |
| Saga / compensating transactions | Rewind is re-queue, not undo. Artifacts get overwritten, not compensated. |
| Plugin / extension system | Finite batch of 105 jobs, not a platform. |
| Rate limiting beyond worker cap | 6-worker cap IS the rate limiter. |
| Mid-task checkpointing | Tasks are atomic. Long tasks should be broken into smaller tasks. |
| Formalized skill registry abstraction | Blueprints may evolve into this, but not designed up front. |
| Deterministic step bypass | Keep the worker loop uniform (always invoke agent). Cheap steps get cheap blueprints. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (populated by roadmap) | | |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 0
- Unmapped: 23 ⚠️

---
*Requirements defined: 2026-03-10*
*Last updated: 2026-03-10 after initial definition*
