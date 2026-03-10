# Domain Pitfalls

**Domain:** Deterministic ETL orchestration CLI with concurrent workers, Postgres task queue, state machine workflow, Claude CLI subprocess management
**Researched:** 2026-03-10

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Claude CLI Output Is Not Reliably JSON

**What goes wrong:** You invoke `claude -p` expecting structured JSON back. Instead you get: natural language preamble before the JSON, Unicode characters (U+2028, U+2029) that break parsers, stderr warnings mixed into stdout, or truncated output on long responses. Reported failure rates as high as 25% in some CLI wrapper projects.

**Why it happens:** The CLI is a wrapper around a model that *wants* to talk. Even with structured output prompts, edge cases leak through. Stderr from the CLI process itself can intermix with stdout. Special characters in code snippets or file paths corrupt the JSON boundary.

**Consequences:** Worker thread gets an unparseable response, marks task as failed, burns a retry. At scale across 105 jobs with multiple steps each, even a 5% parse failure rate means hundreds of wasted invocations and token spend.

**Prevention:**
- Use `--output-format json` flag and parse from the `structured_output` key, not raw stdout
- Redirect stderr to a separate stream (Process.StartInfo.RedirectStandardError = true) and capture independently
- Wrap all JSON parsing in a resilient parser that strips non-JSON preamble/postamble before deserializing
- Define a "parse failure" as a distinct outcome in the state machine (not the same as "task failed") with its own retry path that costs nothing extra
- Consider a validation layer: deserialize to a typed C# model, reject if required fields are missing, before advancing state

**Detection:** Monitor parse failure rate per skill type. If a particular skill consistently fails parsing, the prompt or output schema needs revision, not more retries.

**Phase relevance:** Must be addressed in the first phase when building the agent invocation layer. Getting this wrong poisons everything downstream.

---

### Pitfall 2: Zombie and Orphan Claude CLI Processes

**What goes wrong:** A Claude CLI subprocess hangs (model timeout, network issue, API rate limit) and never exits. The worker thread waits forever, or worse, the orchestrator crashes/restarts and orphans the subprocess. Over time, zombie `claude` processes accumulate, eating memory and potentially holding API connections.

**Why it happens:** `Process.WaitForExit()` without a timeout blocks indefinitely. On Linux (.NET on Docker), child processes that exit without being reaped become zombies. If the orchestrator crashes mid-invocation, there's no parent to reap the children.

**Consequences:** Worker thread is permanently stuck (capacity reduced from 6 to 5, then 4...). Zombie processes fill the process table. Orphaned Claude processes may continue generating tokens and burning budget with no one listening.

**Prevention:**
- **Always** use `Process.WaitForExit(timeoutMs)` with a generous but finite timeout (e.g., 10 minutes per task, tunable per skill type)
- On timeout: `process.Kill(entireProcessTree: true)` then `process.WaitForExit()` to reap
- Track all spawned PIDs in a `ConcurrentDictionary<int, ProcessInfo>` so the orchestrator can kill orphans on startup/shutdown
- Implement a startup sweep: on orchestrator boot, check for stale `claude` processes and kill them
- Use `CancellationToken` threading through `WaitForExitAsync` for graceful shutdown coordination
- Important .NET quirk: when redirecting stdout asynchronously, call the parameterless `WaitForExit()` *after* the timeout version returns true, to ensure async output handlers complete

**Detection:** Periodic health check that counts running `claude` processes and compares to active worker count. Alert if mismatch.

**Phase relevance:** Core infrastructure, same phase as agent invocation. Non-negotiable.

---

### Pitfall 3: Holding Database Locks During Agent Invocations

**What goes wrong:** Worker claims a task with `SELECT ... FOR UPDATE SKIP LOCKED`, then invokes Claude CLI (which takes 30-120+ seconds), and only commits the transaction after processing the response. The row lock is held the entire time. With 6 workers, that's 6 long-held row locks and 6 connections pinned to open transactions.

**Why it happens:** Naive "claim-process-complete" in a single transaction feels safe. And it is, from a correctness standpoint. But it's a resource disaster.

