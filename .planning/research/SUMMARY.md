# Project Research Summary

**Project:** ETL Reverse Engineering Orchestrator
**Domain:** Deterministic task orchestrator for AI-agent-driven ETL reverse engineering pipelines
**Researched:** 2026-03-10
**Confidence:** HIGH

## Executive Summary

This project is a deterministic CLI orchestrator that drives 105 ETL reverse-engineering jobs through a waterfall pipeline (Plan, Define, Design, Build, Validate) using Claude CLI subprocesses as the execution engine. The core design insight -- and the entire reason this exists -- is that the orchestrator must be dumb. Intelligence lives in ephemeral agent subprocesses with zero retained state. The orchestrator is a state machine lookup table backed by a Postgres task queue. Experts build systems like this using the `SELECT ... FOR UPDATE SKIP LOCKED` pattern for work claiming, fixed worker pools for bounded concurrency, and subprocess isolation to prevent the context rot that killed POC5.

The recommended approach is a five-layer .NET 8 / C# 12 application: CLI entry point, orchestrator loop, worker pool (6 threads), task queue (Postgres), and agent dispatcher (Claude CLI via CliWrap). The stack is deliberately lean -- Npgsql for database access (no ORM), a plain Dictionary for the state machine transition table (no framework), System.Threading.Channels for producer-consumer dispatch, and CliWrap for subprocess management. Every technology choice optimizes for simplicity and debuggability over abstraction.

The primary risks are: (1) Claude CLI output parsing failures corrupting the task pipeline, (2) zombie Claude subprocesses accumulating and degrading worker capacity, (3) database lock holding during long agent invocations causing resource exhaustion, and (4) rewind cascade loops where writer and reviewer agents produce irreconcilable output. All four have well-documented prevention strategies. The system's crash resilience comes from Postgres being the single source of truth -- if the process dies, restart it and workers resume from where they left off.

## Key Findings

### Recommended Stack

The stack is .NET 8 LTS with minimal external dependencies. The philosophy: if it ships with the runtime, use it. Only pull in packages that solve genuinely hard problems (subprocess pipe deadlocks, structured logging enrichment, state machine edge cases).

**Core technologies:**
- **.NET 8.0 / C# 12**: Already installed in container, LTS through Nov 2026. No .NET 10 features needed for a CLI orchestrator.
- **Npgsql 8.0.x**: Direct PostgreSQL driver. No ORM -- this is a task queue, not a CRUD app. Raw SQL with locking primitives.
- **CliWrap 3.10.0**: Subprocess management for `claude -p`. Solves the stdout/stderr deadlock problem that raw Process.Start is notorious for.
- **Serilog 4.3.1**: Structured logging with per-job context enrichment (job ID, stage, worker ID on every log entry).
- **System.Threading.Channels**: Built-in producer-consumer dispatch. Bounded channel with capacity 6 provides natural backpressure.
- **System.Text.Json**: Built-in JSON parsing. Agent responses deserialize into strongly-typed C# records.
- **System.CommandLine 2.0.0-beta**: CLI argument parsing. Still beta but stable enough, gives `--help` for free.

**Notable research conflict -- Stateless library:**
STACK.md recommends the Stateless NuGet package (5.20.1) for the state machine. ARCHITECTURE.md explicitly argues against it, recommending a plain `Dictionary<(string, string), string[]>` instead. The architecture researcher's argument is stronger: this workflow is a static lookup table, not a runtime-configurable state machine. Stateless adds ceremony and indirection for features (hierarchical states, parameterized triggers, entry/exit actions) that this project doesn't need. **Recommendation: use the dictionary approach.** It's more testable, more inspectable, and more obvious. Drop Stateless from the dependency list.

See: `.planning/research/STACK.md`

### Expected Features

**Must have (table stakes):**
- Postgres-backed task queue with SKIP LOCKED claiming
- State machine with explicit, deterministic transition table
- Concurrent worker pool (6 threads, bounded)
- Per-task agent isolation (fresh subprocess, zero context carryover)
- Structured JSON agent responses with schema validation
- Circuit breakers (max retry per stage per artifact)
- Task state persistence and crash recovery
- Idempotent task execution (overwrite, not append)
- Graceful shutdown with CancellationToken propagation
- Per-task logging (agent stdout/stderr to files)
- Skill registry (prompt template, model tier, budget cap, timeout per task type)
- Waterfall pipeline definition with stage handoffs
- Review/response cycle with cosmetic vs. substantive severity classification

