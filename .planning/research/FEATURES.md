# Feature Research

**Domain:** Deterministic workflow/state-machine engine for ETL reverse engineering pipeline
**Researched:** 2026-03-13
**Confidence:** HIGH (domain-specific engine with well-defined transition table; research grounded in actual design docs + industry patterns)

## Feature Landscape

### Table Stakes (Engine Is Broken Without These)

Features the engine must have or the state machine semantics are wrong/untestable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Transition table as data | The 27 happy-path nodes + failure edges must be declarative, not hardcoded if/else chains. Without this, every edge change requires surgery. | MEDIUM | Dict/enum structure mapping (state, outcome) -> next_state. The transition table doc is already the spec. |
| Three-outcome review dispatch | Approve/Conditional/Fail at every review node. This is the core branching mechanic. | LOW | Each review node returns an enum. Routing is a lookup. |
| Conditional counter with auto-promote | 4th Conditional becomes Fail. Without this, Conditional loops are unbounded. | LOW | Per-node counter, reset on state entry from a non-response path. |
| Fail-rewind to origin write node | Fail must rewind to the original write node and replay the full pipeline forward from there. This is the most complex single mechanic. | HIGH | Requires knowing the "origin write node" for each review node. The transition table encodes this but the engine must walk forward correctly after rewind. |
| FBR gauntlet with restart-from-top | 6 serial gates, any failure routes to response node then restarts from FBR_BrdCheck. Downstream fix invalidates upstream pass. | HIGH | The gauntlet restart is a non-obvious loop. Engine must re-enter FBR_BrdCheck after any gate's fix path completes, not resume where it left off. |
| FBR depth cap | Prevents infinite gauntlet loops. Without this, a persistently failing gate creates an infinite cycle. | LOW | Counter incremented on each FBR_BrdCheck entry. Exhaustion -> DEAD_LETTER. |
| Per-node retry limits | Every node needs a retry budget. Exhaustion -> DEAD_LETTER. Without this, any persistent failure is an infinite loop. | LOW | Simple counter per (job, node). |
| DEAD_LETTER terminal state | Jobs that exhaust retries must land somewhere inspectable, not silently vanish or crash the engine. | LOW | Terminal state. Job stops processing. Metadata preserved. |
| Triage sub-pipeline (T1-T7) | 7-step diagnostic pipeline when ExecuteProofmark fails. Serial sequence with routing logic at T7. | MEDIUM | Essentially a nested state machine. T7 is pure logic (earliest fault wins, no faults -> DEAD_LETTER). |
| Triage retry counter | Triage has its own exhaustion limit, separate from per-node retries. | LOW | Counter incremented on each T1 entry. Exhaustion -> DEAD_LETTER. |
| Response nodes (targeted fix path) | Conditional routes to response node, then back to same reviewer. Writer gets only most recent rejection reason. | LOW | 6 response nodes. Each is a pass-through that receives rejection context. |
| No errata accumulation | Writer receives ONLY the most recent rejection reason. This is a constraint, not a feature, but violating it breaks the "keep agents dumb" principle. | LOW | Engine must NOT accumulate feedback across retries. Only the latest rejection reason is passed. |
| Structured transition logging | Every transition must be logged: job ID, node, outcome, retry counts. This is the primary validation artifact for v0.1. | MEDIUM | Must be structured enough for post-hoc analysis (JSON or similar). Not just print statements. |
| Job isolation | Each of 105 jobs runs its own independent pipeline. No cross-contamination. One job's failure cannot affect another. | LOW | Each job gets its own state + counters. No shared mutable state between jobs. |

### Differentiators (Nice-to-Have / Future Value)

