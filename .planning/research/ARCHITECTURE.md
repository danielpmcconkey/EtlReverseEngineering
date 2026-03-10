# Architecture Patterns

**Domain:** Deterministic ETL reverse-engineering orchestrator with concurrent workers
**Researched:** 2026-03-10

## Recommended Architecture

Five-layer architecture where each layer has a single owner and communicates through well-defined interfaces. No layer skips another.

```
 CLI Entry Point
      |
 Orchestrator Loop (main thread)
      |
 Worker Pool (6 threads)
      |
 +----+----+----+----+
 |         |         |
Task    State      Agent
Queue  Machine   Dispatcher
 |                   |
Postgres         claude -p
(control           (subprocess)
 schema)
```

### Component Boundaries

| Component | Responsibility | Communicates With | Thread Safety |
|-----------|---------------|-------------------|---------------|
| **CLI Entry Point** | Parse args, configure, start orchestrator, handle shutdown | Orchestrator | Single-threaded |
| **Orchestrator** | Lifecycle management, spawn workers, monitor health, signal shutdown | Worker Pool, Task Queue (read-only stats) | Owns the main thread |
| **Worker Pool** | Fixed pool of 6 long-lived threads, each running an identical work loop | Task Queue, State Machine, Agent Dispatcher | Each worker is independent; no shared mutable state between workers |
| **Task Queue (Postgres)** | Durable task storage, atomic claiming, result recording | Workers via Npgsql | Thread-safe via `SELECT ... FOR UPDATE SKIP LOCKED` |
| **State Machine Engine** | Defines legal transitions, computes next task given (state, outcome) | Worker (called in-process), Task Queue (enqueues next task) | Stateless/pure -- no mutable state, safe to call from any thread |
| **Skill Registry** | Maps task types to prompt templates, allowed tools, output schemas, model tiers, budget caps | Agent Dispatcher (lookup only) | Read-only after initialization -- inherently thread-safe |
| **Agent Dispatcher** | Builds `claude -p` command, spawns subprocess, captures stdout/stderr, parses structured JSON response | Worker (called per-task), filesystem (prompt assembly) | Each invocation is isolated -- no shared state |
| **Circuit Breaker** | Tracks retry counts per job per stage, enforces max limits, quarantines stuck jobs | State Machine (guard condition on transitions) | Per-job counters stored in Postgres, not in-memory |

### Why This Decomposition

The core insight from PROJECT.md: **the orchestrator must be dumb**. That means:

- The state machine is a lookup table, not a decision engine.
- Workers are identical drones running the same loop -- no specialization.
- All intelligence lives in agents, which are ephemeral subprocesses with zero retained state.
- Postgres is the single source of truth. If the process crashes, restart it and workers resume from where they left off.

## Data Flow

### Happy Path (single task lifecycle)

```
1. Worker thread calls TaskQueue.ClaimNext()
   -> BEGIN; SELECT ... FROM tasks WHERE status='pending'
      ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1;
   -> UPDATE status='in_progress', claimed_by=worker_id, claimed_at=now();
   -> COMMIT; return task

2. Worker passes task to StateMachine.GetSkill(task.job_id, task.state)
   -> Returns: skill_name (e.g., "write_brd")

3. Worker passes skill_name to SkillRegistry.Get(skill_name)
   -> Returns: SkillDefinition { prompt_template, allowed_tools[],
      output_schema, model_tier, budget_cap, timeout }

4. Worker passes (task, skill_definition) to AgentDispatcher.Execute()
   -> Assembles prompt from template + task context
   -> Spawns: claude -p "prompt" --model tier --max-tokens budget
   -> Captures stdout, parses JSON against output_schema
   -> Returns: AgentResult { success, structured_output, raw_output }

5. Worker passes (task, agent_result) to StateMachine.Advance()
   -> Looks up (current_state, outcome) in transition table
   -> Circuit breaker check: retry_count < max for this stage?
   -> If next state exists: enqueue new task(s) for job
   -> If terminal: mark job complete/failed
   -> UPDATE task status='completed', result=agent_result

6. Worker loops back to step 1
```