**Should have (differentiators):**
- Dead letter queue for permanently failed tasks
- Job-level progress tracking (CLI status queries)
- Token/cost tracking per task invocation
- Artifact versioning (keep previous versions on rewind)
- Startup state reconciliation (reclaim orphaned tasks)
- Dry-run mode (validate pipeline without invoking agents)
- Configurable model tier per skill (Opus for complex, Sonnet for rote)
- Pause/resume per job
- Deterministic-only skill type (no agent needed for some steps)
- Heartbeat/liveness monitoring for long-running tasks

**Defer indefinitely:**
- Web dashboard / real-time UI
- Priority queue / weighted scheduling (FIFO is correct)
- Cross-job dependency graph (jobs are independent)
- Dynamic agent chaining / LLM-decided routing (the POC5 anti-pattern)
- Distributed workers across machines
- Event-driven / pub-sub architecture
- Plugin / extension system

See: `.planning/research/FEATURES.md`

### Architecture Approach

Five-layer architecture with strict component boundaries: CLI entry point, orchestrator loop (main thread), worker pool (6 dedicated threads), state machine engine (pure lookup table), and agent dispatcher (subprocess spawner). The critical constraint is that no layer skips another. Workers are identical drones running Claim-Execute-Advance loops. All state lives in Postgres. All intelligence lives in ephemeral agent subprocesses. The orchestrator carries no mutable in-memory state between iterations.

**Major components:**
1. **Task Queue (Postgres)** -- Durable task storage with atomic claiming via SKIP LOCKED. Three tables: tasks, circuit_breakers, job_state.
2. **State Machine Engine** -- Dictionary-based transition table mapping (task_type, outcome) to next_task_type[]. Pure function, no side effects, thread-safe by construction.
3. **Worker Pool** -- 6 dedicated threads (not async Task.Run) running identical work loops. Each worker owns its own NpgsqlConnection.
4. **Agent Dispatcher** -- Thin wrapper around CliWrap that assembles prompts from skill templates, spawns `claude -p`, captures output, parses JSON.
5. **Skill Registry** -- Immutable dictionary loaded at startup mapping task types to prompt templates, allowed tools, output schemas, model tiers, budget caps, and timeouts.

**Key architectural decision -- dedicated threads over async:** Workers block on Claude CLI subprocesses for 30-120+ seconds. Using async/await with blocking subprocess calls would starve the .NET thread pool. Dedicated Thread instances make the concurrency model explicit and avoid thread pool starvation.

See: `.planning/research/ARCHITECTURE.md`

### Critical Pitfalls

1. **Claude CLI output is not reliably JSON** -- Even with `--output-format json`, expect preamble, Unicode corruption, and stderr contamination. Build a resilient parser that strips non-JSON content, separates stderr, and treats parse failure as a distinct outcome type with its own retry path. Must be solved in the first phase.

2. **Zombie Claude CLI processes** -- Subprocesses can hang forever on model timeouts or network issues. Always use `Process.WaitForExit(timeoutMs)` with finite timeout, kill the entire process tree on timeout, track spawned PIDs, and sweep for orphans on startup.

3. **Holding database locks during agent invocations** -- Naive single-transaction claim-process-complete holds row locks for minutes. Use the three-phase pattern: short transaction to claim, work outside transaction, short transaction to record results.

4. **Non-idempotent task execution** -- At-least-once delivery means tasks can run twice. All artifact writes must be idempotent (deterministic paths, overwrite not append, atomic rename from temp). Use execution IDs to detect and discard stale results.

5. **Rewind cascade infinite loops** -- Writer and reviewer agents can disagree forever. Circuit breakers must be per-stage AND per-artifact. After N rewrites of the same artifact, escalate strategy (different prompt/model) rather than repeating. Pass previous review feedback into rewrite prompts.

See: `.planning/research/PITFALLS.md`

## Implications for Roadmap

Based on research, the build order is bottom-up following dependency flow. The architecture layers cleanly into phases where each phase is testable independently before the next begins.

### Phase 1: Database Foundation
**Rationale:** Everything depends on the Postgres task queue. It's the single source of truth, the coordination mechanism, and the crash recovery layer. Build and test it first in isolation.
**Delivers:** Schema (tasks, circuit_breakers, job_state tables), partial index, TaskQueue class (claim, complete, fail, stale sweep), concurrent claim simulation tests.
**Addresses:** Task queue, task state persistence, startup reconciliation.
**Avoids:** Pitfall #3 (lock holding -- three-phase claim pattern designed from day one), Pitfall #7 (SKIP LOCKED indexing).

