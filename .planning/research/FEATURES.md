# Feature Landscape

**Domain:** Deterministic task orchestrator for AI-agent-driven ETL reverse engineering pipelines
**Researched:** 2026-03-10

## Table Stakes

Features the orchestrator must have or it fundamentally doesn't work. These aren't negotiable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Postgres-backed task queue with `SELECT ... FOR UPDATE SKIP LOCKED` | Core work distribution. Without it, workers double-claim tasks or deadlock. This is the proven pattern for Postgres job queues -- used by Solid Queue, PgBoss, and every serious Postgres queue implementation. | Low | Well-documented pattern. Composite index on `(status, created_at)` is critical for performance. |
| State machine with explicit transition table | The whole thesis. `(current_state, outcome) -> next_state` must be a deterministic lookup, not logic. Without it you're back to LLM-orchestrated chaos. | Medium | Transition table should be data, not code. Load from config or DB so changes don't require recompilation. |
| Concurrent worker pool (6 threads) | 105 jobs x multi-step pipeline = hundreds of tasks. Serial processing would take forever. Thread pool with bounded concurrency is standard. | Medium | Use `SemaphoreSlim` or `BlockingCollection<T>` -- don't roll your own thread management. |
| Per-task agent isolation (fresh context) | POC5's fatal flaw was context rot. Each agent invocation must be a clean subprocess with zero carryover. This is the core design insight. | Low | `claude -p` subprocess per task. No persistent sessions, no conversation history between tasks. |
| Structured JSON agent responses | Orchestrator must parse agent output deterministically. Free-text responses make the orchestrator non-deterministic by definition. | Low | Define JSON schemas per skill. Fail the task if output doesn't parse. |
| Circuit breakers (max retry per stage) | Without circuit breakers, a failing task retries forever, burning tokens and blocking the pipeline. Standard resilience pattern. | Low | Simple counter per job-stage combo. Three states: closed (normal), open (stop retrying), half-open (test one). Start simple -- just a max-retry count is fine for v1. |
| Task state persistence | Every task's state must survive process crashes. If the orchestrator dies, it must resume from where it left off, not restart everything. | Medium | Postgres is your persistence layer. Task states, timestamps, attempt counts all live in the DB. |
| Idempotent task execution | Workers can crash mid-task. When the task gets reclaimed, re-execution must not produce corrupt state. Agent invocations are naturally idempotent (fresh context, overwrite artifacts). | Low | Artifact writes should be atomic (write to temp, rename). DB state updates in transactions. |
| Graceful shutdown | `Ctrl+C` must not corrupt state. Workers finish current tasks, update DB, then exit. Orphaned "processing" tasks must be recoverable on restart. | Medium | `CancellationToken` propagation through the worker loop. Startup sweep to reclaim orphaned tasks. |
| Per-task logging | When a task fails, you need to know what the agent said, what the orchestrator parsed, and why the transition failed. Without this, debugging 105 pipelines is impossible. | Low | Log agent stdout/stderr to files. One log file per task invocation. Include timestamps, job ID, step, attempt number. |
| Skill registry | Each task type needs its prompt template, output schema, model tier, budget cap, and allowed tools defined in one place. Without this, skill definitions are scattered across the codebase. | Medium | C# classes or config objects. One skill definition = one unit of agent behavior. |
| Waterfall pipeline definition | Plan -> Define -> Design -> Build -> Validate with well-defined handoffs. Each stage produces artifacts consumed by the next. | Medium | The pipeline is really a DAG of task types per job. Within a stage, sub-steps may have their own ordering (write -> review -> respond). |
| Review/response cycle with severity classification | Agents review artifacts and classify issues as cosmetic vs substantive. This drives the rewind-vs-fixup decision. Without severity, every review failure is a full rewind. | Medium | Two code paths: cosmetic -> targeted fix-up task, substantive -> rewind to write step. Severity is part of the review agent's JSON schema. |

## Differentiators