### Failure Path

```
Agent returns error or unparseable output:
  -> StateMachine.Advance(task, Outcome.Failure)
  -> Circuit breaker increments retry count for (job_id, stage)
  -> If under limit: re-enqueue same task type as 'pending'
  -> If at limit: mark job as 'quarantined', log for human review

Worker crashes mid-task:
  -> Task remains 'in_progress' in Postgres
  -> Orchestrator runs periodic stale-task sweep (configurable timeout)
  -> Resets stale 'in_progress' tasks to 'pending'
  -> Worker that picks it up sees it fresh

Process restart:
  -> Workers start claiming from Postgres -- all state is durable
  -> No in-memory state to lose
```

### Re-Review Cascade Flow

```
Final Build Review agent returns findings:
  -> Each finding has: artifact (BRD/BDD/FSD), severity (cosmetic/substantive)

Cosmetic finding:
  -> Enqueue fix-up task for that artifact
  -> Fix-up task is a targeted edit, not a full rewrite

Substantive finding:
  -> Rewind: enqueue Write task for that artifact
  -> Cascade: all downstream tasks for this job that depend on
     the rewritten artifact get cancelled and will be re-enqueued
     when the Write completes
  -> Circuit breaker tracks rewind count per artifact per job
```

## Component Details

### Task Queue Schema (Postgres)

```sql
CREATE TYPE task_status AS ENUM (
    'pending', 'in_progress', 'completed', 'failed', 'quarantined'
);

CREATE TABLE control.tasks (
    id              BIGSERIAL PRIMARY KEY,
    job_id          INT NOT NULL,           -- which of the 105 ETL jobs
    task_type       TEXT NOT NULL,           -- e.g., 'write_brd', 'review_bdd'
    stage           TEXT NOT NULL,           -- pipeline stage: plan/define/design/build/validate
    status          task_status NOT NULL DEFAULT 'pending',
    priority        INT NOT NULL DEFAULT 0, -- reserved for future use, FIFO for now
    payload         JSONB,                  -- input context for the agent
    result          JSONB,                  -- structured output from agent
    claimed_by      TEXT,                   -- worker thread identifier
    claimed_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    retry_count     INT NOT NULL DEFAULT 0,
    max_retries     INT NOT NULL DEFAULT 3,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_claimable
    ON control.tasks (created_at)
    WHERE status = 'pending';

CREATE TABLE control.circuit_breakers (
    job_id          INT NOT NULL,
    stage           TEXT NOT NULL,
    failure_count   INT NOT NULL DEFAULT 0,
    max_failures    INT NOT NULL DEFAULT 5,
    quarantined_at  TIMESTAMPTZ,
    PRIMARY KEY (job_id, stage)
);

CREATE TABLE control.job_state (
    job_id          INT PRIMARY KEY,
    current_stage   TEXT NOT NULL DEFAULT 'plan',
    status          TEXT NOT NULL DEFAULT 'active',  -- active/completed/quarantined
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    metadata        JSONB                            -- job-specific context
);
```

**Confidence: HIGH** -- This schema follows well-established Postgres job queue patterns. The `SELECT ... FOR UPDATE SKIP LOCKED` claim pattern is battle-tested in production systems like Solid Queue, Graphile Worker, and River.

### State Machine (Transition Table)

Don't use a library like Stateless here. The workflow is a static lookup table, not a runtime-configurable state machine. A dictionary is simpler, more testable, and more debuggable than a framework.

