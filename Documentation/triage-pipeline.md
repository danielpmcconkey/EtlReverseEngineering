# Triage Pipeline

Source: `src/workflow_engine/transitions.py` (`AUTONOMOUS_NODES`), `src/workflow_engine/step_handler.py`

## Entry Condition

Triage is entered when `ExecuteProofmark` returns `FAILURE`. The transition
table routes `(ExecuteProofmark, FAILURE)` to `Triage`.

## Architecture (Session 24 Redesign)

Triage is a **single autonomous node**. From the engine's perspective, it's a
dead end — the engine fires it and walks away. The triage orchestrator manages
everything internally via sub-agents.

### Why Autonomous?

The old triage pipeline (T1-T7) was a deterministic 7-node diagnostic chain
that could only route to predetermined rewind targets. It couldn't handle
open-ended problems — e.g., when the OG code was non-deterministic and the
correct fix was to exclude columns from Proofmark comparison. The new design
gives the triage orchestrator holistic authority to diagnose, fix, and reset
the job however it sees fit.

### How It Works

The engine executes the `Triage` node. The step handler:
1. Calls the node's `execute()` method (which invokes the triage orchestrator agent).
2. Logs `autonomous_node_complete`.
3. Completes the task.
4. Does **NOT** save job state (the orchestrator's sub-agents already manipulated the DB directly).
5. Does **NOT** look up a transition or enqueue a next node.

The orchestrator runs three sequential phases via background sub-agents:

| Phase | Blueprint | Role |
|-------|-----------|------|
| Diagnose | `triage-rca.md` | Root cause analysis — open-ended investigation |
| Fix | `triage-fix.md` | Determine and implement remediation |
| Reset | `triage-reset.md` | Manipulate DB state to requeue or dead-letter |

### Phase 1: Diagnose (RCA)

The RCA agent investigates why Proofmark produced FAIL results. It has
holistic authority — no checklists, no mandatory structure. It concludes
either "root cause understood" or "root cause not understood."

Writes: `{job_dir}/artifacts/triage/rca-summary.md` (for orchestrator),
`{job_dir}/artifacts/triage/rca-detail.md` (for Fix agent).

### Phase 2: Fix

The Fix agent reads the RCA detail, determines whether a fix is possible,
and implements it if so. It trusts the RCA's diagnosis but has full latitude
on the remediation approach. It can modify proofmark config, job conf, SQL,
external modules, BRD, BDD, or FSD.

Writes: `{job_dir}/artifacts/triage/fix-summary.md` (for orchestrator),
`{job_dir}/artifacts/triage/fix-detail.md` (for Reset agent).

### Phase 3: Reset

The Reset agent reads the fix detail and either:
- **Requeues** the job: updates `re_job_state` (status=RUNNING, new retry
  count, rewind target), cleans up stale process artifacts, inserts a new
  task into `re_task_queue`.
- **Dead-letters** the job: sets status=DEAD_LETTER in `re_job_state`.

The engine picks up the requeued task on its next poll cycle. It doesn't know
triage put it there.

### Retry Budget

The orchestrator owns the retry counter. Each triage pass costs one main
retry (shared with the rest of the pipeline, cap of 5). If retries are
exhausted, the orchestrator skips diagnosis and goes straight to DEAD_LETTER.

### Triage Report

After all phases complete, the orchestrator writes a triage report at
`{job_dir}/artifacts/triage/triage-report.md`. This is the permanent record
of what happened — especially important for dead-lettered jobs as a handoff
document for human review.

## Legacy Fields

`JobState` still contains `triage_results`, `triage_rewind_target`, and
`Outcome.TRIAGE_ROUTE` from the old pipeline. These are in the DB schema and
are left in place to avoid migration. The Reset agent clears them on every
triage pass. They are not used by any current engine code.

## Old Pipeline (Removed in Session 24)

The old 7-node pipeline (T1-T7) was removed:
- T1 `Triage_ProfileData` — data profiler
- T2 `Triage_AnalyzeOgFlow` — OG flow analyst
- T3-T6 `Triage_Check{Brd,Fsd,Code,Proofmark}` — diagnostic checkers
- T7 `Triage_Route` — deterministic fault router

Along with their node classes (`DiagnosticStubNode`, `TriageRouterNode`),
blueprints, and the step handler's `TRIAGE_ROUTE` handling code. Old
blueprints are in git history if needed.