### Phase 2: State Machine and Pipeline Definition
**Rationale:** The transition table is the brain of the system. It must be defined and tested before any worker or agent code exists. This phase validates the entire workflow logic with deterministic unit tests.
**Delivers:** Transition table dictionary, StateMachine.Advance() method, circuit breaker logic, failure taxonomy (Success, ParseFailure, InfraFailure, QualityFailure, CapabilityFailure, Timeout), integration tests that seed tasks and verify pipeline progression.
**Addresses:** State machine, circuit breakers, review/severity classification, waterfall pipeline.
**Avoids:** Pitfall #5 (rewind cascade loops -- per-artifact circuit breakers), Pitfall #8 (conflated failure types -- distinct outcome taxonomy).

### Phase 3: Worker Infrastructure
**Rationale:** Workers need the queue and state machine but not agents. Build the Claim-Execute-Advance loop with mock executors first. This validates concurrency, shutdown, and error handling without burning tokens.
**Delivers:** Worker loop, worker pool with 6 dedicated threads, orchestrator lifecycle management, graceful shutdown (CancellationToken), stale task recovery, supervisor pattern for dead thread respawn.
**Addresses:** Concurrent worker pool, graceful shutdown, idempotent execution.
**Avoids:** Pitfall #6 (worker thread death), Pitfall #13 (shutdown corruption), Pitfall #11 (state desync).

### Phase 4: Agent Integration
**Rationale:** This is the integration boundary where mocking gives way to real Claude CLI calls. The riskiest phase -- Claude CLI output parsing and subprocess management are the top two critical pitfalls.
**Delivers:** Skill registry, agent dispatcher (CliWrap wrapper), JSON response parser with resilient non-JSON stripping, subprocess timeout and kill logic, PID tracking, per-task log files (agent stdout/stderr).
**Addresses:** Per-task agent isolation, structured JSON responses, per-task logging, skill registry, configurable model tier.
**Avoids:** Pitfall #1 (JSON parsing failures), Pitfall #2 (zombie processes), Pitfall #9 (file system isolation), Pitfall #10 (token budget burn).

### Phase 5: Full Pipeline and Rewind Logic
**Rationale:** With all components proven individually, wire them together for end-to-end pipeline execution. The rewind cascade is the most complex control flow and needs real agent behavior to tune.
**Delivers:** All skill definitions for all task types, re-review cascade logic with depth caps, full pipeline test (1 job through all stages), multi-job concurrency test, dead letter queue, artifact versioning.
**Addresses:** Rewind cascade, dead letter queue, artifact versioning, deterministic-only steps.
**Avoids:** Pitfall #5 (cascade loops -- tuned with real agent data).

### Phase 6: Production Run
**Rationale:** Everything is proven. Seed all 105 jobs, add operational tooling, and execute.
**Delivers:** Job seeding for all 105 ETL jobs, CLI status/progress commands, token/cost tracking, dry-run mode, pause/resume per job, proofmark integration for validation stage.
**Addresses:** Job-level progress tracking, token tracking, dry-run mode, pause/resume, proofmark validation.
**Avoids:** Pitfall #12 (proofmark ordering -- guard conditions on validation entry).

### Phase Ordering Rationale

- **Bottom-up by dependency:** Queue before state machine, state machine before workers, workers before agents. Each layer is testable without the layer above.
- **Deterministic before non-deterministic:** Phases 1-3 require zero Claude CLI interaction and can be validated with unit/integration tests. Phase 4 introduces the non-deterministic element.
- **Cheap before expensive:** Testing the orchestration logic with mock agents costs nothing. Testing with real agents burns tokens. Get the plumbing right first.
- **Simple before complex:** Basic pipeline flow before rewind cascades. The cascade logic needs real agent behavior data to tune circuit breaker thresholds.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Agent Integration):** The exact `claude -p` flags for tool restriction, model selection, and output format need verification against current Claude CLI documentation. The `--output-format json` behavior and `structured_output` key parsing need empirical testing.
- **Phase 5 (Rewind Logic):** The cascade depth caps and circuit breaker thresholds are guesses until real agent behavior is observed. Plan for tuning iterations.
- **Phase 6 (Proofmark Integration):** Proofmark's execution model and output comparison format need research during this phase.

