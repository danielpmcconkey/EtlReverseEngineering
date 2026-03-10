# Technology Stack

**Project:** ETL Reverse Engineering Orchestrator
**Researched:** 2026-03-10

## Target Framework Decision

**.NET 8.0** (LTS, supported through November 2026).

.NET 10 is the current LTS (released November 2025), but the container already has .NET 8.0.124 installed, .NET 8 is still in active support, and there's zero feature in .NET 10 that this project needs. This is a CLI orchestrator, not a web app -- we don't benefit from the AI integration or MAUI changes. Upgrade to .NET 10 if the project is still alive past mid-2026.

**Confidence:** HIGH -- .NET 8 LTS support timeline is well-documented.

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| .NET 8.0 | 8.0.x | Runtime & SDK | Already installed in container. LTS through Nov 2026. No .NET 10 features needed for a CLI orchestrator. |
| C# 12 | (ships with .NET 8) | Language | Required features: primary constructors, collection expressions. Nothing in C# 13 matters here. |

**Confidence:** HIGH

### Database Access

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Npgsql | 8.0.x | PostgreSQL driver + connection pooling | Direct driver, no ORM overhead. Version 8.x matches .NET 8 target. NpgsqlDataSource provides built-in connection pooling. |

**Not Dapper.** Dapper adds a dependency for syntactic sugar you don't need. This project runs a handful of SQL statements -- claim a task, update state, insert results. Raw Npgsql with `NpgsqlCommand` is fine. The SQL is Postgres-specific anyway (`SELECT ... FOR UPDATE SKIP LOCKED`), so Dapper's abstraction buys nothing. Fewer dependencies = fewer things to debug.

**Not Entity Framework.** This is emphatically not an ORM use case. You're managing a task queue with raw SQL locking primitives. EF would actively fight you.

**Confidence:** HIGH -- Npgsql is the canonical .NET PostgreSQL driver, mature, well-documented.

### State Machine

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Stateless | 5.20.1 | State machine workflow engine | The de facto .NET state machine library. Fluent API for defining (state, trigger) -> next_state transitions. Supports guard conditions (circuit breakers), parameterized triggers, reentrant states. Targets .NET 8/9/10. |

Stateless maps directly to the project's needs:
- States: `PlanPending`, `PlanRunning`, `DefinePending`, etc.
- Triggers: `TaskClaimed`, `TaskCompleted`, `ReviewFailed_Cosmetic`, `ReviewFailed_Substantive`, `CircuitBreakerTripped`
- Guard conditions: max retry counts per stage (circuit breakers)
- `OnEntry`/`OnExit` actions: queue management, logging

**Not a hand-rolled state machine.** Stateless handles the edge cases (reentrant states, async transitions, guard clauses) that you'd inevitably rediscover. 14K+ GitHub stars, actively maintained.

**Confidence:** HIGH -- verified version on NuGet, verified .NET 8 compatibility.

### Concurrency & Worker Management

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| System.Threading.Channels | (built into .NET 8) | Producer-consumer work distribution | Bounded channel with capacity 6 = your 6 worker threads. Built-in backpressure. No external dependency. FIFO semantics match the pure FIFO queue requirement. |
| SemaphoreSlim | (built into .NET 8) | Concurrency limiting | Cap concurrent workers at 6. Pairs with Channels for the dispatch loop. |
| Task.WhenAll / Task.Run | (built into .NET 8) | Worker lifecycle | Spin up 6 long-running tasks that consume from the channel. |

The pattern: a single dispatcher reads from the Postgres queue (`SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`) and writes to a bounded Channel<WorkItem>. Six consumer tasks read from the channel, execute skills, and write results back to Postgres.

**Not System.Threading.ThreadPool directly.** You want explicit control over exactly 6 workers. Channel consumers on `Task.Run` with `TaskCreationOptions.LongRunning` give you that without manually managing threads.

**Not TPL Dataflow.** Overkill. You don't need a dataflow graph. You need a queue and 6 consumers.

**Confidence:** HIGH -- System.Threading.Channels is built-in, well-documented, and the standard pattern for producer-consumer in modern .NET.

### Subprocess Management (Claude CLI)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| CliWrap | 3.10.0 | Invoke `claude -p` subprocess | Wraps Process.Start with a sane API. Handles stdout/stderr pipe deadlocks that raw Process.Start is notorious for. Async-first. Supports cancellation tokens. Fluent API for arguments, working directory, environment variables. |

