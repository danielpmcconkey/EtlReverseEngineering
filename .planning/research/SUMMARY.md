# Project Research Summary

**Project:** POC6 Workflow Engine
**Domain:** Deterministic state-machine workflow engine for ETL reverse engineering pipeline
**Researched:** 2026-03-13
**Confidence:** HIGH

## Executive Summary

POC6 is a custom deterministic workflow engine that orchestrates 27+ pipeline nodes through a fully specified transition table. The engine's job is to be dumb on purpose -- a rigid state machine that routes jobs through write, review, and validation steps using outcome-based transitions, while agents (stubbed with RNG in v0.1) do the actual thinking. This is a direct reaction to POC5 where LLM-based routing decisions caused context rot. The entire design philosophy is: the orchestrator never decides, it only dispatches.

The recommended approach is to roll a pure-Python state machine with zero framework dependencies. Every state machine library evaluated (pytransitions, python-statemachine) solves the easy part (declaring states) while adding nothing for the hard parts: fail-rewind with replay-forward, FBR gauntlet restart-from-top semantics, conditional-counter auto-promotion to fail, and triage sub-pipeline routing with earliest-fault-wins logic. The total engine code is estimated at 500-800 lines of Python. structlog is the only external runtime dependency.

The critical risks cluster around counter management and rewind semantics. The engine has four distinct counter families (per-node retry, per-review conditional, FBR depth, triage retry), each with different scope and reset rules. Getting counter resets wrong on rewind creates either infinite loops or unfairly punished jobs. The FBR gauntlet's combinatorial path explosion is the second major risk -- depth cap must stay low (2-3) and automated path coverage is essential. Both risks are addressable through careful state model design in Phase 1 and scenario-trace testing throughout.

## Key Findings

### Recommended Stack

Pure Python 3.12 with stdlib dataclasses, enums, and typing. Zero runtime framework dependencies. structlog is the single external dependency for structured JSON logging (explicitly needed for post-hoc agent analysis). Dev tooling: pytest + pytest-cov for testing, ruff for linting/formatting, mypy for static type checking.

**Core technologies:**
- **Python 3.12 + stdlib (dataclasses, enum, typing):** Engine runtime -- zero-dep, full typing support, already in container
- **structlog 25.5.0:** Structured logging -- JSON-native output for machine-parseable transition logs
- **pytest 8.x + pytest-cov:** Testing -- path coverage verification is critical for validating all transition edges
- **ruff + mypy:** Code quality -- the transition table has enough branching that type errors would be painful to debug at runtime