Features that add value but aren't required for the state machine to be correct in v0.1.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Transition table validation at startup | Verify the transition table is well-formed before running any jobs: no orphan states, no missing edges, all review nodes have all three outcome paths. Catches config bugs before runtime. | MEDIUM | Static analysis of the transition dict. Can verify: every state is reachable, every outcome has a target, no cycles without depth caps. |
| Path coverage reporting | After a run, report which transitions were exercised and which weren't. Essential for knowing if RNG actually hit all edge cases. | MEDIUM | Track (state, outcome) pairs seen. Compare against full transition table. Report gaps. |
| State machine visualization | Render the transition table as a graph (DOT/graphviz). Useful for design review and debugging. | LOW | graphviz dot output from the transition dict. One-time utility, not runtime. |
| Replayable execution log | Log format that allows replaying a specific job's execution path deterministically. Feed the same RNG seed, get the same path. | MEDIUM | Requires capturing RNG seed per job. Useful for debugging specific failure paths. |
| Configurable RNG outcome weights | Tune the probability distribution for stub outcomes (e.g., 70% Approve, 20% Conditional, 10% Fail). Different weight profiles exercise different paths. | LOW | Parameterize the RNG. Run multiple profiles to maximize coverage. |
| Job state snapshots / checkpointing | Serialize job state to disk so runs can be resumed after crashes. | MEDIUM | Not needed for v0.1 (in-memory, short runs), but required when real agents + Postgres come in. |
| Dry-run mode | Walk the transition table without executing nodes. Verify routing logic in isolation. | LOW | Skip stub execution, just follow the transition edges with predetermined outcomes. |
| Batch run statistics | After running N jobs, aggregate stats: how many completed, how many DEAD_LETTERed, average path length, most common failure nodes. | LOW | Post-hoc analysis of logs. Trivial if logging is structured. |
| Event hooks / callbacks | Emit events on state transitions that external code can subscribe to. Useful for future Postgres integration, metrics, alerting. | MEDIUM | Decouples the engine from its consumers. Makes the Postgres queue integration cleaner later. |
| Idempotent state transitions | Same input + same state = same output, always. No side effects in the engine itself. | LOW | This should fall out naturally from deterministic design, but explicitly testing it matters. |

### Anti-Features (Do NOT Build These)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Generic workflow DSL / YAML config | "Make it configurable for any workflow." | You have exactly one workflow with exactly one transition table. A generic DSL adds abstraction tax for zero benefit. The transition table IS the config. | Hardcode the transition table as a Python data structure. It's already well-specified. |
| LLM-based routing decisions | "Let the AI decide what to do next." | This is literally what killed POC5. The whole point is a dumb orchestrator. Any intelligence in the control loop reintroduces context rot. | Deterministic lookup tables. All routing is pre-defined. |
| Automatic retry backoff / exponential delay | "Add exponential backoff between retries." | v0.1 is stubs + RNG. There's nothing to back off from. In production, the agents are stateless CLI invocations -- backoff is the wrong abstraction. Retry limits handle persistence. | Simple retry counter with hard cap. No timing. |
| Parallel job execution in v0.1 | "Run all 105 jobs concurrently." | Concurrency adds race conditions, debugging complexity, and non-determinism to a system whose entire purpose is validating deterministic mechanics. | Sequential single-threaded. Validate correctness first. Parallelism is a v0.2+ concern. |
| Compensation / rollback / saga pattern | "Undo completed steps on failure." | There's nothing to undo. Steps produce artifacts (documents). A "fail" doesn't need to delete the old BRD -- the rewrite replaces it. Compensation adds complexity for a problem that doesn't exist here. | Rewind-and-rewrite. The new artifact overwrites the old one. No undo needed. |
| Errata accumulation across retries | "Give the writer ALL previous feedback so it learns." | Explicitly rejected in the design. Accumulated context is how agents get confused and fabricate. Fresh context per invocation is a core constraint. | Most recent rejection reason only. Retry counter is the only memory. |
| Plugin architecture / extensibility framework | "Make nodes pluggable so anyone can add new ones." | One user (Dan), one pipeline, one purpose. Plugin overhead is pure waste. | Direct function references in the transition table. Add nodes by editing the table. |
| Web UI / dashboard | "Visualize job progress in real time." | v0.1 validation happens by reading logs. A UI is months of work for a POC that might pivot. | Structured logs + post-hoc analysis scripts. |
| Database persistence in v0.1 | "Use Postgres from the start." | Validate mechanics first, infrastructure second. Postgres adds connection management, schema migration, and deployment concerns to a prototype. | In-memory dicts. Postgres is explicitly out of scope for v0.1. |

