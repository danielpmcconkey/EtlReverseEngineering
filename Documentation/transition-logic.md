# Transition Logic

Source: `src/workflow_engine/transitions.py`, `src/workflow_engine/step_handler.py`, `src/workflow_engine/models.py`

## Outcomes

Defined in `models.Outcome`:

| Outcome | Meaning |
|---|---|
| SUCCESS | WORK node completed successfully. Advances to next node. |
| FAILURE | WORK node failed. Used by response nodes and ExecuteProofmark. |
| APPROVE | REVIEW node approved. Advances to next node. |
| CONDITIONAL | REVIEW node found issues but they're fixable. Routes to response node. |
| FAIL | REVIEW node rejected. Routes to rewind target. |
| TRIAGE_ROUTE | Emitted only by Triage_Route. Engine handles directly (no transition table entry). |

## Transition Table

Built programmatically in `transitions.py`:

1. **Happy-path edges**: Each node gets one forward edge. WORK nodes on SUCCESS, REVIEW nodes on APPROVE. The last node (FBR_EvidenceAudit) advances to COMPLETE.

2. **Review branching** (from `REVIEW_ROUTING`): For each of the 6 in-flow review nodes:
   - `(reviewer, CONDITIONAL)` -> response node
   - `(reviewer, FAIL)` -> rewind target (the paired WORK node)
   - `(response_node, SUCCESS)` -> back to reviewer
   - `(response_node, FAILURE)` -> rewind target

3. **FBR branching** (from `FBR_ROUTING`): For each of the 6 FBR gates:
   - `(fbr_gate, CONDITIONAL)` -> response node (reuses same response nodes as in-flow review)
   - `(fbr_gate, FAIL)` -> rewind target
   - No `(response_node, SUCCESS)` edges added here -- already exist from step 2.

4. **Triage entry**: `(ExecuteProofmark, FAILURE)` -> Triage_ProfileData

## Counter Mechanics

Two counters in `JobState`, managed by `StepHandler._resolve_outcome()`:

### `conditional_counts[node_name]` (per-node)

- Incremented on CONDITIONAL outcome.
- Reset to 0 on APPROVE outcome.
- When count reaches `max_conditional_per_node` (default 3), the CONDITIONAL is **escalated to FAIL**.

### `main_retry_count` (global)

- Incremented on every FAIL outcome (after conditional escalation if applicable).
- Incremented on every TRIAGE_ROUTE outcome.
- When count reaches `max_main_retries` (default 5), job goes to DEAD_LETTER.

## Rewind Behavior

When a FAIL occurs at a review/FBR node, the transition table routes back to the paired WORK node (the "rewind target"). For example, `ReviewBrd` FAIL rewinds to `WriteBrd`.

On rewind, `_reset_downstream_conditionals()` clears all conditional counters for the rewind target and every node downstream of it in `HAPPY_PATH`. This prevents stale counters from prematurely escalating future review passes.

When `use_agents` is true, rewind also triggers `_cleanup_stale_artifacts()`, which deletes process artifact JSON files for all downstream nodes so agents start fresh.

## DEAD_LETTER

A job enters DEAD_LETTER (terminal failure) when any of these conditions is met:

1. `main_retry_count` reaches `max_main_retries`.
2. A node in `TERMINAL_FAIL_NODES` returns FAIL. Currently only `FBR_EvidenceAudit` -- if traceability is broken, the whole RE attempt is suspect.
3. Triage_Route sets `triage_rewind_target` to "DEAD_LETTER" (no fault found, nothing to rewind to).

DEAD_LETTER jobs are saved and the task is completed. No further enqueuing.

## FBR Intercept

When `fbr_return_pending` is true and a review node (from `REVIEW_ROUTING`) returns APPROVE, the normal next-node is overridden to `FBR_BrdCheck`. This re-enters the FBR gauntlet from the top after a fix-and-re-review cycle. See [fbr-gauntlet.md](fbr-gauntlet.md).

## Terminal Nodes with No Retry

ExecuteUnitTests and ExecuteJobRuns have no FAILURE edges in the transition table. Their agents have a built-in 3-attempt leash. If they emit FAIL, the engine has no transition and will raise `ValueError`. These are expected to succeed or be handled upstream.