Phases with standard, well-documented patterns (skip additional research):
- **Phase 1 (Database Foundation):** SKIP LOCKED queue pattern is battle-tested. Multiple production implementations exist (Solid Queue, Graphile Worker, River).
- **Phase 2 (State Machine):** Dictionary-based transition table is trivial. No framework needed.
- **Phase 3 (Worker Infrastructure):** Dedicated thread pools with CancellationToken are standard .NET patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All packages verified on NuGet with version numbers. .NET 8 LTS timeline confirmed. Only uncertainty is System.CommandLine beta status (low risk). |
| Features | HIGH | Feature landscape well-defined. Clear separation between table stakes, differentiators, and anti-features. MVP path is unambiguous. |
| Architecture | HIGH | Component boundaries are clean. Data flow is well-documented. The five-layer decomposition follows established patterns. Postgres-as-truth is proven. |
| Pitfalls | HIGH | 13 pitfalls identified with specific prevention strategies. Sources include official .NET runtime issues, real-world Claude CLI wrapper failures, and established architecture patterns. |

**Overall confidence:** HIGH

### Gaps to Address

- **Claude CLI `--output-format json` reliability:** Research identified the risk (Pitfall #1) but actual failure rates need empirical measurement. Build the resilient parser, then measure during Phase 4 integration testing.
- **Stateless vs. Dictionary resolution:** Stack and Architecture research disagree on the state machine approach. Recommendation is Dictionary (see Key Findings), but this should be confirmed during Phase 2 planning.
- **Claude CLI tool restriction flags:** The exact mechanism for constraining agent tool access per skill (`--allowedTools` or equivalent) needs verification against current CLI docs.
- **Rewind cascade thresholds:** Circuit breaker limits for per-artifact rewrites are undefined. Need real agent data from Phase 4 before tuning in Phase 5.
- **Polly necessity:** Deferred from the stack. May need transient fault handling for Claude CLI infrastructure failures (network timeouts, rate limits). Evaluate after Phase 4.

## Sources

### Primary (HIGH confidence)
- [PostgreSQL Explicit Locking docs](https://www.postgresql.org/docs/current/explicit-locking.html) -- SKIP LOCKED semantics
- [Microsoft: System.Threading.Channels](https://learn.microsoft.com/en-us/dotnet/core/extensions/channels) -- producer-consumer pattern
- [Microsoft: Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker) -- resilience patterns
- [Npgsql official docs](https://www.npgsql.org/doc/basic-usage.html) -- connection pooling, NpgsqlDataSource
- [NuGet: Stateless 5.20.1](https://www.nuget.org/packages/stateless/) -- evaluated and rejected
- [NuGet: CliWrap 3.10.0](https://www.nuget.org/packages/CliWrap) -- subprocess management
- [NuGet: Serilog 4.3.1](https://www.nuget.org/packages/serilog/) -- structured logging
- [.NET Runtime Issue #29232](https://github.com/dotnet/runtime/issues/29232) -- WaitForExit async stdout bug
- [.NET Runtime Issue #81896](https://github.com/dotnet/runtime/issues/81896) -- Process stdout/stderr deadlock

### Secondary (MEDIUM confidence)
- [The Unreasonable Effectiveness of SKIP LOCKED](https://www.inferable.ai/blog/posts/postgres-skip-locked) -- queue patterns
- [River: Go + Postgres job queue](https://brandur.org/river) -- architectural influence
- [Vlad Mihalcea: Database Job Queue SKIP LOCKED](https://vladmihalcea.com/database-job-queue-skip-locked/) -- queue implementation
- [Claude CLI JSON parsing failures](https://github.com/eyaltoledano/claude-task-master/issues/1223) -- real-world failure modes
- [Claude Code JSON output corruption](https://github.com/anthropics/claude-code/issues/25025) -- stderr contamination
- [AI Agent Orchestration Patterns - Azure](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) -- orchestration patterns

### Tertiary (needs validation)
- Claude CLI `--output-format json` exact behavior and `structured_output` key format -- needs empirical testing
- Claude CLI tool restriction mechanism -- needs current docs verification
- Optimal circuit breaker thresholds for LLM agent rewrite cycles -- needs production data

---
*Research completed: 2026-03-10*
*Ready for roadmap: yes*
