# Technology Stack

**Project:** POC6 Workflow Engine
**Researched:** 2026-03-13

## TL;DR Recommendation

Roll your own state machine in pure Python. Use dataclasses for state, structlog for logging, pytest for testing. No state machine library. No workflow framework.

## The Build vs. Buy Decision

### Why NOT pytransitions (transitions 0.9.3)

| Factor | Assessment |
|--------|-----------|
| **What it gives you** | State/transition declarations, callbacks, conditions, hierarchical states, visualization |
| **What it doesn't give you** | Rewind semantics, retry counters, conditional-limit promotion, FBR gauntlet restart logic, triage sub-pipeline routing |
| **The problem** | Your transition table has 27+ happy-path nodes, 7 response nodes, a 6-gate gauntlet with restart-from-top semantics, a 7-step triage sub-pipeline with earliest-fault routing, three-outcome reviews with auto-promotion on the 4th conditional, and per-node retry counters with exhaustion to DEAD_LETTER. pytransitions gives you `Machine(states=..., transitions=...)` and callbacks. Every piece of your actual complexity lives in the callbacks. The library becomes ceremony around the only easy part (declaring states) while adding zero value for the hard parts (rewind, retry, counter management, gauntlet logic). |
| **Abstraction mismatch** | pytransitions models FSMs. Your system is a state machine on paper but a workflow engine in practice -- the transitions carry substantial logic (reset counters, invalidate downstream, route to earliest fault). Forcing this into pytransitions' callback model means fighting the abstraction. |
| **Confidence** | HIGH -- read the transition table, read the pytransitions API. The complexity is in the edges, not the nodes. |

### Why NOT python-statemachine (3.0.0)

Same core argument. python-statemachine 3.0 is more modern (declarative class-based API, SCXML compliance, compound states, history states) but it's solving a different problem -- complex statechart semantics for UI-style state machines. Your needs are simpler in some ways (flat state list, no parallel regions) and harder in others (rewind-to-arbitrary-node, counter-driven promotion, sub-pipeline routing). The library would be load-bearing infrastructure that doesn't carry any of the actual load.

**Confidence:** HIGH

### Why NOT workflow orchestration frameworks (Prefect, Temporal, Airflow)

These are distributed workflow orchestration platforms. They solve scheduling, retries at the infrastructure level, observability, and distributed execution. Your v0.1 is single-threaded, in-memory, and the entire point is validating your custom transition logic. Temporal's retry semantics are its own -- they'd fight yours. Prefect and Airflow are DAG runners, not state machines. Wrong tool entirely.

**Confidence:** HIGH

### Why roll your own

1. **The transition table IS the spec.** Your 27-node table with its failure edges, rewind targets, counter rules, and gauntlet semantics is already a complete state machine specification. Translating it into a library's API is pure overhead -- you'd write the same logic either way, just wrapped in someone else's abstractions.

2. **The hard parts are custom.** Rewind-to-write-node-and-replay-forward, 4th-conditional-auto-promotes-to-fail, FBR-gate-failure-restarts-from-top, triage-routes-to-earliest-fault -- no library implements these. They're your domain logic.

3. **Debuggability.** When a job takes a wrong transition, you need to step through YOUR code, not a library's callback dispatch chain. With ~500-800 lines of pure Python, every transition is explicit and debuggable.

4. **The constraint says so.** PROJECT.md: "Pure Python -- no external frameworks for the engine itself." This is already decided. The research confirms it's the right call.

**Confidence:** HIGH

---

## Recommended Stack

### Core Engine (zero dependencies)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12 | Runtime | Already in container. Modern, stable, full typing support |
| dataclasses (stdlib) | -- | Job state, node definitions, transition records | Zero-dep, immutable-friendly, clean `__repr__` for logging. No need for Pydantic validation overhead -- state is internal, not user input |
| enum (stdlib) | -- | Node names, outcomes, job status | Type-safe state identifiers. `NodeName.REVIEW_BRD` beats `"ReviewBrd"` for refactoring safety |
| typing (stdlib) | -- | Type hints throughout | Catch bugs before runtime. The transition table is complex enough that types pay for themselves |

**Confidence:** HIGH -- stdlib, zero risk

### Logging

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| structlog | 25.5.0 | Structured logging | JSON-native structured output. Every transition logs `{"job_id": 42, "node": "ReviewBrd", "outcome": "conditional", "conditional_count": 2, "retry_count": 1}`. Post-hoc analysis (by agents or humans) needs structured data, not string parsing. stdlib logging can't do this without painful formatting gymnastics. |

structlog is the one external dependency the engine should have. The PROJECT.md requirement says "no external frameworks for the engine itself" -- structlog is a logging library, not a framework, and structured logs are explicitly called out as a requirement ("structured enough for post-hoc agent analysis").