## Feature Dependencies

```
[Transition table as data]
    └──requires──> [Three-outcome review dispatch]
    └──requires──> [Fail-rewind to origin write node]
    └──requires──> [FBR gauntlet with restart-from-top]

[Conditional counter with auto-promote]
    └──requires──> [Three-outcome review dispatch]
    └──requires──> [Per-node retry limits]  (auto-promoted Fail uses same retry budget)

[FBR gauntlet with restart-from-top]
    └──requires──> [Response nodes (targeted fix path)]
    └──requires──> [FBR depth cap]

[Triage sub-pipeline (T1-T7)]
    └──requires──> [Triage retry counter]
    └──requires──> [Fail-rewind to origin write node]  (T7 routes to origin write nodes)
    └──requires──> [DEAD_LETTER terminal state]  (no faults -> DEAD_LETTER)

[Structured transition logging]
    └──enhances──> [Path coverage reporting]
    └──enhances──> [Batch run statistics]
    └──enhances──> [Replayable execution log]

[Transition table validation at startup]
    └──requires──> [Transition table as data]

[Job isolation]
    └──conflicts──> [Parallel job execution in v0.1]
    (isolation is trivial in sequential; parallelism makes it a real engineering problem)
```

### Dependency Notes

- **Conditional counter requires three-outcome dispatch:** Can't count Conditionals if the review model doesn't produce them.
- **FBR gauntlet requires response nodes:** Conditional at any FBR gate routes through a response node before gauntlet restart.
- **Triage requires fail-rewind:** T7 routing sends jobs back to origin write nodes, reusing the same rewind mechanic.
- **Path coverage requires structured logging:** Coverage analysis is post-hoc log parsing. Garbage logs = no coverage data.
- **Transition table validation requires table-as-data:** Can only validate the table statically if it's a data structure, not scattered if/else.

## MVP Definition

### Launch With (v0.1)

Minimum to validate: "the state machine correctly implements the transition table."

- [ ] Transition table as data structure — the foundation everything routes through
- [ ] Three-outcome review dispatch — core branching mechanic
- [ ] Conditional counter with auto-promote to Fail — prevents Conditional loops
- [ ] Fail-rewind to origin write node — the hardest mechanic, must be validated early
- [ ] FBR gauntlet with restart-from-top — second hardest mechanic
- [ ] FBR depth cap — prevents infinite gauntlet loops
- [ ] Per-node retry limits with DEAD_LETTER — prevents all infinite loops
- [ ] Triage sub-pipeline (T1-T7) with routing and retry counter — nested state machine
- [ ] Response nodes with most-recent-rejection-only — Conditional fix path
- [ ] Structured transition logging — the validation artifact
- [ ] Job isolation (sequential execution of N jobs) — prove no cross-contamination
- [ ] Stubbed nodes with RNG outcomes — exercise all paths without real agents

### Add After Validation (v0.2)

Features to add once the state machine is proven correct.

- [ ] Transition table validation at startup — when adding real complexity, catch config bugs early
- [ ] Path coverage reporting — confirm all edges were exercised across test runs
- [ ] Configurable RNG weights — tune profiles to maximize coverage
- [ ] Replayable execution log — debug specific failure paths deterministically
- [ ] Event hooks / callbacks — prepare for Postgres integration

### Future Consideration (v1.0 — Real Agents)

