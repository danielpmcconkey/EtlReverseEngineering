# Phase 2: Review Branching and Counter Mechanics - Research

**Researched:** 2026-03-13
**Domain:** State machine branching, counter semantics, rewind/replay mechanics
**Confidence:** HIGH

## Summary

Phase 2 transforms a linear happy-path engine into a branching state machine. The existing Phase 1 code has a clean foundation: `TRANSITION_TABLE` is a `dict[(node, Outcome) -> next_node]`, `JobState` already carries `main_retry_count`, `conditional_counts`, and `last_rejection_reason`, and `EngineConfig` already has `max_main_retries` (N=5) and `max_conditional_per_node` (M=3). The engine loop is a simple while-loop that looks up `(current_node, outcome)` in the table and advances. Currently, non-happy-path outcomes (CONDITIONAL, FAIL, FAILURE) have no transition entries and raise `ValueError`.

The work is entirely about (a) expanding `TRANSITION_TABLE` with Conditional and Fail edges for every review node, (b) adding 7 response nodes (stubs + registry entries), (c) implementing counter increment/reset/auto-promotion logic in the engine loop, and (d) adding DEAD_LETTER terminal handling. No new libraries. No new frameworks. Pure Python state machine logic.

**Primary recommendation:** Extend the transition table with all non-happy-path edges first (data layer), then modify `engine.py` to handle counter semantics and rewind logic (engine layer). The transition table should remain purely declarative -- counter logic belongs in the engine, not the table.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SM-04 | Main retry counter increments on any full Fail at any review node | Engine loop: on FAIL outcome, increment `job.main_retry_count` before resolving rewind target |
| SM-05 | Main retry counter reaching N sends job to DEAD_LETTER | Engine loop: check `main_retry_count >= config.max_main_retries` after increment, set `status = "DEAD_LETTER"` |
| SM-06 | Per-node conditional counter increments on Conditional outcome | Engine loop: increment `job.conditional_counts[node_name]` on CONDITIONAL |
| SM-07 | Per-node conditional counter reaching M auto-promotes to Fail | Engine loop: after incrementing conditional counter, if `>= M`, treat as FAIL (increment main retry, resolve rewind target) |
| SM-08 | Per-node conditional counter resets to 0 on success at that node | Engine loop: on APPROVE at a review node, set `conditional_counts[node_name] = 0` |
| SM-09 | Per-node conditional counters reset to 0 for all nodes downstream of a rewind target | On rewind: clear conditional counts for all nodes at or after the rewind target in `HAPPY_PATH` order |
| RB-01 | Approve routes to next node in happy path | Already works via existing `(node, APPROVE) -> next` entries in `TRANSITION_TABLE` |
| RB-02 | Conditional routes to response node -> same reviewer | New `TRANSITION_TABLE` entries: `(ReviewX, CONDITIONAL) -> ResponseX` and `(ResponseX, SUCCESS) -> ReviewX` |
| RB-03 | Fail rewinds to original write node and replays forward | New `TRANSITION_TABLE` entries: `(ReviewX, FAIL) -> WriteX` (the original write node, not response node) |
| RB-04 | Writer/response nodes receive only the most recent rejection reason | Engine loop: on CONDITIONAL or FAIL, set `job.last_rejection_reason` to a stub reason string; response/write nodes can read it |
| RB-05 | 7 response nodes exist | Add to `nodes.py`: WriteBrdResponse, WriteBddResponse, WriteFsdResponse, BuildJobArtifactsResponse, BuildProofmarkResponse, BuildUnitTestsResponse, TriageProofmarkFailures (all as StubWorkNode) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| structlog | >=25.0 | Structured JSON logging | Already in use from Phase 1, only runtime dep |
| pytest | latest | Test framework | Already configured in pyproject.toml |

### Supporting
No new libraries needed. This phase is pure Python logic changes to existing modules.

## Architecture Patterns

### Current Project Structure (from Phase 1)
```
src/workflow_engine/
  __init__.py
  __main__.py
  engine.py         # Engine class with run_job() / run()
  logging.py        # configure_logging()
  models.py         # Outcome, NodeType, JobState, EngineConfig
  nodes.py          # Node ABC, StubWorkNode, StubReviewNode, create_node_registry()
  transitions.py    # HAPPY_PATH, NODE_TYPES, TRANSITION_TABLE, validate_transition_table()
tests/
  conftest.py
  test_engine.py
  test_logging.py
  test_models.py
  test_nodes.py
  test_transitions.py
```