**Explicitly rejected:** pytransitions (callback model doesn't help with rewind/retry), python-statemachine (statechart features irrelevant), Pydantic (no untrusted input to validate), any ORM (v0.1 is in-memory), Temporal/Prefect/Airflow (distributed orchestrators, wrong abstraction level entirely).

### Expected Features

**Must have (table stakes -- engine is broken without these):**
- Transition table as declarative data structure (foundation everything routes through)
- Three-outcome review dispatch (Approve/Conditional/Fail)
- Conditional counter with auto-promote to Fail on 4th occurrence
- Fail-rewind to origin write node with replay-forward (hardest single mechanic)
- FBR gauntlet with restart-from-top and depth cap
- Per-node retry limits with DEAD_LETTER exhaustion
- Triage sub-pipeline (T1-T7) with earliest-fault routing
- Response nodes with most-recent-rejection-only (no errata accumulation)
- Structured transition logging (primary validation artifact)
- Job isolation with sequential execution

**Should have (v0.2, after validation):**
- Transition table validation at startup (catch config bugs before runtime)
- Path coverage reporting (confirm all edges exercised)
- Configurable RNG outcome weights (maximize coverage with tuned profiles)
- Replayable execution logs (debug specific paths deterministically)
- Event hooks/callbacks (prepare for Postgres integration)

**Defer (v1.0+):**
- Postgres task queue, parallel execution, checkpointing, batch statistics

**Anti-features (explicitly do NOT build):**
- Generic workflow DSL/YAML config, LLM-based routing, exponential backoff, parallel execution in v0.1, compensation/saga patterns, errata accumulation, plugin architecture, web UI, database persistence in v0.1

### Architecture Approach

Four-component architecture: Engine (main loop), Transition Resolver (centralized routing logic), Node Registry (state-name-to-executable mapping), and Job State (per-job mutable state bag). The Transition Resolver is the heart -- all branching logic (happy path, conditional routing, fail rewind, FBR restart, triage routing, retry exhaustion) lives in one class with declarative data structures. Nodes are deliberately dumb: execute and return an Outcome enum. They know nothing about transitions, counters, or other nodes.

**Major components:**
1. **Engine** -- Main loop driving the execute-resolve-transition cycle per job
2. **Transition Resolver** -- Centralized transition table + all counter/rewind/routing logic
3. **Node Registry + Node hierarchy** -- Maps state names to executable nodes (WorkNode, ReviewNode, TriageNode, TriageRouterNode)
4. **Job State** -- Per-job mutable state: current node, retry counts, conditional counts, FBR depth, triage context, last rejection reason
5. **Logger** -- Structured log of every transition with full counter state

**Key patterns:** Outcome-driven dispatch (not event-triggered), centralized transition table (not distributed routing), counter state on the job (not on nodes), rewind = set current_node + clear downstream counters (no stack-based undo), explicit FBR context flag (not implicit call-stack inspection).

### Critical Pitfalls

1. **Counter scope confusion** -- Four counter families with different reset rules. A rewind must reset downstream conditional/retry counters but not FBR depth. Solution: explicit CounterPolicy with scope/reset definitions, generation tracking on job state, and scenario-trace unit tests that assert counter values at every node after rewind.

2. **Stale artifacts surviving rewind** -- Rewind re-executes nodes but doesn't inherently invalidate downstream artifacts. Invisible in v0.1 stubs, catastrophic with real agents. Solution: artifact generation counter per node, version consistency assertions. Design in Phase 1, even if stubs don't produce real artifacts.

3. **FBR gauntlet path explosion** -- 6 gates with restart-from-top creates combinatorial path space. Depth cap of 5 produces astronomical path counts. Solution: depth cap of 2-3, automated path enumeration tool, RNG simulation with coverage measurement.

4. **FBR Conditional vs. Fail routing ambiguity** -- In-flow reviews and FBR gates use the same three-outcome model but route differently. DRY instinct leads to a generic handler that gets FBR routing wrong. Solution: per-node transition declarations in the transition table, not type-based routing inference.

5. **Triage state bleed into main pipeline** -- Triage fields bolted onto flat job state create stale diagnostic results on re-entry. Solution: nested TriageContext that is created on triage entry and destroyed on exit.

## Implications for Roadmap

### Phase 1: Foundation -- State Model and Data Structures
**Rationale:** Every pitfall identified points back to "get the state model right first." Counter scope, generation tracking, triage context isolation, and artifact versioning all require upfront design. This is the load-bearing foundation.
**Delivers:** JobState dataclass with generation tracking, Outcome enum, Node ABC, CounterPolicy definitions, transition table data structures (HAPPY_PATH, CONDITIONAL_TARGETS, FAIL_REWIND_TARGETS, FBR_FAIL_TARGETS, TRIAGE_ROUTES), structured logger.
**Addresses:** Transition table as data, job isolation, counter definitions
**Avoids:** Pitfalls 1 (counter scope), 5 (triage state bleed), 7 (orphaned counters)

### Phase 2: Stub Nodes and Happy Path Engine
**Rationale:** Get something running fast. The engine main loop with happy-path-only routing is the first runnable milestone. Every subsequent phase adds to the resolver's resolve() method.
**Delivers:** StubWorkNode, StubReviewNode, StubTriageNode, Node Registry, Engine main loop, happy-path-only transition resolution. Can run N jobs through the pipeline with all-approve/all-success outcomes.
**Addresses:** Three-outcome review dispatch, job isolation, structured logging
**Avoids:** Premature complexity -- prove the loop works before adding branching

### Phase 3: Review Branching -- Conditional and Fail Paths
**Rationale:** Conditional routing and fail-rewind are the two most complex mechanics and the primary validation targets. They depend on the working engine loop from Phase 2.
**Delivers:** Conditional counter with auto-promote, fail-rewind to origin write node, counter reset on rewind, response nodes. The engine now handles all three review outcomes correctly for in-flow reviews.
**Addresses:** Conditional counter, fail-rewind, response nodes, no-errata constraint
**Avoids:** Pitfalls 1 (counter reset on rewind), 2 (artifact invalidation), 7 (generation-scoped counters)

### Phase 4: FBR Gauntlet
**Rationale:** Depends on Phase 3 (reuses conditional/fail routing and response nodes). The gauntlet adds FBR-specific routing: restart-from-top on conditional fix, fbr_return_pending flag, depth cap.
**Delivers:** FBR gates in transition table, FBR fail/conditional routing, gauntlet restart logic, FBR depth cap with DEAD_LETTER.
**Addresses:** FBR gauntlet with restart-from-top, FBR depth cap
**Avoids:** Pitfalls 3 (path explosion -- set cap low), 4 (routing ambiguity -- per-node declarations)

### Phase 5: Triage Sub-Pipeline
**Rationale:** Depends on Phase 3 (reuses fail-rewind logic for T7 routing). Conceptually a nested state machine with its own entry/exit lifecycle.
**Delivers:** T1-T7 nodes, TriageRouterNode with earliest-fault-wins logic, triage context lifecycle (create on entry, destroy on exit), triage retry counter with DEAD_LETTER.
**Addresses:** Triage sub-pipeline, triage retry counter, DEAD_LETTER
**Avoids:** Pitfalls 5 (triage state bleed), 6 (routing ambiguity -- explicit priority enum)

### Phase 6: Retry Exhaustion and DEAD_LETTER Hardening
**Rationale:** Per-node retry limits can be woven in during Phases 3-5 but deserve a dedicated validation pass. This phase hardens all terminal-state paths and ensures no infinite loops exist.
**Delivers:** Per-node retry limits enforced at every node, DEAD_LETTER as verified terminal state, circuit breaker for total node executions per job.
**Addresses:** Per-node retry limits, DEAD_LETTER completeness
**Avoids:** Any remaining infinite loop scenarios

### Phase 7: Validation Run and Coverage
**Rationale:** Run 100+ jobs with RNG outcomes and verify all transition edges are exercised. This is the whole point of v0.1 -- prove the state machine is correct.
**Delivers:** Path coverage report, batch statistics, identification of unexercised edges, configurable RNG weights for targeted coverage.
**Addresses:** Path coverage reporting, batch statistics, RNG weight config
**Avoids:** False confidence from tests that only exercise obvious paths

### Phase Ordering Rationale

- **Phase 1 before everything:** All 7 critical pitfalls trace back to state model design decisions. Getting JobState, CounterPolicy, and the transition table data structures right is non-negotiable before any engine code.
- **Phase 2 early:** The first runnable milestone. Everything after is incremental additions to the resolver.
- **Phase 3 before 4 and 5:** FBR gauntlet and triage both depend on the conditional/fail routing mechanics built in Phase 3. Fail-rewind is reused by triage T7 routing.
- **Phases 4 and 5 are independent of each other** once Phase 3 is complete. Could be built in parallel or either order.
- **Phase 6 as hardening pass:** Retry limits are simple per-counter checks, but verifying all terminal paths requires all other mechanics to be in place.
- **Phase 7 last:** Validation requires the complete engine.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Review Branching):** Counter reset semantics on rewind need scenario-trace design. The transition table specifies what happens but not all counter reset implications. Needs explicit CounterPolicy table before coding.
- **Phase 4 (FBR Gauntlet):** Path enumeration to validate depth cap choice. Need to calculate actual path counts at cap=2 vs cap=3 before committing.
- **Phase 5 (Triage Sub-Pipeline):** T7 routing logic and "earliest fault wins" priority need explicit test scenarios designed against the transition table.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Pure data modeling -- dataclasses, enums, dicts. No unknowns.
- **Phase 2 (Happy Path Engine):** Simple while loop + dict lookups. Well-understood pattern.
- **Phase 6 (Retry/DEAD_LETTER):** Counter checks and terminal state. Straightforward.
- **Phase 7 (Validation Run):** Log analysis and coverage reporting. Standard testing practice.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero-dependency Python engine is an explicit project constraint. structlog is the only decision and it's well-justified. No ambiguity. |
| Features | HIGH | Transition table is fully specified in design docs. Every feature maps directly to a transition table mechanic. No guessing about what to build. |
| Architecture | HIGH | Four-component architecture with centralized resolver is the obvious fit. Design docs are precise enough that this is "translate spec to code." |
| Pitfalls | HIGH | Pitfalls are derived from the actual transition table mechanics, not generic warnings. Counter scope and rewind semantics are genuine risks grounded in the design. |