Features that add robustness, observability, or operational quality. The system works without them, but they prevent pain at scale.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dead letter queue | Tasks that exhaust circuit breaker retries go to a dead letter state instead of disappearing. Enables post-mortem analysis and manual intervention. | Low | Just another task status in the DB. `failed_permanent` or `dead_letter`. Query them later for patterns. |
| Job-level progress tracking | Dashboard-free way to answer "how far along is job 47?" Current stage, completed stages, total tasks, failed tasks. | Low | Aggregate query over task states per job. CLI command to dump progress. |
| Aggregate pipeline metrics | Success rate, average duration per stage, failure hotspots across all 105 jobs. Surfaces systemic issues (e.g., "Design stage fails 40% of the time"). | Medium | Postgres aggregation queries. No fancy tooling needed -- SQL views or CLI reports. |
| Token/cost tracking per task | Each agent invocation burns API tokens. Tracking cost per task, per stage, per job lets you spot runaway agents and optimize model tier assignments. | Low | Parse Claude CLI output for token counts. Store in task record. |
| Rewind cascade logic | Substantive review failures in Build's final review can cascade re-reviews of BRD/BDD/FSD. Previous artifacts may need updates when later stages reveal issues. | High | This is the most complex control flow in the system. Needs careful state management to avoid infinite loops. Cap cascade depth. |
| Artifact versioning | When a rewind overwrites an artifact, keep the previous version. Enables diffing between versions and understanding what changed. | Low | Simple: append version number to artifact filename, or store in DB with version column. |
| Startup state reconciliation | On restart, scan for orphaned tasks (status = "processing" but no worker owns them) and reclaim them. | Low | Single query on startup: `UPDATE tasks SET status = 'pending' WHERE status = 'processing' AND claimed_at < NOW() - interval '30 minutes'`. |
| Dry-run mode | Run the orchestrator without actually invoking agents. Validates the state machine, queue setup, and pipeline definition. | Low | Flag that skips the `claude -p` subprocess and returns mock success. |
| Configurable model tier per skill | Some skills need Opus, some are fine with Sonnet. Don't burn Opus tokens on boilerplate tasks. | Low | Already in the skill registry design. Just make it configurable. |
| Pause/resume per job | Ability to pause a specific job's pipeline (e.g., waiting for manual review) without stopping other jobs. | Low | Job-level status flag. Workers skip paused jobs when claiming. |
| Deterministic-only steps (no agent) | Some steps like "Locate OG sources" or "Publish artifact" might be pure code, no LLM needed. The skill registry should support both agent and deterministic skill types. | Low | Skill type enum: `Agent` vs `Deterministic`. Worker dispatches accordingly. |
| Heartbeat/liveness for long tasks | Agent invocations can take minutes. Workers should emit heartbeats so the orchestrator knows they're alive, not hung. | Medium | Periodic DB timestamp update from worker thread. Stale heartbeats trigger task reclamation. |

## Anti-Features

Things to deliberately NOT build. Each one is a trap that adds complexity without proportional value for this specific use case.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Priority queue / weighted scheduling | FIFO is correct here. All 105 jobs are equally important. Priority adds complexity, tuning knobs, and starvation bugs for zero benefit. | Pure FIFO. First claimed, first processed. |
| Web dashboard / real-time UI | Over-engineering for a CLI tool processing a finite batch. You'll spend more time building the dashboard than using it. | CLI commands for status queries. SQL views for ad-hoc analysis. |
| Cross-job dependency graph | Jobs are independent by design. Adding cross-job dependencies creates a coordination problem that doesn't need to exist. | Per-job isolation. If a shared concern emerges, handle it outside the orchestrator. |
| Dynamic agent chaining / LLM-decided routing | This is the POC5 anti-pattern. The moment an LLM decides what to do next, you've lost determinism. The orchestrator decides, always. | Hardcoded state machine transitions. Agents execute tasks, they don't choose them. |
| Distributed workers across machines | 6 workers on one machine is the constraint. Distributed coordination (consensus, network partitions, clock skew) is massive complexity for no gain here. | Single-process, multi-threaded. Postgres handles the coordination. |
| Event-driven / pub-sub architecture | The system is pull-based (workers poll the queue). Event-driven adds infrastructure (message brokers, event schemas, delivery guarantees) that Postgres SKIP LOCKED already solves. | Poll-based worker loop. Workers claim tasks, process them, update state. Simple. |
| Saga / compensating transactions | The rewind mechanism is NOT a saga. Rewinding to a write step just re-queues downstream tasks -- it doesn't "undo" anything. Artifacts get overwritten, not compensated. | Rewind = re-queue downstream tasks with fresh state. No compensation logic needed. |
| Plugin / extension system | 105 jobs with a known pipeline. This is a finite, well-scoped batch, not a platform. Building extensibility is building for users who don't exist. | Hardcode the pipeline. If the pipeline changes, change the code. |
| Rate limiting / backpressure to Claude API | The 6-worker cap IS the rate limiter. Adding token bucket / sliding window rate limiting on top is redundant complexity. | Bounded thread pool is your rate limiter. If you hit API limits, reduce workers. |
| Checkpointing within a single task | Tasks are atomic -- an agent invocation either succeeds or fails. Mid-task checkpointing implies long-running tasks that should be broken into smaller tasks instead. | Break complex work into multiple discrete tasks in the pipeline definition. |