**Confidence:** HIGH -- structlog 25.5.0 released Oct 2025, mature, widely adopted

### Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pytest | 8.x | Test runner | Industry standard, zero debate |
| pytest-cov | 6.x | Coverage reporting | Know which transition paths are exercised |

**Confidence:** HIGH

### Development Quality

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ruff | 0.9.x | Linting + formatting | Replaces flake8, black, isort in one tool. Fast. Opinionated. |
| mypy | 1.14.x | Static type checking | The transition table has enough branching that type errors in node routing would be painful to debug at runtime |

**Confidence:** MEDIUM -- versions are approximate, but both tools are stable and backward-compatible

---

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| **pytransitions** | Abstraction mismatch. Gives you state declarations (easy part), adds nothing for rewind/retry/gauntlet logic (hard part). See detailed analysis above. |
| **python-statemachine** | Same argument. More modern API but solving UI-statechart problems, not workflow-with-custom-rewind problems. |
| **Prefect / Temporal / Airflow** | Distributed workflow orchestrators. Wrong abstraction level. Would fight your custom retry semantics. |
| **Pydantic** | Overkill for internal state. No untrusted input to validate. dataclasses are lighter and sufficient. Pydantic adds ~200ms import time for zero benefit here. |
| **SQLAlchemy / any ORM** | v0.1 is in-memory. When Postgres comes later, raw psycopg2/3 or asyncpg with explicit SQL is more appropriate for a task queue than an ORM. |
| **celery / dramatiq** | Task queues for distributed work. v0.1 is single-threaded. Future versions dispatch to Claude CLI, not Python workers. |
| **attrs** | Marginally more powerful than dataclasses but adds a dependency for no practical benefit in this codebase. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| State machine | Roll own | pytransitions 0.9.3 | Callback model doesn't help with rewind/retry complexity |
| State machine | Roll own | python-statemachine 3.0.0 | Statechart features (compound states, SCXML) irrelevant; custom semantics still need custom code |
| State representation | dataclasses | Pydantic BaseModel | No external input validation needed; import overhead; dependency for no benefit |
| State representation | dataclasses | TypedDict | Less ergonomic, no default values, no methods, no `__post_init__` |
| Logging | structlog | stdlib logging | Structured JSON output requires painful custom formatters; structlog does it natively |
| Logging | structlog | loguru | Good library but structlog's processor pipeline is better for the "every log entry is a structured event" pattern |
| Type checking | mypy | pyright | Either works; mypy is more widely used and has better ecosystem support |
| Linting | ruff | flake8 + black + isort | ruff replaces all three, 10-100x faster |

---

## Installation

```bash
# Core (only runtime dependency)
pip install structlog==25.5.0

# Dev dependencies
pip install pytest pytest-cov ruff mypy
```

Or with a `pyproject.toml` (recommended):

```toml
[project]
name = "workflow-engine"
requires-python = ">=3.12"
dependencies = [
    "structlog>=25.5.0,<26",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=6.0",
    "ruff>=0.9",
    "mypy>=1.14",
]
```

---

## Architecture Implications

The "roll your own" decision means the engine design is load-bearing. Key structural choices:

1. **Transition table as data, not code.** Define the 27+ nodes and their edges in a declarative data structure (dict or list of dataclasses). The engine interprets the table. Don't scatter transition logic across 27 methods.

2. **Outcome enum drives everything.** `Outcome.APPROVE`, `Outcome.CONDITIONAL`, `Outcome.FAIL`, `Outcome.SUCCESS`, `Outcome.FAILURE`. The engine's core loop is: execute node -> get outcome -> look up transition -> apply counters -> move to next state.

3. **Counter state lives on the job, not the node.** Each job carries its own `retry_counts: dict[NodeName, int]`, `conditional_counts: dict[NodeName, int]`, `fbr_restart_count: int`, `triage_count: int`. Nodes are stateless. Jobs are stateful.

4. **Rewind = set current_node + clear downstream state.** No need for stack-based undo. Just point the job at the rewind target and let it walk forward through the happy path again.

---

## Sources

- [pytransitions/transitions on GitHub](https://github.com/pytransitions/transitions) -- v0.9.3, MIT, released Jul 2025
- [python-statemachine on PyPI](https://pypi.org/project/python-statemachine/) -- v3.0.0, released Feb 2026
- [python-statemachine docs](https://python-statemachine.readthedocs.io/) -- v3.0.0, SCXML-compliant statecharts
- [structlog on PyPI](https://pypi.org/project/structlog/) -- v25.5.0, released Oct 2025
- [structlog documentation](https://www.structlog.org/) -- v25.5.0
- [transitions on PyPI](https://pypi.org/project/transitions/) -- v0.9.3 version confirmation