No new files needed. All changes extend existing modules.

### Pattern 1: Declarative Transition Table Extension

**What:** Add CONDITIONAL and FAIL edges to `TRANSITION_TABLE` for all 6 review nodes, plus SUCCESS edges for all 7 response nodes.

**When to use:** All review branching routing.

**Key data from design docs:**

```python
# Review node -> response node (Conditional path)
# Review node -> write node (Fail/rewind path)
# Response node -> review node (return after conditional fix)

REVIEW_ROUTING: dict[str, dict] = {
    "ReviewBrd": {
        "response_node": "WriteBrdResponse",
        "rewind_target": "WriteBrd",
    },
    "ReviewBdd": {
        "response_node": "WriteBddResponse",
        "rewind_target": "WriteBddTestArch",
    },
    "ReviewFsd": {
        "response_node": "WriteFsdResponse",
        "rewind_target": "WriteFsd",
    },
    "ReviewJobArtifacts": {
        "response_node": "BuildJobArtifactsResponse",
        "rewind_target": "BuildJobArtifacts",
    },
    "ReviewProofmarkConfig": {
        "response_node": "BuildProofmarkResponse",
        "rewind_target": "BuildProofmarkConfig",
    },
    "ReviewUnitTests": {
        "response_node": "BuildUnitTestsResponse",
        "rewind_target": "BuildUnitTests",
    },
}
```

These become transition table entries:
- `(ReviewX, CONDITIONAL) -> ResponseX`
- `(ReviewX, FAIL) -> RewindTarget`
- `(ResponseX, SUCCESS) -> ReviewX`

### Pattern 2: Counter Logic in Engine Loop (NOT in Transition Table)

**What:** The transition table stays pure routing data. Counter increment, reset, auto-promotion, and DEAD_LETTER checks live in `engine.py`'s `run_job()` method.

**Why:** Mixing counter logic into the table would make it procedural. The table answers "where do I go?", the engine answers "should I even go there, or is this job dead?"

**Engine loop pseudocode for Phase 2:**
```python
outcome = node.execute(job)

# --- Counter logic (new in Phase 2) ---
if outcome == Outcome.CONDITIONAL:
    job.conditional_counts[current_node] = job.conditional_counts.get(current_node, 0) + 1
    job.last_rejection_reason = f"Conditional at {current_node}"
    if job.conditional_counts[current_node] >= config.max_conditional_per_node:
        # Auto-promote to Fail
        outcome = Outcome.FAIL
        log.info("conditional_auto_promoted", node=current_node, ...)

if outcome == Outcome.FAIL:
    job.main_retry_count += 1
    job.last_rejection_reason = f"Fail at {current_node}"
    if job.main_retry_count >= config.max_main_retries:
        job.status = "DEAD_LETTER"
        log.info("dead_letter", ...)
        break  # or continue to exit while loop

# --- Rewind counter reset (SM-09) ---
if outcome == Outcome.FAIL:
    rewind_target = TRANSITION_TABLE[(current_node, Outcome.FAIL)]
    _reset_downstream_conditionals(job, rewind_target)

if outcome == Outcome.APPROVE:
    # SM-08: reset conditional counter for this node on success
    job.conditional_counts[current_node] = 0

# --- Standard transition lookup ---
next_node = TRANSITION_TABLE[(current_node, outcome)]
```

### Pattern 3: Downstream Counter Reset

**What:** On rewind (FAIL), clear conditional counts for all nodes at or after the rewind target in HAPPY_PATH order.

**Implementation:**
```python
def _reset_downstream_conditionals(job: JobState, rewind_target: str) -> None:
    """Reset conditional counters for rewind_target and all downstream nodes."""
    target_idx = HAPPY_PATH.index(rewind_target)
    for node in HAPPY_PATH[target_idx:]:
        job.conditional_counts.pop(node, None)
```

Note: Response nodes are NOT in HAPPY_PATH, so they don't need clearing. Their conditional counters wouldn't exist anyway since only review nodes accumulate conditional counts.

### Anti-Patterns to Avoid