**Overall confidence:** HIGH -- This is unusually well-specified for a POC. The transition table IS the spec. The architecture research confirms the design docs' approach. The main risk is implementation bugs in counter management and rewind logic, not uncertainty about what to build.

### Gaps to Address

- **Counter reset semantics on rewind:** The transition table specifies rewind targets but doesn't fully specify which counters reset. Need an explicit CounterPolicy table during Phase 1 planning.
- **FBR depth cap value:** Research says "keep it low (2-3)" but the optimal value depends on path count analysis. Calculate during Phase 4 planning.
- **Artifact versioning granularity:** v0.1 stubs don't produce real artifacts, but the version-tracking mechanism needs to be designed now so it's not retrofitted later. How much to implement in v0.1 vs. defer is a judgment call.
- **T7 routing edge cases:** "Multiple faults with earliest-fault-wins" needs explicit test scenarios. What happens when T3 and T6 both fault? Design doc implies T6 is ignored but this needs verification against intent.
- **"No errata accumulation" enforcement mechanism:** The constraint says "most recent rejection only" but the mechanism for ensuring stale rejection reasons don't leak through needs explicit design.

## Sources

### Primary (HIGH confidence)
- POC6 transition table: `/workspace/AtcStrategy/POC6/BDsNotes/state-machine-transitions.md`
- POC6 architecture: `/workspace/AtcStrategy/POC6/BDsNotes/poc6-architecture.md`
- POC6 agent taxonomy: `/workspace/AtcStrategy/POC6/BDsNotes/agent-taxonomy.md`
- [pytransitions/transitions](https://github.com/pytransitions/transitions) -- v0.9.3, evaluated and rejected
- [python-statemachine](https://python-statemachine.readthedocs.io/) -- v3.0.0, evaluated and rejected
- [structlog](https://www.structlog.org/) -- v25.5.0, recommended

### Secondary (MEDIUM confidence)
- [Temporal: Beyond State Machines](https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications) -- durable execution vs FSM tradeoffs
- [Workflow Engine vs State Machine](https://workflowengine.io/blog/workflow-engine-vs-state-machine/) -- pattern classification
- [AWS Step Functions redrive](https://aws.amazon.com/blogs/compute/introducing-aws-step-functions-redrive-a-new-way-to-restart-workflows/) -- rewind/redrive semantics
- [LlamaIndex retry counter reset bug](https://github.com/run-llama/llama_index/issues/20403) -- counter reset pitfall example
- [Dapr Workflow Patterns](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-patterns/) -- retry/compensation patterns

### Tertiary (LOW confidence)
- [State of Workflow Orchestration 2025](https://www.pracdata.io/p/state-of-workflow-orchestration-ecosystem-2025) -- ecosystem context only

---
*Research completed: 2026-03-13*
*Ready for roadmap: yes*