**Not raw System.Diagnostics.Process.** Process.Start + async stdout + stderr is a minefield of deadlocks and race conditions. Every .NET developer has been bitten by the "read stdout and stderr simultaneously without deadlocking" problem. CliWrap exists specifically to solve this. It's a single dependency with zero transitive deps.

Usage pattern:
```csharp
var result = await Cli.Wrap("claude")
    .WithArguments(["-p", prompt, "--output-format", "json"])
    .WithWorkingDirectory(jobWorkDir)
    .WithValidation(CommandResultValidation.None) // handle exit codes ourselves
    .ExecuteBufferedAsync(cancellationToken);

var response = JsonSerializer.Deserialize<AgentResponse>(result.StandardOutput);
```

**Confidence:** HIGH -- CliWrap 3.10.0 verified on NuGet, 5K+ GitHub stars, actively maintained.

### JSON Parsing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| System.Text.Json | (built into .NET 8) | Parse structured agent responses | Built-in, fast, AOT-compatible. .NET 8 version has all the features needed: source generators, JsonDocument for exploratory parsing, strong deserialization. No reason to pull in Newtonsoft.Json. |

Agent responses will be deserialized into strongly-typed C# records:
```csharp
public record AgentResponse(
    string Status,        // "success" | "failure"
    string? Severity,     // "cosmetic" | "substantive" (for reviews)
    string[] Artifacts,   // file paths produced
    string Summary,       // human-readable summary
    string[] Evidence     // BRD#, BDD scenario#, code refs
);
```

**Not Newtonsoft.Json.** System.Text.Json is the modern default. Newtonsoft is legacy at this point. The only reason to use Newtonsoft is if you need features STJ doesn't have (dynamic, JObject manipulation) -- and you don't.

**Confidence:** HIGH -- System.Text.Json ships with .NET 8.

### Logging

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Serilog | 4.3.1 | Structured logging | Structured events, not string interpolation. Per-job context enrichment (job ID, stage, worker thread). File + console sinks. The standard choice for .NET structured logging. |
| Serilog.Sinks.Console | 6.1.1 | Console output | Colored, structured console output. |
| Serilog.Sinks.File | (latest) | Log files | Rolling file logs with per-day rotation. |

Why not just `Microsoft.Extensions.Logging` directly? You could, but Serilog's enrichment model is better suited for per-job context. Every log entry from a worker should carry `{JobId}`, `{Stage}`, `{WorkerId}` without manually threading them through every call.

**Confidence:** HIGH -- Serilog 4.3.1 verified on NuGet.

### Resilience (Optional -- evaluate during implementation)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Polly | 8.6.x | Retry/circuit breaker for Claude CLI calls | If Claude CLI hangs or rate-limits, Polly provides retry with exponential backoff + circuit breaker. But: the state machine already has circuit breakers (max retries per stage). Polly would be for transient infrastructure failures (network timeouts, process crashes), not business logic retries. |

**Verdict:** Start without Polly. The state machine handles business-logic retries. Add Polly only if you see transient Claude CLI failures in practice. Don't preemptively add complexity.

**Confidence:** MEDIUM -- Polly is well-known, but whether you need it is TBD.

### CLI Argument Parsing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| System.CommandLine | 2.0.0-beta (latest) | CLI argument parsing | Microsoft's official CLI library. Still in beta but stable enough for production use. Handles `--workers 6`, `--dry-run`, `--job-filter`, etc. |

**Alternative: skip it entirely.** This orchestrator has maybe 3 flags. You could parse `args[]` manually and not regret it. System.CommandLine is worth it if you anticipate growing the CLI interface. If the CLI stays simple, just use a switch statement on args.

**Verdict:** Use System.CommandLine. The overhead is minimal and it gives you `--help` for free.

**Confidence:** MEDIUM -- still in beta, but widely used in .NET CLI tools.

## Full Stack Summary