- **Counter logic in the transition table:** The table should be pure `(node, outcome) -> next_node` data. Counter checks, auto-promotion, and DEAD_LETTER happen BEFORE the table lookup, potentially mutating the outcome.
- **Separate rewind function that replays nodes:** Rewind just sets `current_node` to the rewind target. The existing while loop naturally replays forward from there. No special replay mechanism needed.
- **Response nodes in HAPPY_PATH:** Response nodes are off the happy path. They should NOT be added to the `HAPPY_PATH` list. They exist only in `TRANSITION_TABLE`, `NODE_TYPES`, and the node registry.
- **Errata accumulation:** RB-04 is explicit -- writer gets ONLY the most recent rejection reason. Don't build a list of past rejections.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Replay-forward after rewind | Custom replay function that re-executes nodes | Just set `current_node = rewind_target` and let the existing while loop handle it | The engine loop already handles "execute current, advance, repeat" -- rewind is just a position change |
| Node ordering for counter reset | Custom graph traversal | `HAPPY_PATH.index(target)` then slice | HAPPY_PATH is already the canonical ordering |

## Common Pitfalls

### Pitfall 1: Auto-Promotion Ordering Bug
**What goes wrong:** If you check DEAD_LETTER before auto-promoting CONDITIONAL to FAIL, a job at max conditionals won't increment the main retry counter correctly.
**Why it happens:** The CONDITIONAL->FAIL promotion and FAIL->DEAD_LETTER check are sequential steps with ordering dependencies.
**How to avoid:** Process in this exact order: (1) increment conditional counter, (2) check M and auto-promote to FAIL if needed, (3) increment main retry, (4) check N and DEAD_LETTER if needed.
**Warning signs:** Tests where M conditionals don't result in a main retry increment.

### Pitfall 2: Conditional Counter Key Confusion
**What goes wrong:** Using the response node name as the counter key instead of the review node name.
**Why it happens:** After a CONDITIONAL at ReviewBrd, the job routes to WriteBrdResponse, then back to ReviewBrd. If the counter tracks "WriteBrdResponse" instead of "ReviewBrd", the M limit never triggers.
**How to avoid:** Counter key is always the review node name. The counter increments when the review node returns CONDITIONAL, keyed by that review node's name.
**Warning signs:** Conditional counter never reaching M despite repeated conditionals.

### Pitfall 3: Rewind Counter Reset Scope
**What goes wrong:** Only resetting the counter for the rewind target node, not all downstream nodes.
**Why it happens:** Misreading SM-09 as "reset the target node's counter" instead of "reset counters for all nodes at or downstream of the target."
**How to avoid:** SM-09 explicitly says "all nodes downstream of a rewind target." Use HAPPY_PATH index to identify the boundary.
**Warning signs:** Stale conditional counts surviving a rewind.

### Pitfall 4: FAILURE vs FAIL Confusion
**What goes wrong:** WORK nodes return `Outcome.FAILURE`, REVIEW nodes return `Outcome.FAIL`. These are different enum values with different semantics. FAILURE on a work node currently has no transition (Phase 1 raises ValueError). Phase 2 doesn't change work node failure handling -- that's potentially Phase 3 territory (triage).
**Why it happens:** The Outcome enum has both FAILURE and FAIL which look similar.
**How to avoid:** Be explicit in code comments and tests. FAIL = review rejection (rewind + retry). FAILURE = work node failure (different handling, out of Phase 2 scope except for response nodes).
**Warning signs:** Tests accidentally using FAILURE when they mean FAIL or vice versa.

### Pitfall 5: Response Node Outcome Type
**What goes wrong:** Response nodes are WORK nodes (they write/build), so they return SUCCESS/FAILURE, not APPROVE/CONDITIONAL/FAIL. If you give them REVIEW type, the RNG stub returns wrong outcomes.
**Why it happens:** Response nodes sit between review nodes in the conditional path, so they "feel" like part of the review process.
**How to avoid:** Response nodes are explicitly `NodeType.WORK`. Their SUCCESS routes back to the reviewer.
**Warning signs:** Response nodes returning APPROVE instead of SUCCESS.

## Code Examples

