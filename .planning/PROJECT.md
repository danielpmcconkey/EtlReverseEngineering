# ETL Reverse Engineering Orchestrator

## What This Is

A deterministic C# CLI application that orchestrates the AI-driven reverse engineering of 105 ETL jobs from MockEtlFramework. The orchestrator contains zero LLM logic — it's a state machine that manages 6 worker threads, dispatches tasks to Claude CLI agents, and advances each job through a defined workflow based on structured agent responses. Agents produce Python artifacts targeting MockEtlFrameworkPython.

## Core Value

Every job completes its full pipeline — Plan → Define → Design → Build → Validate — with deterministic orchestration that cannot context-rot, cannot fabricate results, and cannot forget its constraints.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Deterministic C# orchestrator with 6 concurrent worker threads
- [ ] Postgres-backed task queue with thread-safe claiming (SELECT ... FOR UPDATE SKIP LOCKED)
- [ ] State machine workflow definition mapping (current_state, outcome) → next_state
- [ ] Per-job isolation — no cross-job contamination
- [ ] Skill registry — discrete C# functions encapsulating prompt template, allowed tools, output schema, model tier, budget cap
- [ ] Agent invocation via `claude -p` with fresh context per task
- [ ] Full per-job waterfall pipeline: Plan → Define → Design → Build → Validate
- [ ] Review/response cycles with severity classification (cosmetic vs substantive)
- [ ] Cosmetic review failures trigger targeted fix-up tasks
- [ ] Substantive review failures rewind to the Write step for that artifact
- [ ] Circuit breakers as guard conditions on state transitions (max retry limits per stage)
- [ ] Structured agent responses (JSON) parsed by the orchestrator
- [ ] Proofmark integration for OG vs RE output validation
- [ ] All 105 jobs processed through the pipeline

### Out of Scope

- LLM-based orchestration — the whole point is deterministic control
- Cross-job dependencies or shared state between pipelines
- Real-time UI or dashboard — CLI output and DB state are sufficient
- Worker prioritization logic — pure FIFO from the queue
- F# — immutable-first doesn't play nice with concurrent mutable state

## Context

**POC5 lesson:** An LLM-based orchestrator (GSD executor) suffered context rot. As conversations grew, the orchestrator lost constraints and fabricated results — copying OG output to fake RE output, writing plausible summaries for unperformed work. This drove the core design decision: the orchestrator must be dumb. All intelligence lives in agents with fresh context per invocation.

**Polyglot reality:** C# orchestrator, Python target artifacts. MockEtlFrameworkPython supports dynamic class loading, eliminating the compile-rebuild human-in-the-middle bottleneck from POC5.

**Infrastructure:**
- Postgres task queue in existing `control` schema (host: 172.18.0.1, port: 5432)
- Claude CLI for agent invocation
- MockEtlFramework (C#) — OG source to reverse engineer
- MockEtlFrameworkPython — target for RE'd artifacts
- proofmark — comparison engine for validation

**Per-job waterfall pipeline:**
Plan (locate sources, inventory outputs/data sources, note dependencies) → Define (write/review BRD) → Design (write/review BDD, write/review FSD) → Build (build/review artifacts, build/review proofmark config, build/review/execute unit tests, publish, final build review) → Validate (execute job runs, execute proofmark, triage failures, final sign-off)

**Re-review cascade logic:** Final build review can trigger re-reviews of BRD/BDD/FSD. Re-review agents return severity (cosmetic/substantive). Cosmetic → fix-up task. Substantive → rewind to Write step for that artifact, cascading downstream steps back into the queue.

## Constraints

- **Tech stack**: C# orchestrator, Python artifacts — no negotiation
- **Concurrency**: 6 worker threads max (CPU/RAM/token budget)
- **Agent model**: Claude CLI subprocess per task, fresh context, no state carried
- **Database**: Existing Postgres instance, `control` schema
- **Hardware**: GTX 1080 (8GB VRAM), running in Docker container

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Deterministic C# orchestrator, not LLM | POC5 context rot proved LLM orchestrators fabricate results | — Pending |
| BDD before FSD | Tests drive the spec, not the other way around | — Pending |
| All agents cite evidence | No unsupported claims — BRD#, BDD scenario#, code refs required | — Pending |
| Review Response agents separate from Write agents | Atomicity — reviewer shouldn't also be the author | — Pending |
| Severity-based re-review cascade | Cosmetic failures get fix-ups, substantive failures rewind to Write step | — Pending |
| 6 concurrent workers | CPU/RAM/token budget constraint | — Pending |
| Pure FIFO queue | No prioritization logic — simplicity over cleverness | — Pending |
| Publish and Locate OG may be deterministic | Some steps might not need LLM agents at all | — Pending |

---
*Last updated: 2026-03-10 after initialization*