## Feature Dependencies

```
Task Queue ─────────────────┐
State Machine ──────────────┤
Skill Registry ─────────────┼──> Worker Pool ──> Agent Invocation ──> Response Parsing
Per-task Logging ───────────┤
Circuit Breakers ───────────┘

State Machine + Skill Registry ──> Waterfall Pipeline Definition

Response Parsing ──> Review/Severity Classification ──> Rewind Logic
                                                    ──> Fix-up Task Generation

Rewind Logic ──> Rewind Cascade (differentiator, build on top of basic rewind)

Task Queue ──> Dead Letter Queue (just another status)
Task Queue ──> Graceful Shutdown (reclaim orphaned tasks)
Task Queue ──> Startup Reconciliation (reclaim stale tasks)

Skill Registry ──> Configurable Model Tier
Skill Registry ──> Deterministic-only Steps
```

## MVP Recommendation

**Build first (foundation):**
1. Task queue with SKIP LOCKED claiming -- this is the beating heart
2. State machine with transition table -- this is the brain
3. Worker pool with bounded concurrency -- this is the muscle
4. Skill registry with at least one skill defined -- this proves the dispatch model
5. Agent invocation with JSON response parsing -- this proves the integration
6. Per-task logging -- you'll need this immediately for debugging

**Build second (pipeline):**
7. Full waterfall pipeline definition with all stages
8. Review/response cycle with severity classification
9. Circuit breakers (max retry counts)
10. Graceful shutdown and startup reconciliation

**Build third (robustness):**
11. Rewind cascade logic for substantive failures
12. Dead letter queue
13. Job-level progress tracking
14. Token/cost tracking

**Defer indefinitely:**
- Dashboard, priority queues, distributed workers, dynamic routing, saga patterns, plugin systems. See anti-features.

## Sources

- [The Unreasonable Effectiveness of SKIP LOCKED in PostgreSQL](https://www.inferable.ai/blog/posts/postgres-skip-locked)
- [Using FOR UPDATE SKIP LOCKED for Queue-Based Workflows](https://www.netdata.cloud/academy/update-skip-locked/)
- [AI Agent Orchestration Patterns - Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [AI Agents vs. AI Workflows: Why Pipelines Dominate in 2025](https://intuitionlabs.ai/articles/ai-agent-vs-ai-workflow)
- [Circuit Breaker - Martin Fowler](https://martinfowler.com/bliki/CircuitBreaker.html)
- [How to Configure Circuit Breaker Patterns](https://oneuptime.com/blog/post/2026-02-02-circuit-breaker-patterns/view)
- [Workflow Orchestration Best Practices for ETL, ELT, and ML Pipelines](https://www.ml4devs.com/what-is/workflow-orchestration/)
- [Saga Design Pattern Explained - Temporal](https://temporal.io/blog/saga-pattern-made-easy)
- [Workflow Engine vs. State Machine](https://workflowengine.io/blog/workflow-engine-vs-state-machine/)
- [6 Patterns That Turned My Pipeline from Chaotic to Production-Grade](https://medium.com/@wasowski.jarek/building-ai-workflows-neither-programming-nor-prompt-engineering-cdd45d2d314a)
- [Sequential Pipeline Pattern - Google ADK](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/)
