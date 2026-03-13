---
phase: 02-review-branching-and-counter-mechanics
plan: 01
subsystem: state-machine
tags: [python, transition-table, state-machine, review-branching, stub-nodes]

# Dependency graph
requires:
  - phase: 01-foundation-and-happy-path-engine
    provides: TRANSITION_TABLE, HAPPY_PATH, NODE_TYPES, StubWorkNode, StubReviewNode, create_node_registry

provides:
  - REVIEW_ROUTING dict mapping 6 review nodes to (response_node, rewind_target) tuples
  - TRANSITION_TABLE expanded with 18 review branching edges (6 CONDITIONAL + 6 FAIL + 6 response SUCCESS)
  - NODE_TYPES extended with all 7 response nodes as NodeType.WORK
  - TriageProofmarkFailures placeholder transition (SUCCESS -> ExecuteProofmark)
  - 7 response node stubs registered as StubWorkNode in create_node_registry
  - _RESPONSE_NODE_DESCRIPTIONS dict in nodes.py
  - TestReviewRouting class (12 tests) in test_transitions.py
  - 6 new response node tests in test_nodes.py

affects:
  - 02-02 (engine counter mechanics, needs REVIEW_ROUTING and response nodes for branching logic)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Transition table is pure declarative data: (node, outcome) -> next_node. No counter logic in table."
    - "Response nodes are NodeType.WORK -- they return SUCCESS/FAILURE, never APPROVE/CONDITIONAL/FAIL."
    - "REVIEW_ROUTING dict as single source of truth for review-node -> response/rewind mapping."
    - "Loop over REVIEW_ROUTING to add all 18 branching edges atomically."

key-files:
  created: []
  modified:
    - src/workflow_engine/transitions.py
    - src/workflow_engine/nodes.py
    - tests/test_transitions.py
    - tests/test_nodes.py

key-decisions:
  - "REVIEW_ROUTING typed as dict[str, tuple[str, str]] (not dict of dicts) -- flat tuples are sufficient and easier to unpack."
  - "Response nodes NOT added to HAPPY_PATH -- they are off the happy path and only appear in TRANSITION_TABLE and node registry."
  - "TriageProofmarkFailures gets a placeholder SUCCESS -> ExecuteProofmark edge now (Phase 3 will own full triage routing)."
  - "NODE_TYPES extended for response nodes via a post-construction loop, keeping the main dict comprehension clean."

patterns-established:
  - "TDD RED->GREEN: tests written and confirmed failing before implementation in every task."
  - "Per-task atomic commits: each task's tests + implementation committed together."

requirements-completed: [RB-01, RB-02, RB-03, RB-05]

# Metrics
duration: 2min
completed: 2026-03-13
---

# Phase 2 Plan 01: Review Branching Data Layer Summary

**REVIEW_ROUTING dict and expanded TRANSITION_TABLE with 18 branching edges, plus 7 response node stubs registered as StubWorkNode**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-13T20:03:59Z
- **Completed:** 2026-03-13T20:05:54Z
- **Tasks:** 2 of 2
- **Files modified:** 4

## Accomplishments

- Added `REVIEW_ROUTING` dict with exact (response_node, rewind_target) tuples for all 6 review nodes
- Expanded `TRANSITION_TABLE` with 18 new edges: CONDITIONAL->response, FAIL->rewind, response SUCCESS->reviewer
- Extended `NODE_TYPES` to include all 7 response nodes as NodeType.WORK
- Added `_RESPONSE_NODE_DESCRIPTIONS` and extended `create_node_registry()` to return 34 nodes (27 + 7)
- Added 18 new tests across test_transitions.py and test_nodes.py, all green; no regressions in existing 32 tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Add REVIEW_ROUTING and expand TRANSITION_TABLE with branching edges** - `e1c1073` (feat)
2. **Task 2: Add 7 response node stubs and register them** - `a5f598c` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks - tests written first (RED), then implementation (GREEN), single commit per task._

## Files Created/Modified

- `src/workflow_engine/transitions.py` - Added REVIEW_ROUTING, _RESPONSE_NODES, expanded TRANSITION_TABLE with 18 branching edges + TriageProofmarkFailures placeholder
- `src/workflow_engine/nodes.py` - Added _RESPONSE_NODE_DESCRIPTIONS, extended create_node_registry() to include 7 response StubWorkNodes
- `tests/test_transitions.py` - Added TestReviewRouting class with 12 tests covering all new routing behaviors
- `tests/test_nodes.py` - Added 6 new tests: response node existence, type, descriptions, deterministic mode, RNG mode, registry size

## Decisions Made

- `REVIEW_ROUTING` uses `dict[str, tuple[str, str]]` (flat tuples, not dicts) -- clean to unpack, matches research example
- Response nodes stay out of `HAPPY_PATH` -- they're off the happy path and must NOT be added there (research Anti-Pattern)
- `TriageProofmarkFailures` gets a `SUCCESS -> ExecuteProofmark` placeholder now to satisfy RB-05 stub requirement; full triage routing is Phase 3
- `NODE_TYPES` extended for response nodes via a separate loop after the main dict comprehension, keeping it readable

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- pytest not installed on the Python 3.12 system interpreter -- resolved with `pip3 install -e ".[dev]" --break-system-packages` (project was already configured with dev dependencies in pyproject.toml).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Data layer complete: TRANSITION_TABLE has all routing data Plan 02 needs for counter logic and rewind implementation
- REVIEW_ROUTING is exported from transitions.py for use by engine.py in Plan 02
- Response nodes are registered and ready for engine execution
- No blockers

---
*Phase: 02-review-branching-and-counter-mechanics*
*Completed: 2026-03-13*