```csharp
// Transition: (CurrentTaskType, Outcome) -> NextTaskType[]
// This is the entire workflow definition. No hidden logic.
private static readonly Dictionary<(string taskType, string outcome), string[]> Transitions = new()
{
    // Plan stage
    { ("locate_sources", "success"),        new[] { "write_plan" } },
    { ("write_plan", "success"),            new[] { "review_plan" } },
    { ("review_plan", "approved"),          new[] { "write_brd" } },
    { ("review_plan", "revise"),            new[] { "revise_plan" } },
    { ("revise_plan", "success"),           new[] { "review_plan" } },

    // Define stage
    { ("write_brd", "success"),             new[] { "review_brd" } },
    { ("review_brd", "approved"),           new[] { "write_bdd" } },
    { ("review_brd", "cosmetic"),           new[] { "fixup_brd" } },
    { ("review_brd", "substantive"),        new[] { "write_brd" } },
    { ("fixup_brd", "success"),             new[] { "write_bdd" } },

    // Design stage
    { ("write_bdd", "success"),             new[] { "review_bdd" } },
    { ("review_bdd", "approved"),           new[] { "write_fsd" } },
    // ... pattern continues through Build and Validate

    // Build stage - final review can cascade
    { ("final_build_review", "approved"),   new[] { "publish" } },
    { ("final_build_review", "cascade"),    new[] { /* dynamically determined */ } },

    // Validate stage
    { ("execute_proofmark", "pass"),        new[] { "final_signoff" } },
    { ("execute_proofmark", "fail"),        new[] { "triage_failures" } },
    { ("final_signoff", "success"),         Array.Empty<string>() },  // terminal
};
```

**Confidence: HIGH** -- A lookup table is the right abstraction for a fixed workflow. Stateless adds ceremony without value here. The transition table can be loaded from config/DB later if needed, but start with code.

### Worker Pool

```
Design: 6 long-lived threads, not Task.Run/async
Why: Each worker blocks on a subprocess (claude -p) for seconds to minutes.
     Thread pool starvation is the risk with async + blocking subprocess calls.
     Dedicated threads make the concurrency model obvious and debuggable.

Pattern:
  - Orchestrator creates 6 Thread instances, each running WorkerLoop()
  - WorkerLoop: while (!cancellationToken.IsCancellationRequested)
      1. ClaimTask() -- may return null if queue empty
      2. If null: Thread.Sleep(pollInterval) and continue
      3. ExecuteTask(task)
      4. AdvanceStateMachine(task, result)
  - CancellationTokenSource for graceful shutdown
  - Each worker gets its own NpgsqlConnection (not shared)
```

**Confidence: HIGH** -- Dedicated threads are the correct choice when the work is blocking subprocess I/O. The .NET thread pool is designed for short-lived async work, not for 6 slots that each block for minutes at a time.

### Agent Dispatcher

```
Design: Thin wrapper around Process.Start()

Input:  SkillDefinition + task payload
Output: Parsed JSON (AgentResult) or error

Steps:
  1. Load prompt template from SkillDefinition
  2. Interpolate task-specific context from payload
  3. Build ProcessStartInfo:
     - FileName: "claude"
     - Arguments: -p "{assembled_prompt}" --output-format json [--model tier]
     - RedirectStandardOutput: true
     - RedirectStandardError: true
     - UseShellExecute: false
  4. Start process, read stdout/stderr with timeout
  5. Parse stdout as JSON against expected schema
  6. Return AgentResult { Success, Output, RawStdout, Stderr, ExitCode, Duration }

Timeout handling:
  - Process.WaitForExit(timeout_ms)
  - If timeout: Process.Kill(), return failure result
  - Timeout per skill from SkillDefinition.Timeout

No retry logic here -- that's the state machine's job.
```

**Confidence: HIGH** -- `claude -p` with `--output-format json` is the documented way to get structured output from Claude CLI. The dispatcher should be dumb -- just spawn, capture, parse.

### Skill Registry

```
Design: In-memory dictionary loaded at startup from config/code

Each SkillDefinition contains:
  - Name: "write_brd"
  - PromptTemplate: path to .md template file
  - AllowedTools: ["Read", "Grep", "Glob"]  -- what the agent can use
  - OutputSchema: JSON schema for expected response structure
  - ModelTier: "opus" | "sonnet" | "haiku"  -- matches task complexity
  - BudgetCap: max tokens
  - Timeout: TimeSpan
  - Stage: which pipeline stage this belongs to

Loaded once, immutable after startup. Thread-safe by construction.
```

**Confidence: MEDIUM** -- The concept is solid. The exact `claude -p` flags for tool restriction and model selection need verification against current Claude CLI docs. The schema validation approach (validate after parse vs. instruct in prompt) is a design decision to make during implementation.

