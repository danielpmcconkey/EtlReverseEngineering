# POC6 Workflow Engine

## What This Is

A pure Python deterministic workflow engine that orchestrates the ETL reverse engineering pipeline for 105 jobs. The engine is a state machine — no LLM in the control loop. It drives each job through a defined waterfall (Plan → Define → Design → Build → Validate), dispatching atomic agents that claim a task, do one thing, and die. v0.1 validates the state machine mechanics with stubbed nodes and RNG outcomes before any real agents or infrastructure are connected.

## Core Value

The state machine correctly implements the transition table — rewinds, conditional loops, FBR gauntlet restarts, triage routing, and DEAD_LETTER on retry exhaustion all behave as designed.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Deterministic state machine with 27 happy-path nodes matching the transition table
- [ ] Three-outcome review model: Approve / Conditional (3 max) / Fail at every review node
- [ ] 4th Conditional auto-promotes to Fail
- [ ] Fail rewinds to the original write node and replays the full pipeline forward
- [ ] Conditional routes to response node → same reviewer, no downstream invalidation
- [ ] FinalBuildReview gauntlet: 6 serial gates, any failure restarts from FBR_BrdCheck
- [ ] FBR depth cap prevents infinite gauntlet loops
- [ ] 7-step proofmark triage sub-pipeline (T1-T7)
- [ ] Triage routing: earliest fault wins, no faults → DEAD_LETTER
- [ ] Two counter types: main retry (N, per job) and conditional (M, per node instance)
- [ ] Main retry increments on any full Fail; reaching N → DEAD_LETTER
- [ ] Conditional counter reaching M auto-promotes to Fail (incrementing main retry)
- [ ] Conditional counters reset to 0 on success or on rewind past that node
- [ ] N and M are configurable with sensible defaults
- [ ] Stubbed nodes: review nodes return RNG Approve/Conditional/Fail, non-review return RNG Success/Failure
- [ ] Logging: job ID, node name, outcome, retry counts, transitions (structured enough for post-hoc agent analysis)
- [ ] Run N jobs through full pipeline to exercise all paths
- [ ] Writer/response nodes receive only the most recent rejection reason — no errata accumulation
- [ ] Source lives at `src/workflow_engine/`

### Out of Scope

- Postgres task queue — v0.1 uses in-memory job state
- Claude CLI agent invocation — stubs only
- Real agent blueprints — stubs have comments describing future behavior
- Parallelism / concurrency — single-threaded sequential for v0.1
- Proofmark integration — triage sub-pipeline is stubbed
- MockEtlFrameworkPython integration — no real artifact production
- Automated assertions — logs are the validation artifact, agents analyze post-hoc

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
*Last updated: 2026-03-13 after initialization*