### Transition Table Extension
```python
# In transitions.py -- add after the happy-path table construction

# Review routing metadata: review_node -> (response_node, rewind_target)
REVIEW_ROUTING: dict[str, tuple[str, str]] = {
    "ReviewBrd":             ("WriteBrdResponse",          "WriteBrd"),
    "ReviewBdd":             ("WriteBddResponse",          "WriteBddTestArch"),
    "ReviewFsd":             ("WriteFsdResponse",           "WriteFsd"),
    "ReviewJobArtifacts":    ("BuildJobArtifactsResponse",  "BuildJobArtifacts"),
    "ReviewProofmarkConfig": ("BuildProofmarkResponse",     "BuildProofmarkConfig"),
    "ReviewUnitTests":       ("BuildUnitTestsResponse",     "BuildUnitTests"),
}

# Add Conditional and Fail edges for each review node
for review_node, (response_node, rewind_target) in REVIEW_ROUTING.items():
    TRANSITION_TABLE[(review_node, Outcome.CONDITIONAL)] = response_node
    TRANSITION_TABLE[(review_node, Outcome.FAIL)] = rewind_target
    # Response node SUCCESS routes back to the same reviewer
    TRANSITION_TABLE[(response_node, Outcome.SUCCESS)] = review_node
```

### Response Node Registration
```python
# In nodes.py -- response nodes with descriptions

_RESPONSE_NODE_DESCRIPTIONS: dict[str, str] = {
    "WriteBrdResponse":          "brd-writer: Revises BRD based on reviewer feedback",
    "WriteBddResponse":          "bdd-writer: Revises BDD test architecture based on reviewer feedback",
    "WriteFsdResponse":          "fsd-writer: Revises FSD based on reviewer feedback",
    "BuildJobArtifactsResponse": "builder: Revises job artifacts based on reviewer feedback",
    "BuildProofmarkResponse":    "proofmark-builder: Revises proofmark config based on reviewer feedback",
    "BuildUnitTestsResponse":    "test-writer: Revises unit tests based on reviewer feedback",
    "TriageProofmarkFailures":   "triage: Analyzes proofmark failures and routes to appropriate fix",
}

# In create_node_registry(): add response nodes as StubWorkNode instances
```

### Engine Counter Logic
```python
# In engine.py run_job() -- after node.execute(job)

def _resolve_outcome(self, job: JobState, node_name: str, raw_outcome: Outcome) -> Outcome:
    """Apply counter logic: conditional increment, auto-promotion, main retry increment."""
    outcome = raw_outcome

    if outcome == Outcome.APPROVE:
        # SM-08: reset conditional counter on success at this review node
        job.conditional_counts[node_name] = 0
        return outcome

    if outcome == Outcome.CONDITIONAL:
        # SM-06: increment per-node conditional counter
        count = job.conditional_counts.get(node_name, 0) + 1
        job.conditional_counts[node_name] = count
        job.last_rejection_reason = f"Conditional feedback at {node_name}"

        # SM-07: auto-promote to Fail if M reached
        if count >= self._config.max_conditional_per_node:
            outcome = Outcome.FAIL  # fall through to FAIL handling below

    if outcome == Outcome.FAIL:
        # SM-04: increment main retry counter
        job.main_retry_count += 1
        if raw_outcome != Outcome.FAIL:
            job.last_rejection_reason = f"Auto-promoted to Fail at {node_name} (conditional limit)"
        else:
            job.last_rejection_reason = f"Fail at {node_name}"

        # SM-05: check DEAD_LETTER
        if job.main_retry_count >= self._config.max_main_retries:
            job.status = "DEAD_LETTER"
            return outcome

        # SM-09: reset downstream conditional counters
        rewind_target = TRANSITION_TABLE[(node_name, Outcome.FAIL)]
        self._reset_downstream_conditionals(job, rewind_target)

    return outcome
```

## State of the Art

Not applicable -- this is a custom state machine, not a library ecosystem. No external state-of-the-art concerns.

## Open Questions

1. **FAILURE outcome on response nodes**
   - What we know: Response nodes are WORK nodes and can return FAILURE via RNG. Currently no transition for `(ResponseX, FAILURE)`.
   - What's unclear: Should a response node FAILURE be handled in Phase 2, or is it a work-node failure that falls under Phase 3 triage?
   - Recommendation: For Phase 2, either (a) response nodes with RNG=None always return SUCCESS (deterministic path), or (b) add `(ResponseX, FAILURE) -> rewind_target` entries to handle it. Option (b) is cleaner -- a failed response is essentially a failed write, so rewind to the same target as a FAIL at the review node.