## Patterns to Follow

### Pattern 1: Claim-Execute-Advance (Worker Loop)

**What:** Each worker runs a tight loop: claim a task from Postgres, execute it, advance the state machine. No batching, no prefetching.

**When:** Always. This is the core pattern.

**Why:** Single-task-per-iteration means a crash loses at most one task (which gets reclaimed via stale sweep). Simplicity over throughput -- you're bottlenecked on Claude API latency, not on claim overhead.

```csharp
private void WorkerLoop(CancellationToken ct)
{
    while (!ct.IsCancellationRequested)
    {
        var task = _taskQueue.ClaimNext(_workerId);
        if (task == null)
        {
            Thread.Sleep(_pollInterval);
            continue;
        }

        try
        {
            var skill = _skillRegistry.Get(task.TaskType);
            var result = _agentDispatcher.Execute(task, skill);
            _stateMachine.Advance(task, result);
        }
        catch (Exception ex)
        {
            _taskQueue.MarkFailed(task.Id, ex.Message);
            _logger.Error(ex, "Worker {WorkerId} failed task {TaskId}", _workerId, task.Id);
        }
    }
}
```

### Pattern 2: Postgres as the Only Source of Truth

**What:** All state lives in Postgres. Workers carry no state between iterations. The process can be killed and restarted at any time.

**When:** Always. This is the resilience guarantee.

**Why:** The POC5 lesson -- context rot happens when state accumulates in-memory. By forcing everything through Postgres, you get: crash recovery for free, ability to inspect state with SQL, ability to manually intervene (mark tasks, re-queue, quarantine).

### Pattern 3: Subprocess Isolation for Agents

**What:** Every agent invocation is a fresh `claude -p` subprocess. No persistent sessions, no conversation history, no shared context.

**When:** Every single agent call.

**Why:** This is the anti-context-rot design. Fresh context per invocation means the agent can never accumulate stale beliefs. The prompt template + task payload is the complete context. If the agent needs history (e.g., review feedback), it's serialized into the payload explicitly.

### Pattern 4: Immutable Skill Definitions

**What:** Skills are defined once at startup and never mutated. Each skill specifies everything an agent needs: prompt template, tools, model, budget, timeout.

**When:** Configuration time only.

**Why:** Eliminates a class of concurrency bugs (no locking needed) and makes the system reproducible -- same skill definition always produces the same agent invocation shape.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Async/Await for Worker Threads

**What:** Using `Task.Run` or `async` worker loops that call blocking subprocess operations.

**Why bad:** `Process.WaitForExit()` blocks the thread. Wrapping blocking calls in async creates thread pool starvation risk. With 6 workers each blocking for minutes, you'll exhaust the default thread pool and starve other async work (like health checks or logging).

**Instead:** Use dedicated `Thread` instances. They're explicitly allocated and don't compete with the thread pool.

### Anti-Pattern 2: In-Memory Queue with Postgres Backup

**What:** Loading tasks into a ConcurrentQueue and syncing to Postgres.

**Why bad:** Two sources of truth. Crash loses in-memory state. Sync logic is a bug farm.

**Instead:** Postgres IS the queue. `SELECT FOR UPDATE SKIP LOCKED` is fast enough -- you're not doing thousands of claims per second, you're doing 6.

### Anti-Pattern 3: Smart Workers

**What:** Workers that contain branching logic, special-case handling, or task-type-specific code.

**Why bad:** Violates the "dumb orchestrator" principle. Logic in workers rots the same way LLM context does -- just slower.

**Instead:** Workers are identical. All task-type-specific logic lives in the SkillDefinition (prompt, schema, tools) and the transition table (what happens next).

### Anti-Pattern 4: Stateless Library for the State Machine

**What:** Using the `dotnet-state-machine/stateless` NuGet package for workflow transitions.

**Why bad:** Stateless is designed for runtime-configurable state machines with entry/exit actions, hierarchical states, and parameterized triggers. This workflow is a static lookup table. Stateless adds: a dependency, ceremony for configuration, indirection that makes debugging harder, and async concerns you don't need.