**Consequences:** Connection pool exhaustion (6 workers = 6 long-held connections, leaving none for status queries or monitoring). Postgres `idle in transaction` connections hold resources. If a worker crashes mid-transaction, the lock is held until Postgres detects the dead connection (could be minutes with default `tcp_keepalives_idle`).

**Prevention:**
- **Three-phase pattern:** (1) Short transaction: claim task, set status to `claimed`, set `claimed_by` and `claimed_at`, COMMIT. (2) Do the work (agent invocation) outside any transaction. (3) Short transaction: update task with results, advance state, COMMIT.
- Add a `visibility_timeout` column: if a task has been `claimed` for longer than N minutes without completion, it's eligible for reclaim by another worker (the original worker crashed)
- Set `statement_timeout` and `idle_in_transaction_session_timeout` in Postgres as safety nets
- Connection pool size = workers + margin (e.g., 10 for 6 workers), not matched 1:1

**Detection:** Monitor `pg_stat_activity` for `idle in transaction` connections. Alert if any transaction is open longer than your expected max agent invocation time.

**Phase relevance:** Database/queue design phase. Must be right from day one -- changing the claim pattern later means rewriting the worker loop.

---

### Pitfall 4: Non-Idempotent Task Execution Causes Duplicate Artifacts

**What goes wrong:** A task runs, produces artifacts (writes a BRD file, creates a Python module), but the orchestrator crashes before recording completion. On restart, the visibility timeout expires, another worker picks up the "uncompleted" task and runs it again. Now you have duplicate or conflicting artifacts.

**Why it happens:** At-least-once delivery is inherent in any system where "do work" and "record completion" aren't atomic. And they can't be atomic when the work involves writing files to disk and invoking external processes.

**Consequences:** Duplicate files, corrupted state, or worse -- a half-written artifact from run 1 gets overwritten by run 2, but run 1's metadata is what the state machine uses to advance. Subtle corruption that may not surface until validation.