2. **FinalSignOff review node**
   - What we know: FinalSignOff is classified as REVIEW in `_REVIEW_NODES`. It's the last node before COMPLETE.
   - What's unclear: What are FinalSignOff's CONDITIONAL and FAIL targets? The design doc's review routing table doesn't include it. It might only have APPROVE (happy path) for Phase 2, with FAIL/CONDITIONAL deferred.
   - Recommendation: FinalSignOff CONDITIONAL/FAIL handling is likely Phase 3 scope (it's not in Phase 2's requirement IDs). Skip it for Phase 2 -- only APPROVE is needed.

3. **TriageProofmarkFailures as a Phase 2 response node**
   - What we know: RB-05 lists it as one of 7 response nodes. But the triage sub-pipeline (TR-*) is Phase 3 scope.
   - What's unclear: Does Phase 2 need to fully implement TriageProofmarkFailures routing, or just create the stub?
   - Recommendation: Create the stub node in Phase 2 (satisfies RB-05), but don't wire its transition table entries until Phase 3 when the triage pipeline exists. Or wire a simple `(TriageProofmarkFailures, SUCCESS) -> ExecuteProofmark` entry as a placeholder.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (latest, configured in pyproject.toml) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -x -q` |
| Full suite command | `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SM-04 | Main retry increments on FAIL | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_fail_increments_main_retry -x` | No - Wave 0 |
| SM-05 | N fails -> DEAD_LETTER | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_dead_letter_on_max_retries -x` | No - Wave 0 |
| SM-06 | Conditional increments per-node counter | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_conditional_increments_counter -x` | No - Wave 0 |
| SM-07 | M conditionals auto-promotes to Fail | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_conditional_auto_promotes_to_fail -x` | No - Wave 0 |
| SM-08 | Conditional counter resets on approve | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_conditional_resets_on_approve -x` | No - Wave 0 |
| SM-09 | Downstream counters reset on rewind | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_downstream_counters_reset_on_rewind -x` | No - Wave 0 |
| RB-01 | Approve routes to happy path next | unit | `python -m pytest tests/test_transitions.py::TestReviewRouting::test_approve_routes_happy_path -x` | No - Wave 0 |
| RB-02 | Conditional -> response -> reviewer | integration | `python -m pytest tests/test_engine.py::TestReviewBranching::test_conditional_loop -x` | No - Wave 0 |
| RB-03 | Fail rewinds to write node | integration | `python -m pytest tests/test_engine.py::TestReviewBranching::test_fail_rewinds_to_write_node -x` | No - Wave 0 |
| RB-04 | Only most recent rejection reason | unit | `python -m pytest tests/test_engine.py::TestReviewBranching::test_only_latest_rejection_reason -x` | No - Wave 0 |
| RB-05 | 7 response nodes exist | unit | `python -m pytest tests/test_nodes.py::test_response_nodes_exist -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_engine.py::TestCounterMechanics` -- new test class covering SM-04 through SM-09
- [ ] `tests/test_engine.py::TestReviewBranching` -- new test class covering RB-01 through RB-04
- [ ] `tests/test_transitions.py::TestReviewRouting` -- new tests for expanded transition table
- [ ] `tests/test_nodes.py::test_response_nodes_exist` -- verify 7 response nodes in registry

Existing test infrastructure (conftest.py, pytest config) is sufficient. No new framework setup needed.

## Sources

### Primary (HIGH confidence)
- Phase 1 source code: `src/workflow_engine/` -- all 6 modules read and analyzed
- Design doc: `/workspace/AtcStrategy/POC6/BDsNotes/state-machine-transitions.md` -- canonical transition table with all review routing
- `.planning/REQUIREMENTS.md` -- all 11 phase requirements (SM-04..SM-09, RB-01..RB-05)
- `.planning/PROJECT.md` -- constraints, decisions, counter model

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` -- Phase 1 completion status and accumulated decisions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, pure Python changes to existing code
- Architecture: HIGH -- existing code is clean and well-structured, extension points are obvious
- Pitfalls: HIGH -- the counter ordering and key confusion issues are classic state machine bugs, identified directly from requirements analysis

**Research date:** 2026-03-13
**Valid until:** Indefinite -- this is a custom codebase, not an external dependency
