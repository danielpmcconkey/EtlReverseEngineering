# EtlReverseEngineering

Deterministic orchestrator CLI for reverse engineering 105 ETL jobs from [MockEtlFramework](https://github.com/danielpmcconkey/MockEtlFramework) using AI agents.

## The Goal

Build a C# CLI application that orchestrates the AI-driven reverse engineering of 105 ETL jobs. The orchestrator itself contains **zero LLM logic** — it's a deterministic loop that manages a pool of workers, dispatches tasks to Claude via the CLI, and advances each job through a defined workflow based on outcomes.

## Why This Exists

POC5 used an LLM-based orchestrator (GSD executor) that suffered from context rot. As conversations grew, the orchestrator lost its constraints and began fabricating results — copying OG output to fake RE output, writing plausible summaries for work it didn't do. The core lesson: **the orchestrator must be dumb.** All intelligence lives in the agents, which get a fresh context on every invocation.

## Architecture

### The Orchestrator (C#, no LLM)

A deterministic processing loop that:

1. Polls a Postgres task queue for unclaimed work
2. Claims a task (thread-safe)
3. Dispatches it to the appropriate Claude agent via `claude -p`
4. Parses the structured response
5. Writes results and enqueues the next step(s) per the workflow definition
6. Manages a pool of ~12 concurrent workers across all jobs

The orchestrator doesn't make decisions. It follows a workflow definition — a state machine that maps (current_state, outcome) → next_state. The workflow knows things like "if this is the 5th triage attempt for this job, mark it failed and move on."

### 105 Independent Pipelines

Each job gets its own full lifecycle pipeline. No cross-job contamination. One job's failure doesn't cascade to others.

### Agent Invocation

Each agent is invoked as a fresh Claude CLI subprocess:

```bash
claude -p "<task prompt>" \
  --system-prompt "$(cat blueprints/<skill>.md)" \
  --dangerously-skip-permissions \
  --model sonnet \
  --max-budget-usd 0.50 \
  --output-format json \
  --allowedTools "Bash Read Grep"
```

Agents claim a task, do their work, return a structured result, and die. No state carried between invocations.

### Polyglot Reality

The orchestrator is C#. The agents produce **Python** artifacts targeting [MockEtlFrameworkPython](https://github.com/danielpmcconkey/MockEtlFrameworkPython). Python was chosen for the target framework because it supports dynamic class loading — eliminating the compile-rebuild cycle that created a human-in-the-middle bottleneck in POC5.

### Task Queue (Postgres)

A new task queue table in the `control` schema (existing database, connection details in the orchestrator config). The queue supports:

- Thread-safe claiming (SELECT ... FOR UPDATE SKIP LOCKED or equivalent)
- Per-job isolation
- State tracking (workflow position for each job)
- Attempt counting (for circuit breaker logic)

## Skills, Not Agents

The POC6 taxonomy (see below) has a lot of leaf nodes that are really "call Claude with a different prompt." Rather than treating each as a separate agent type, we define **discrete skills as C# functions**. A skill encapsulates:

- The prompt template
- The allowed tools
- The expected output schema
- The model tier (sonnet vs opus)
- The budget cap

The orchestrator calls the right skill function based on the task type. The skill function builds the CLI invocation and parses the result.

## Workflow Definition

Each job progresses through a waterfall: **Plan → Define → Design → Build → Validate**. Within each stage are discrete steps with review/response cycles.

The workflow should be represented as a state machine — not a giant if/else chain. Key properties:

- Each state has defined transitions based on outcome (pass/fail/error)
- Circuit breakers are guard conditions on transitions (e.g., max 4 triage attempts)
- The orchestrator looks up the transition, doesn't compute it
- The database tracks each job's current state and attempt counts

## Per-Job Waterfall Pipeline

The full taxonomy of steps each job goes through:

```
RE Job Pipeline
├── Plan
│   ├── Locate OG source files
│   ├── Inventory outputs (DataframeWriter, External modules)
│   ├── Inventory data sources
│   └── Note dependencies
├── Define
│   ├── Write BRD (data flow, transformation rules, output schemas, anti-patterns)
│   ├── Review BRD (verify evidence, approve/reject)
│   └── Re-review BRD (triggered by final build review)
├── Design
│   ├── Write BDD test architecture (acceptance criteria, scenarios, fixtures, edge cases)
│   ├── Review BDD
│   ├── Write FSD (data flow, sourcing, transformations, module sequence, traceability)
│   ├── Review FSD
│   ├── Re-review BDD (triggered by final build review)
│   └── Re-review FSD (triggered by final build review)
├── Build
│   ├── Build job artifacts (conf files, external modules)
│   ├── Review job artifacts
│   ├── Build proofmark config (match rules from BRD schemas)
│   ├── Review proofmark config
│   ├── Build unit tests (from BDD architecture)
│   ├── Review unit tests
│   ├── Execute unit tests (run, triage failures)
│   ├── Publish (register in control.jobs)
│   └── Final build review (re-execute all reviewers, verify publication)
└── Validate
    ├── Execute job runs (queue effective dates, monitor, triage)
    ├── Execute proofmark (compare OG vs RE output)
    ├── Triage proofmark failures (RCA, fix, re-queue)
    └── Final sign-off (confirm all dates pass, summarize results)
```

The full detailed taxonomy with all sub-steps is maintained at: https://github.com/danielpmcconkey/AtcStrategy (private, POC6/BDsNotes/agent-taxonomy.md)

## Design Decisions Already Made

- **BDD before FSD** — tests drive the spec, not the other way around
- **All agents cite evidence** — BRD#, BDD scenario#, code references. No unsupported claims.
- **Review Response agents are separate from Write agents** — atomicity matters
- **Publish and Locate OG might not need LLM agents** — could be deterministic functions
- **Circuit breakers are workflow concerns** — the state machine enforces retry limits, not the agents

## Open Questions

These are intentionally left open for the design/planning phase:

- Blueprint format — what goes in each skill's system prompt?
- Exact queue schema design
- Failure handling details — max retries per stage?
- Cost model — budget per skill? Per job total?
- Per-job directory isolation strategy
- How do Validate-stage tasks interact with external systems (running jobs, running proofmark) without wasting worker slots on blocking waits?
- Which jobs to tackle first — easiest (Append mode) or hardest?

## Related Repos

- [MockEtlFramework](https://github.com/danielpmcconkey/MockEtlFramework) — The original C# ETL engine and job configs
- [MockEtlFrameworkPython](https://github.com/danielpmcconkey/MockEtlFrameworkPython) — Python rebuild of the ETL engine (target for RE'd jobs)
- [proofmark](https://github.com/danielpmcconkey/proofmark) — Comparison engine for OG vs RE output verification
- [AtcStrategy](https://github.com/danielpmcconkey/AtcStrategy) — (private) Design notes, taxonomy, architecture docs