**Instead:** A `Dictionary<(string, string), string[]>` is the right abstraction. It's testable (assert transitions), inspectable (dump the table), and obvious (no framework magic).

## Suggested Build Order

Dependencies flow downward. Build from the bottom up.

```
Phase 1: Foundation (no agent integration)
  1. Postgres schema + migrations
  2. TaskQueue class (claim, complete, fail, stale sweep)
  3. Unit tests for TaskQueue with concurrent claim simulation

Phase 2: State Machine (still no agents)
  4. Transition table definition
  5. StateMachine.Advance() -- given task + outcome, enqueue next
  6. Circuit breaker logic
  7. Integration tests: seed tasks, advance through pipeline, verify state

Phase 3: Worker Infrastructure
  8. Worker loop (claim-execute-advance)
  9. Worker pool + orchestrator lifecycle
  10. Graceful shutdown (CancellationToken)
  11. Stale task recovery

Phase 4: Agent Integration
  12. Skill registry + skill definitions (start with 1-2 skills)
  13. Agent dispatcher (Process.Start wrapper)
  14. JSON response parsing + schema validation
  15. End-to-end test: 1 job through 1 stage

Phase 5: Full Pipeline
  16. All skill definitions for all task types
  17. Re-review cascade logic
  18. Full pipeline test: 1 job through all stages
  19. Multi-job concurrency test

Phase 6: Production Run
  20. Seed all 105 jobs
  21. Monitoring/logging for the actual run
  22. Proofmark integration for validation stage
```

**Rationale:** Phases 1-3 can be built and tested without any Claude CLI dependency. This means you can validate the entire orchestration layer with deterministic tests before introducing the expensive, non-deterministic agent calls. Phase 4 is the integration boundary where mocking gives way to real agents.

## Scalability Considerations

| Concern | At 6 workers (current) | At 12 workers | At 50+ workers |
|---------|----------------------|---------------|----------------|
| Postgres connections | 6 + 1 orchestrator = trivial | Still trivial | Connection pooling via PgBouncer |
| `SKIP LOCKED` contention | Zero -- 6 concurrent claims on a table with 100s of rows | Still zero | Index on `(status, created_at)` keeps it fast |
| Claude API rate limits | Likely bottleneck before workers saturate | Almost certainly rate-limited | Would need token bucket / rate limiter in dispatcher |
| Memory | ~6 subprocess stdout buffers | ~12 buffers | Need to stream large outputs |
| Disk I/O | Prompt templates read per task (cached by OS) | Same | Same |

For 105 jobs with 6 workers, none of these are concerns. The system is bottlenecked on Claude API response latency, not on orchestrator throughput.

## Sources

- [PostgreSQL FOR UPDATE SKIP LOCKED pattern](https://www.dbpro.app/blog/postgresql-skip-locked) -- MEDIUM confidence (blog, but pattern matches official docs)
- [PostgreSQL Explicit Locking docs](https://www.postgresql.org/docs/current/explicit-locking.html) -- HIGH confidence (official)
- [Postgres job queue schema design](https://medium.com/@huimin.hacker/task-queue-design-with-postgres-b57146d741dc) -- MEDIUM confidence (community pattern, multiple sources agree)
- [Building a robust Postgres job queue](https://www.danieleteti.it/post/building-a-simple-yet-robust-job-queue-system-using-postgresql/) -- MEDIUM confidence
- [Stateless library for C# state machines](https://github.com/dotnet-state-machine/stateless) -- HIGH confidence (official repo, evaluated and rejected)
- [C# Process.Start for subprocess management](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.start) -- HIGH confidence (Microsoft docs)
- [Circuit breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker) -- HIGH confidence (Microsoft architecture docs)
- [Npgsql connection pooling](https://www.npgsql.org/doc/basic-usage.html) -- HIGH confidence (official docs)
- [River: Go + Postgres job queue](https://brandur.org/river) -- MEDIUM confidence (architectural influence, different language but same patterns)
