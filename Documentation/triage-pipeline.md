# Triage Pipeline

Source: `src/workflow_engine/transitions.py` (`TRIAGE_NODES`), `src/workflow_engine/nodes.py` (`DiagnosticStubNode`, `TriageRouterNode`), `src/workflow_engine/step_handler.py`

## Entry Condition

The triage pipeline is entered when `ExecuteProofmark` returns `FAILURE`. The transition table routes `(ExecuteProofmark, FAILURE)` to `Triage_ProfileData`.

On entry to `Triage_ProfileData`, `job.triage_results` is cleared.

## The 7 Steps

| Step | Node | Role | What It Does |
|---|---|---|---|
| T1 | Triage_ProfileData | Context | Profiles the failed row data |
| T2 | Triage_AnalyzeOgFlow | Context | Analyzes the original data flow |
| T3 | Triage_CheckBrd | Diagnostic | Checks BRD against data flow findings |
| T4 | Triage_CheckFsd | Diagnostic | Checks FSD against data flow findings |
| T5 | Triage_CheckCode | Diagnostic | Checks code artifacts against data flow findings |
| T6 | Triage_CheckProofmark | Diagnostic | Checks proofmark config against data profile |
| T7 | Triage_Route | Router | Reads results, picks rewind target |

All 7 nodes are WORK type. T1-T6 advance on SUCCESS. T7 returns `TRIAGE_ROUTE`, which has no transition table entry -- the engine handles it directly.

## Diagnostic Nodes (T3-T6)

Each diagnostic node stores a verdict in `job.triage_results[node_name]`:
- `"clean"` -- no fault found
- `"fault"` -- fault detected

In stub mode, the verdict is deterministic (`"clean"`) without RNG, or random with RNG.

## Triage Routing (T7)

`TriageRouterNode` reads `job.triage_results` and picks the **earliest fault** by priority order:

| Priority | Check Node | Rewind Target |
|---|---|---|
| 1 (highest) | Triage_CheckBrd | WriteBrd |
| 2 | Triage_CheckFsd | WriteFsd |
| 3 | Triage_CheckCode | BuildJobArtifacts |
| 4 (lowest) | Triage_CheckProofmark | BuildProofmarkConfig |

If no fault is found, `triage_rewind_target` is set to `"DEAD_LETTER"`.

## Engine Handling of TRIAGE_ROUTE

In `StepHandler.__call__`, when `outcome == TRIAGE_ROUTE`:

1. `main_retry_count` is incremented.
2. `last_rejection_reason` is set to `"Triage routed to {target}"`.
3. If `triage_rewind_target == "DEAD_LETTER"` or `main_retry_count >= max_main_retries`, the job goes to DEAD_LETTER.
4. Otherwise, downstream conditional counters are reset and the job rewinds to the target node.

The job then re-walks the happy path from the rewind target, eventually reaching ExecuteProofmark again. If proofmark fails again, triage runs again, burning another main retry.