```
Runtime:        .NET 8.0 (LTS)
Language:       C# 12
DB Driver:      Npgsql 8.0.x
State Machine:  Stateless 5.20.1
Concurrency:    System.Threading.Channels + SemaphoreSlim (built-in)
Subprocess:     CliWrap 3.10.0
JSON:           System.Text.Json (built-in)
Logging:        Serilog 4.3.1 + Console/File sinks
CLI Parsing:    System.CommandLine 2.0.0-beta
Resilience:     Polly 8.6.x (deferred -- add if needed)
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| DB Access | Npgsql (raw) | Dapper | Unnecessary abstraction for 5 SQL statements. Adds dependency for zero benefit. |
| DB Access | Npgsql (raw) | EF Core | ORM actively fights raw SQL locking. Wrong tool for a task queue. |
| State Machine | Stateless | Hand-rolled | You'll reinvent guard conditions, reentrant states, and async transitions. |
| State Machine | Stateless | Automatonymous (MassTransit) | Pulls in MassTransit ecosystem. Massive overkill for an in-process state machine. |
| Subprocess | CliWrap | System.Diagnostics.Process | Stdout/stderr deadlock hell. Every .NET dev has the scar tissue. |
| JSON | System.Text.Json | Newtonsoft.Json | Legacy. STJ is faster, built-in, and sufficient. |
| Logging | Serilog | NLog | Both work. Serilog's structured event model is slightly better for enriched per-job logging. |
| Logging | Serilog | Microsoft.Extensions.Logging only | Lacks Serilog's enrichment ergonomics. |
| Concurrency | Channels | TPL Dataflow | Dataflow graph is overkill for a simple producer-consumer pattern. |
| Concurrency | Channels | Hangfire/Quartz | External job schedulers for a project that IS a job scheduler. Circular. |
| Target | .NET 8 | .NET 10 | Not installed in container. No features needed. Upgrade when .NET 8 EOL approaches. |

## Installation

```bash
# Create project
dotnet new console -n EtlOrchestrator --framework net8.0

# Core dependencies
dotnet add package Npgsql --version 8.0.*
dotnet add package Stateless --version 5.20.1
dotnet add package CliWrap --version 3.10.0
dotnet add package Serilog --version 4.3.1
dotnet add package Serilog.Sinks.Console --version 6.1.1
dotnet add package Serilog.Sinks.File
dotnet add package System.CommandLine --prerelease

# Optional (add if transient failures observed)
# dotnet add package Polly.Core --version 8.6.6
```

## Project Structure (Recommended)

```
EtlOrchestrator/
  Program.cs                    # Entry point, DI setup, CLI parsing
  Orchestrator.cs               # Main dispatch loop (producer)
  Workers/
    Worker.cs                   # Channel consumer, skill executor
  StateMachine/
    JobStateMachine.cs          # Stateless configuration
    JobState.cs                 # State enum
    JobTrigger.cs               # Trigger enum
  Skills/
    ISkill.cs                   # Skill interface
    SkillRegistry.cs            # Maps (state, trigger) -> skill
    PlanSkill.cs                # Example skill implementation
  Queue/
    TaskQueue.cs                # Postgres queue operations (claim, complete, fail)
    DbConnection.cs             # NpgsqlDataSource factory
  Agent/
    ClaudeInvoker.cs            # CliWrap wrapper for claude -p
    AgentResponse.cs            # Response DTOs
  Models/
    WorkItem.cs                 # Task queue row model
```

## Sources

- [NuGet: Npgsql 10.0.1](https://www.nuget.org/packages/Npgsql) (latest; 8.0.x for .NET 8 compat)
- [NuGet: Stateless 5.20.1](https://www.nuget.org/packages/stateless/)
- [NuGet: CliWrap 3.10.0](https://www.nuget.org/packages/CliWrap)
- [NuGet: Serilog 4.3.1](https://www.nuget.org/packages/serilog/)
- [NuGet: Serilog.Sinks.Console 6.1.1](https://www.nuget.org/packages/serilog.sinks.console/)
- [NuGet: Polly.Core 8.6.5](https://www.nuget.org/packages/polly.core/)
- [Microsoft: System.Threading.Channels](https://learn.microsoft.com/en-us/dotnet/core/extensions/channels)
- [Microsoft: System.CommandLine](https://learn.microsoft.com/en-us/dotnet/standard/commandline/get-started-tutorial)
- [Microsoft: .NET 10 release](https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-10/overview)
- [GitHub: Stateless](https://github.com/dotnet-state-machine/stateless)
- [Npgsql connection pooling](https://www.npgsql.org/doc/basic-usage.html)
- [Process stdout/stderr deadlock issue](https://github.com/dotnet/runtime/issues/81896)