**Prevention:**
- Make every task idempotent by design: writing a BRD should overwrite, not append. Use deterministic file paths based on job ID and artifact type
- Record a `task_execution_id` (GUID) with each invocation. On completion, check that the execution ID matches before recording results (if it doesn't, a reclaim happened and this result should be discarded)
- Use the database as the source of truth for "what was produced," not the filesystem. Task completion should record artifact paths and checksums
- For file writes: write to a temp path, then atomic rename on success

**Detection:** Log every task execution with its execution ID. If you see two execution IDs for the same task, investigate immediately.

**Phase relevance:** Task execution and artifact management phases. The idempotency contract must be defined early even if enforcement comes later.

---

### Pitfall 5: State Machine Rewind Cascade Creates Infinite Loops

**What goes wrong:** The re-review cascade logic (final build review can trigger re-reviews of BRD/BDD/FSD, substantive failures rewind to Write step) creates a cycle where: Agent writes BRD -> reviewer says substantive fail -> rewind to write BRD -> agent writes slightly different BRD -> reviewer says substantive fail -> repeat forever.

**Why it happens:** LLM agents aren't deterministic. A reviewer agent might consistently reject output that a writer agent consistently produces. Two agents can have irreconcilable "opinions" about what's correct, especially on subjective quality judgments.

**Consequences:** A single job gets stuck in an infinite rewind loop, consuming worker capacity and token budget indefinitely. With circuit breakers, it eventually stops -- but if the circuit breaker threshold is too generous (e.g., 5 retries * 3 artifact types * 2 review stages = 30 attempts), that's a lot of waste before it trips.

**Prevention:**
- Circuit breakers must be per-stage, per-job, AND per-artifact. "BRD for Job 42 has been rewritten 3 times" is the meaningful metric, not "Job 42 has had 3 failures"
- Escalation, not repetition: after N rewrites of the same artifact, escalate to a different strategy (different prompt, different model tier, or flag for human review) rather than running the same skill again
- Pass previous review feedback into rewrite prompts so the agent knows what to fix (without this, it will produce the same output)
- Log the full review -> rewrite -> re-review chain for post-mortem analysis
- Consider a "diff threshold": if the rewrite is <10% different from the previous version, the agent isn't capable of addressing the feedback -- circuit break immediately

**Detection:** Dashboard showing rewrite counts per artifact per job. Any artifact hitting rewrite count >= 2 deserves attention.

**Phase relevance:** State machine design phase, but the circuit breaker tuning will need adjustment during the Build phase once you see real agent behavior.

## Moderate Pitfalls

### Pitfall 6: Worker Thread Exception Kills the Pool

**What goes wrong:** An unhandled exception in a worker thread (null reference from unexpected agent output, network timeout, file system error) crashes that thread. If using raw `Thread` objects, the thread is gone forever. The orchestrator continues with 5 workers, then 4, then 3, silently degrading.

**Prevention:**
- Wrap the entire worker loop in try/catch. The catch should log, mark the current task as failed with the exception details, and **continue the loop** -- never let a single task failure kill the worker
- Use a supervisor pattern: a manager thread monitors worker health and respawns dead workers
- Prefer `Task.Run` with a proper exception handling pipeline over raw `Thread` objects. Unobserved task exceptions in .NET are swallowed by default but logged -- make sure you're observing them
- `SemaphoreSlim(6)` controlling concurrency is more resilient than managing 6 explicit threads

**Detection:** Log worker heartbeats. If a worker hasn't logged activity in longer than the max expected task duration, it's dead or stuck.

**Phase relevance:** Worker pool infrastructure phase.

---

### Pitfall 7: SKIP LOCKED Without Proper Indexing Becomes a Full Table Scan

**What goes wrong:** `SELECT ... WHERE status = 'pending' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1` looks elegant. Without a composite index on `(status, created_at)`, Postgres does a sequential scan of the entire tasks table, checking locks row by row. As completed tasks accumulate (thousands over 105 jobs * ~15 steps each), this gets progressively slower.

**Prevention:**
- Create a composite index: `CREATE INDEX idx_tasks_queue ON tasks (status, created_at) WHERE status = 'pending'` (partial index -- even better)
- Periodically archive or partition completed tasks so the working set stays small
- Be aware: `FOR UPDATE SKIP LOCKED` forces heap access even with an index (can't do index-only scans), so keep the table slim
- Consider a separate `task_queue` table for pending work vs. a `task_history` table for completed work

**Detection:** `EXPLAIN ANALYZE` on your claim query periodically. Watch for sequential scans or increasing query times.

**Phase relevance:** Database schema design phase.

---

### Pitfall 8: Conflating "Task Failed" with "Agent Produced Wrong Output"

**What goes wrong:** The orchestrator treats every non-success as the same failure type. But there's a massive difference between: (a) Claude CLI crashed / timed out / returned garbage (infrastructure failure), (b) Agent returned valid JSON but the content is wrong (quality failure), and (c) Agent returned valid JSON indicating it can't do the work (capability failure). Retry strategy should differ for each.

**Prevention:**
- Define distinct outcome types in the state machine: `Success`, `ParseFailure`, `InfraFailure`, `QualityFailure`, `CapabilityFailure`, `Timeout`
- Infrastructure failures get automatic retry (probably transient)
- Quality failures go through the review/rewrite cycle
- Capability failures get escalated (different model, human review, skip with flag)
- Parse failures get automatic retry with possibly adjusted prompt formatting
- Different circuit breaker thresholds for each failure type

**Detection:** Failure type distribution per skill. If one skill type has 80% capability failures, the skill design is wrong, not the infrastructure.

**Phase relevance:** State machine design phase, but the failure taxonomy should be defined during architecture.

---

### Pitfall 9: Per-Job Isolation Violations Through Shared File System

**What goes wrong:** The project says "per-job isolation -- no cross-job contamination." But 6 workers writing artifacts concurrently to the same file system can collide. Two jobs might write to the same directory, one job's agent might read another job's in-progress artifact as context, or file path conventions might collide.

**Prevention:**
- Enforce a strict directory convention: `/workspace/artifacts/{job_id}/` with no exceptions
- Agent invocations should include explicit working directory constraints in the prompt
- The orchestrator should create job directories before dispatching any tasks for that job
- Consider using the `--allowedTools` flag in Claude CLI to restrict file system access to the job's directory
- Never pass relative paths to agents -- always absolute paths scoped to the job

**Detection:** Post-task validation: check that all files written by a task are within the expected job directory. Flag any out-of-scope writes.

**Phase relevance:** Agent invocation design and artifact management phases.

---

### Pitfall 10: Token Budget Burn from Unconstrained Agent Context

**What goes wrong:** Skills pass too much context to Claude CLI agents. A "review BRD" skill sends the entire source code of the OG ETL job plus the BRD plus all previous review history. The agent hits the context window limit, or the token cost per invocation balloons. Multiply by 105 jobs and the budget explodes.

**Prevention:**
- Each skill definition should have a `max_input_tokens` estimate. Track actual usage and alert when it exceeds the estimate
- Use the `--max-turns 1` flag (or equivalent) to prevent agent from spawning tool-use loops that burn tokens
- Budget caps per skill type, not just per job. A BRD review should cost roughly the same for every job
- The skill registry should define exactly what context each skill receives -- no "throw everything at it" defaults
- Consider tiered models: use cheaper/faster models for rote tasks (formatting, simple reviews) and expensive models only for complex reasoning

**Detection:** Track token usage per skill invocation. Establish baselines in the first 10 jobs, then alert on deviations > 2x.

**Phase relevance:** Skill registry design phase. The budget constraints need to be baked into the skill definitions.

## Minor Pitfalls

### Pitfall 11: Orchestrator State Desynchronizes from Postgres

**What goes wrong:** The orchestrator caches task state in memory for performance. A crash loses the in-memory state, and on restart, the orchestrator's view of the world doesn't match Postgres. Or worse, the orchestrator advances in-memory state but fails to write it to Postgres.

**Prevention:**
- Postgres is the single source of truth. Period. Workers read state from Postgres before every decision, write state to Postgres after every action. No in-memory state caching for task status
- If you need caching for performance, use it only for immutable data (skill definitions, job metadata), never for mutable state (task status, progress)

**Detection:** Startup reconciliation: on boot, verify all `claimed` tasks are actually being worked on. Any `claimed` task with no active worker gets reset to `pending`.

**Phase relevance:** Worker pool infrastructure.

---

### Pitfall 12: Proofmark Validation Ordering and Timing

**What goes wrong:** Proofmark comparison requires both the OG and RE jobs to have been executed and produced output. If the orchestrator kicks off proofmark validation before the RE job has actually run (or before OG data is available), you get false failures or meaningless comparisons.

**Prevention:**
- Proofmark validation should be the absolute last step, gated by explicit preconditions (RE job executed successfully, OG output available, proofmark config reviewed and approved)
- Model this as a state machine guard condition, not just ordering. The state transition to "validate" should check preconditions, not just assume the previous step handled it

**Detection:** Proofmark failures that are "file not found" or "empty output" rather than actual comparison differences indicate ordering problems.

**Phase relevance:** Validate phase design.

---

### Pitfall 13: Graceful Shutdown Is Harder Than You Think

**What goes wrong:** You hit Ctrl+C or Docker sends SIGTERM. The orchestrator needs to: stop claiming new tasks, wait for in-flight tasks to complete (or time out), kill any stuck agent subprocesses, and update Postgres to release claimed tasks. Getting this wrong means tasks stuck in `claimed` state until visibility timeout expires on next boot.

**Prevention:**
- Handle `Console.CancelKeyPress` and `AppDomain.CurrentDomain.ProcessExit`
- Use a `CancellationTokenSource` that all workers check between iterations
- On shutdown signal: set cancellation token, stop the claim loop, wait for in-flight tasks with a shutdown timeout (e.g., 30 seconds), then force-kill remaining subprocesses
- Mark any incomplete tasks back to `pending` in Postgres during shutdown

**Detection:** After restart, check how many tasks were in `claimed` state. If it's consistently > 0, shutdown isn't clean.

**Phase relevance:** Worker pool infrastructure, but easy to defer and regret later. Build it with the worker loop.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Database schema design | SKIP LOCKED without index (#7), lock holding during work (#3) | Design the three-phase claim pattern and partial index from day one |
| State machine design | Rewind cascade loops (#5), conflated failure types (#8) | Define failure taxonomy and per-artifact circuit breakers before coding |
| Agent invocation layer | JSON parse failures (#1), zombie processes (#2), token burn (#10) | Build robust subprocess wrapper with timeout, stderr separation, resilient parsing |
| Worker pool | Thread death (#6), shutdown (#13), state desync (#11) | Supervisor pattern, CancellationToken throughout, Postgres as sole truth |
| Artifact management | Idempotency (#4), job isolation (#9) | Deterministic paths, atomic writes, execution IDs |
| Skill registry | Token budget (#10), failure types (#8) | Per-skill budget caps, context limits, model tier assignments |
| Validate phase | Proofmark ordering (#12) | Guard conditions on state transitions, explicit precondition checks |

## Sources

- [The Unreasonable Effectiveness of SKIP LOCKED](https://www.inferable.ai/blog/posts/postgres-skip-locked) - Postgres queue patterns
- [Netdata: FOR UPDATE SKIP LOCKED](https://www.netdata.cloud/academy/update-skip-locked/) - Deadlock-free queue workflows
- [Neon: Queue System using SKIP LOCKED](https://neon.com/guides/queue-system) - Queue implementation guide
- [Alex Stoica: FOR UPDATE SKIP LOCKED Performance](https://www.alexstoica.com/blog/postgres-select-for-update-perf) - Index impact on SKIP LOCKED
- [.NET Runtime Issue #29232: WaitForExit hangs](https://github.com/dotnet/runtime/issues/29232) - Process.WaitForExit async stdout bug
- [.NET Runtime Issue #21661: Zombie processes on Linux](https://github.com/dotnet/corefx/issues/19695) - Process.Start zombie process problem
- [Andrew Lock: Stopped waiting doesn't stop the Task](https://andrewlock.net/just-because-you-stopped-waiting-for-it-doesnt-mean-the-task-stopped-running/) - Task cancellation misconceptions
- [Claude Structured Outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) - Official structured output guidance
- [claude-task-master Issue #1223: AI response parsing](https://github.com/eyaltoledano/claude-task-master/issues/1223) - Real-world Claude CLI JSON parsing failures
- [claude-code Issue #25025: JSON output corruption](https://github.com/anthropics/claude-code/issues/25025) - Stderr corrupting JSON output
- [SFEIR: Claude Code Headless Mode Common Mistakes](https://institute.sfeir.com/en/claude-code/claude-code-headless-mode-and-ci-cd/errors/) - CLI headless mode pitfalls
- [Milan Jovanovic: Idempotent Consumer Pattern](https://www.milanjovanovic.tech/blog/the-idempotent-consumer-pattern-in-dotnet-and-why-you-need-it) - .NET idempotency patterns
- [Vlad Mihalcea: Database Job Queue SKIP LOCKED](https://vladmihalcea.com/database-job-queue-skip-locked/) - Queue implementation patterns
- [PostgreSQL Advisory Locks guide](https://appmaster.io/blog/postgresql-advisory-locks-double-processing) - Advisory vs row locks for queues
- [Temporal: Beyond State Machines](https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications) - State machine orchestration complexity
- [Richard Clayton: Use State Machines](https://rclayton.silvrback.com/use-state-machines) - State machine design patterns
- [Or Ben Shmueli: Task and Concurrency in C#](https://medium.com/@orbens/advanced-task-and-concurrency-management-in-c-patterns-pitfalls-and-solutions-129d9536f233) - C# concurrency pitfalls
- [Mark Heath: Constraining Concurrent Threads](https://markheath.net/post/constraining-concurrent-threads-csharp) - SemaphoreSlim patterns