- [ ] Postgres task queue integration — replace in-memory state
- [ ] Parallel job execution — concurrent workers with isolation guarantees
- [ ] Job state checkpointing — crash recovery for long-running real agent invocations
- [ ] Batch run statistics — operational monitoring at scale

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Transition table as data | HIGH | MEDIUM | P1 |
| Three-outcome review dispatch | HIGH | LOW | P1 |
| Conditional counter + auto-promote | HIGH | LOW | P1 |
| Fail-rewind to origin | HIGH | HIGH | P1 |
| FBR gauntlet + restart | HIGH | HIGH | P1 |
| FBR depth cap | HIGH | LOW | P1 |
| Per-node retry limits | HIGH | LOW | P1 |
| DEAD_LETTER terminal | HIGH | LOW | P1 |
| Triage sub-pipeline | HIGH | MEDIUM | P1 |
| Triage retry counter | HIGH | LOW | P1 |
| Response nodes | HIGH | LOW | P1 |
| No errata (constraint) | HIGH | LOW | P1 |
| Structured logging | HIGH | MEDIUM | P1 |
| Job isolation | HIGH | LOW | P1 |
| Transition table validation | MEDIUM | MEDIUM | P2 |
| Path coverage reporting | MEDIUM | MEDIUM | P2 |
| RNG weight config | LOW | LOW | P2 |
| Replayable execution log | MEDIUM | MEDIUM | P2 |
| Event hooks | MEDIUM | MEDIUM | P2 |
| State visualization | LOW | LOW | P3 |
| Dry-run mode | LOW | LOW | P3 |
| Batch statistics | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for v0.1 launch (validates state machine correctness)
- P2: Should have after v0.1 validates (improves debuggability and prepares for v1.0)
- P3: Nice to have, add when convenient

## Competitor Feature Analysis

This isn't a product competing in a market -- it's a bespoke engine. But the design borrows from and deliberately rejects patterns in established workflow engines.

| Feature | Temporal / Cadence | Airflow / Prefect | This Engine |
|---------|-------------------|-------------------|-------------|
| State persistence | Event-sourced durable history | DB-backed DAG runs | In-memory dicts (v0.1), Postgres (v1.0) |
| Retry semantics | Activity-level with backoff policies | Task-level with configurable retries | Per-node counter, hard cap, no backoff |
| Failure handling | Compensation / saga pattern | Task retry + upstream clearing | Rewind-to-origin + replay forward |
| Routing logic | Code-based (workflow-as-code) | DAG definition (declarative) | Transition table lookup (declarative) |
| Observability | Built-in UI + event history | Built-in UI + logs | Structured logs only (v0.1) |
| Concurrency | Native async, worker pools | Celery / K8s executors | Sequential (v0.1), capped parallelism (v1.0) |
| Review / human-in-loop | Signals + queries | Sensors + external triggers | Three-outcome review nodes (agent-based, human-equivalent) |
| Dead letter handling | Not built-in (use error handlers) | Not built-in (mark as failed) | First-class DEAD_LETTER state |
| Nested workflows | Child workflows | SubDAGs (deprecated) / TaskGroups | Triage sub-pipeline (nested state machine) |

Key insight: Temporal's durable execution and Airflow's DAG model are both overkill here. This engine needs something simpler -- a finite state machine with a well-defined transition table, not a general-purpose orchestration framework. The rewind-on-fail mechanic is unusual (most engines don't replay forward from an earlier state) and is the primary thing that makes this engine domain-specific.

## Sources

- [Temporal: Beyond State Machines](https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications) — Temporal's argument for durable execution over FSMs
- [Workflow Engine Design Principles](https://temporal.io/blog/workflow-engine-principles) — Core principles for workflow engine design
- [Workflow Engine vs State Machine](https://workflowengine.io/blog/workflow-engine-vs-state-machine/) — Distinction between workflow engines and state machines
- [Dapr Workflow Patterns](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-patterns/) — Retry, fan-out, compensation patterns
- [State Transition Testing Guide](https://www.f22labs.com/blogs/state-transition-testing-techniques-in-software-testing-ultimate-guide/) — Coverage criteria for state-based testing
- [Error Handling in Distributed Systems](https://temporal.io/blog/error-handling-in-distributed-systems) — Retry and compensation patterns
- [State of Workflow Orchestration 2025](https://www.pracdata.io/p/state-of-workflow-orchestration-ecosystem-2025) — Ecosystem overview
- [pytransitions/transitions](https://github.com/pytransitions/transitions) — Python FSM library (reference, not recommended for use)
- [python-statemachine](https://pypi.org/project/python-statemachine/) — Python FSM library (reference, not recommended for use)
- POC6 design docs: `state-machine-transitions.md`, `poc6-architecture.md`, `PROJECT.md`

---
*Feature research for: Deterministic workflow/state-machine engine for ETL reverse engineering*
*Researched: 2026-03-13*
