---
phase: 02-review-branching-and-counter-mechanics
plan: 02
subsystem: state-machine
tags: [python, engine, counter-logic, rewind, dead-letter]

# Dependency graph
requires:
  - phase: 02-review-branching-and-counter-mechanics
    plan: 01
    provides: REVIEW_ROUTING, expanded TRANSITION_TABLE with CONDITIONAL/FAIL/response-SUCCESS edges, 7 response node stubs
provides:
  - _resolve_outcome() with counter semantics
  - _reset_downstream_conditionals() for rewind cleanup
  - DEAD_LETTER termination on N exhaustion
  - Auto-promotion from CONDITIONAL to FAIL at M threshold
---

## What Was Built

Implemented the engine's counter logic in `_resolve_outcome()` — the decision layer that sits between raw node outcomes and transition table lookups. Handles:

- **APPROVE**: Resets conditional counter for that review node to 0
- **CONDITIONAL**: Increments per-node conditional counter; auto-promotes to FAIL when M reached
- **FAIL** (including auto-promoted): Increments main retry counter; triggers DEAD_LETTER at N; rewinds to original write node and resets all downstream conditional counters

Critical ordering preserved: APPROVE reset → CONDITIONAL increment → M-check auto-promote → FAIL main increment → N-check DEAD_LETTER → downstream counter reset.

## Key Files

### key-files.created
- (none — modified existing files only)

### key-files.modified
- `src/workflow_engine/engine.py` — Added `_resolve_outcome()`, `_reset_downstream_conditionals()`, restructured `run_job()` loop
- `tests/test_engine.py` — Added `ScriptedNode` helper, `TestCounterMechanics` (6 tests: SM-04–SM-09), `TestReviewBranching` (3 tests: RB-02–RB-04), updated `TestNoStateBleed`

## Test Results

59 passed, 0 failed. 9 new tests added. Zero regressions against Phase 1 and Plan 02-01 tests.

## Deviations

- Updated Phase 1 `test_no_state_bleed_between_jobs` — APPROVE now explicitly resets counters to 0 (creating dict keys) rather than leaving `conditional_counts` empty. Changed assertion from `== {}` to `all(v == 0 for v in ...)`. Semantically equivalent — no actual retries occurred.

## Decisions

- Counter key is always the review node name, never the response node name (per research Pitfall 2)
- `last_rejection_reason` is a formatted string like `"FAIL at ReviewBrd"` — sufficient for Phase 2; Phase 3 can enrich with agent context
- Response node FAILURE handling deferred — Plan 01 didn't add `(ResponseX, FAILURE)` edges, and the plan didn't require them. Will be addressed in Phase 3 if needed.
