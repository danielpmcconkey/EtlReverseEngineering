# POC6 Workflow Engine

## What This Is

A pure Python deterministic workflow engine that orchestrates the ETL reverse engineering pipeline for 103 jobs. The engine is a state machine — no LLM in the control loop. It drives each job through a defined waterfall (Plan → Define → Design → Build → Validate), dispatching atomic agents that claim a task, do one thing, and die. v0.1 validated the state machine mechanics with stubbed nodes. v0.2 replaces the synchronous execution model with a Postgres-backed task queue and multi-threaded worker pool so multiple jobs run concurrently.

## Core Value

A constant swarm of worker threads processes jobs concurrently through the validated state machine — no worker ever blocks waiting on another, and the system scales by adding workers.

## Current Milestone: v0.2 Parallel Execution Infrastructure

**Goal:** Replace the synchronous single-threaded engine with a Postgres task queue and multi-threaded worker pool that processes jobs concurrently.

**Target features:**
- Postgres `re_task_queue` table with `SELECT ... FOR UPDATE SKIP LOCKED` claiming
- Postgres-backed job state (replaces in-memory JobState)
- N configurable worker threads (default 6) monitoring the queue
- Job manifest JSON ingestion — load manifest, enqueue first node for every job
- All v0.1 state machine logic preserved, invoked per-step through the queue

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Deterministic state machine with 27 happy-path nodes — v0.1
- ✓ Three-outcome review model (Approve/Conditional/Fail) with counter mechanics — v0.1
- ✓ FBR 6-gate gauntlet with restart semantics — v0.1
- ✓ 7-step triage sub-pipeline with earliest-fault routing — v0.1
- ✓ Structured logging sufficient for post-hoc analysis — v0.1

### Active

<!-- Current scope. Building toward these. -->

- [ ] Postgres task queue with FIFO claiming
- [ ] Postgres-backed job state
- [ ] Multi-threaded worker pool (default 6, configurable)
- [ ] Job manifest JSON ingestion
- [ ] State machine logic preserved through queue-based execution
- [ ] Engine integration tests rewritten for queue-based model

### Out of Scope

- Claude CLI agent invocation — stubs only, de-stubbing is a future milestone
- Real agent blueprints — stubs have comments describing future behavior
- Proofmark integration — triage sub-pipeline is stubbed
- MockEtlFrameworkPython integration — no real artifact production

## Context

**POC5 failure:** An LLM-based orchestrator (GSD executor) suffered context rot. As conversations grew, the orchestrator lost constraints and fabricated results — copying OG output to fake RE output, writing plausible summaries for unperformed work. This drove the core design decision: the orchestrator must be dumb. All intelligence lives in agents with fresh context per invocation.

**The flip:** POC5 ran 1 waterfall to RE 105 jobs (vertical). POC6 runs 105 waterfalls to RE 1 job each (horizontal). Each job gets its own full lifecycle pipeline. No job's failure contaminates another.

**Infrastructure context (not used in v0.1 but informs design):**
- Postgres task queue at 172.18.0.1:5432 (control schema)
- Claude CLI for agent invocation (`claude -p` with per-agent blueprints)
- MockEtlFramework (C# OG) at `/workspace/MockEtlFramework/`
- MockEtlFrameworkPython (RE target) at `/workspace/MockEtlFrameworkPython/`
- OG output (answer key): `/workspace/og-curated/` (read-only)
- RE output: `/workspace/re-curated/` (read-only, framework writes here)

**Design documents:**
- Transition table: `/workspace/AtcStrategy/POC6/BDsNotes/state-machine-transitions.md`
- Agent taxonomy: `/workspace/AtcStrategy/POC6/BDsNotes/agent-taxonomy.md`
- Architecture: `/workspace/AtcStrategy/POC6/BDsNotes/poc6-architecture.md`
- State overview: `/workspace/AtcStrategy/POC6/BDsNotes/state-of-poc6.md`

## Constraints

- **Language**: Pure Python — no external frameworks for the engine itself
- **No LLM in control loop**: The orchestrator is deterministic. Period.
- **No errata**: Writer gets only the most recent rejection reason. Retry counter is the only memory.
- **Fresh context**: Every agent invocation starts clean. No state carried between invocations.
- **v0.1 boundary**: Stubs + RNG only. No real infrastructure, no real agents, no real cost.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Dumb orchestrator, no LLM | POC5 context rot proved LLM orchestrators fabricate results | — Pending |
| Three-outcome review (Approve/Conditional/Fail) | Conditional = targeted fix, Fail = full rewrite. Granularity prevents over-punishment | — Pending |
| 4th Conditional → auto-Fail | Prevents infinite conditional loops while giving 3 honest chances | — Pending |
| FBR restarts from top of gauntlet | Downstream fix could invalidate upstream pass | — Pending |
| Triage routes to earliest fault | Higher faults cascade further; fix the root first | — Pending |
| No errata accumulation | Keep agents dumb. Let retry limits handle persistent failures | — Pending |
| Logs as validation artifact | Human reads logs or background agents analyze post-hoc. No automated assertions in v0.1 | — Pending |
| In-memory job state for v0.1 | Postgres comes later. Validate mechanics first, infrastructure second | — Pending |

---
*Last updated: 2026-03-14 after v0.2 milestone start*
