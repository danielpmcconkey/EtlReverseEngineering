# Phase 3: FBR Gauntlet, Triage, and Validation Run - Research

**Researched:** 2026-03-13
**Domain:** State machine extension -- FBR gauntlet restart semantics, triage sub-pipeline, N-job validation run
**Confidence:** HIGH

## Summary

Phase 3 is purely additive to the clean Phase 2 foundation. The engine already handles three-outcome review nodes, counter mechanics, rewinds, and DEAD_LETTER. What's missing: (1) FBR gate Conditional/Fail edges with restart-from-top semantics, (2) the `fbr_return_pending` flag that reroutes post-fix review approvals back to FBR_BrdCheck, (3) the triage sub-pipeline (7 nodes: T1-T7) triggered on ExecuteProofmark FAILURE, and (4) a validation run of 100+ jobs with RNG outcomes that exercises all paths.

The two big design challenges are the `fbr_return_pending` flag (FBR-04 -- approvals at review nodes sometimes route to FBR_BrdCheck instead of the happy-path next node) and the T7 triage router (TR-04 -- pure orchestrator logic that reads T3-T6 results and picks the earliest fault). Neither is a library problem; both are engine state management problems.

There is also one deferred-from-Phase-2 loose end: `(ResponseX, FAILURE)` edges have no transition entries. Phase 3 needs to decide whether work node FAILURE inside the FBR fix loop causes a further rewind or DEAD_LETTER. The transition table docs don't specify this case explicitly -- it needs a design decision.

**Primary recommendation:** Split into two plans: Plan 03-01 owns FBR gauntlet (data + engine flag), Plan 03-02 owns triage sub-pipeline + validation run. The gauntlet and triage are independent subsystems; splitting isolates risk.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FBR-01 | 6 serial gates (FBR_BrdCheck -> FBR_UnitTestCheck) execute after Publish | Already in HAPPY_PATH (indices 18-23). Need CONDITIONAL/FAIL edges in TRANSITION_TABLE for all 6 gates |
| FBR-02 | FBR gate Conditional: response node -> review -> approve -> restart gauntlet from FBR_BrdCheck | Requires FBR_ROUTING dict (parallel to REVIEW_ROUTING) + `fbr_return_pending` flag on JobState. Approve at the review node checks the flag and routes to FBR_BrdCheck instead of happy-path next |
| FBR-03 | FBR gate Fail: rewind to original write node, replay forward, naturally arrives back at FBR_BrdCheck | Rewind is identical to existing Phase 2 rewind mechanics. The "naturally arrives" part is just the pipeline structure -- after a full replay from WriteBrd, the job re-executes Publish and lands at FBR_BrdCheck again |
| FBR-04 | Engine tracks fbr_return_pending flag so post-fix review approval routes back to FBR_BrdCheck | New field on JobState. Set to True when FBR Conditional triggers. Cleared when job enters FBR_BrdCheck. Engine checks flag on APPROVE at any in-flow review node |
| TR-01 | ExecuteProofmark failure enters 7-step triage (T1-T7) | Need `(ExecuteProofmark, FAILURE) -> Triage_ProfileData` in TRANSITION_TABLE |
| TR-02 | T1-T2 are context-gathering stubs (data profiling, OG flow analysis) | New StubWorkNode instances: Triage_ProfileData, Triage_AnalyzeOgFlow. Both return SUCCESS deterministically or via RNG. SUCCESS advances to next triage step |
| TR-03 | T3-T6 are diagnostic stubs returning clean/fault via RNG | New nodes: Triage_CheckBrd, Triage_CheckFsd, Triage_CheckCode, Triage_CheckProofmark. Need a TriageDiagnosticNode stub that returns one of {SUCCESS="clean", FAILURE="fault"} and optionally stores result on job state |
| TR-04 | T7 is pure orchestrator logic -- routes to earliest fault found | Triage_Route is NOT a node stub -- it's special engine logic (or a special node subclass) that reads T3-T6 results from job state and routes to the correct rewind target |
| TR-05 | Multiple faults route to the earliest (highest up the pipeline) | T7 priority order: T3 fault -> WriteBrd, T4 fault -> WriteFsd, T5 fault -> BuildJobArtifacts, T6 fault -> BuildProofmarkConfig. Engine checks in priority order and takes first match |
| TR-06 | No faults found -> DEAD_LETTER | If all T3-T6 are clean, T7 routes to DEAD_LETTER. This must increment main_retry_count first (since it's a failure, not a happy-path terminal) |
| TR-07 | Triage routing triggers a rewind (which increments main retry counter) | T7's chosen rewind target goes through the same rewind logic as a FAIL (increments main_retry_count, resets downstream conditionals). T7 is a FAIL variant, not a special bypass |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| structlog | >=25.0 | Structured JSON logging | Already in use; no change |
| pytest | latest | Test framework | Already configured; no change |

### Supporting
No new libraries. Phase 3 is pure Python, same as Phases 1 and 2.

**Installation:** None needed.

## Architecture Patterns

### Current Project Structure (from Phase 2, verified)
```
src/workflow_engine/
  __init__.py
  __main__.py
  engine.py         # Engine class, _resolve_outcome(), _reset_downstream_conditionals()
  logging.py        # configure_logging()
  models.py         # Outcome, NodeType, JobState, EngineConfig
  nodes.py          # Node ABC, StubWorkNode, StubReviewNode, create_node_registry()
  transitions.py    # HAPPY_PATH, NODE_TYPES, TRANSITION_TABLE, REVIEW_ROUTING, validate_transition_table()
tests/
  conftest.py
  test_engine.py    # 59 passing tests through Phase 2
  test_logging.py
  test_models.py
  test_nodes.py
  test_transitions.py
```

**Phase 3 adds no new files.** All changes are extensions to existing modules.

### Pattern 1: FBR Routing Table (parallel to REVIEW_ROUTING)

**What:** A new `FBR_ROUTING` dict in `transitions.py` mapping each FBR gate to its (response_node, rewind_target). The conditional loop for FBR gates is different from in-flow review nodes: after the response node success -> review approval, the job goes to FBR_BrdCheck (not the next happy-path node). FBR gates don't have APPROVE edges in the happy path the normal way -- they DO have APPROVE edges to the next FBR gate, which are already in the HAPPY_PATH transition table. The delta: CONDITIONAL and FAIL edges for each FBR gate.

**FBR_ROUTING data (from state-machine-transitions.md):**
```python
FBR_ROUTING: dict[str, tuple[str, str]] = {
    "FBR_BrdCheck":      ("WriteBrdResponse",          "WriteBrd"),
    "FBR_BddCheck":      ("WriteBddResponse",          "WriteBddTestArch"),
    "FBR_FsdCheck":      ("WriteFsdResponse",          "WriteFsd"),
    "FBR_ArtifactCheck": ("BuildJobArtifactsResponse", "BuildJobArtifacts"),
    "FBR_ProofmarkCheck":("BuildProofmarkResponse",    "BuildProofmarkConfig"),
    "FBR_UnitTestCheck": ("BuildUnitTestsResponse",    "BuildUnitTests"),
}
```

**Transition entries added for FBR gates:**
```python
for fbr_gate, (response_node, rewind_target) in FBR_ROUTING.items():
    TRANSITION_TABLE[(fbr_gate, Outcome.CONDITIONAL)] = response_node
    TRANSITION_TABLE[(fbr_gate, Outcome.FAIL)] = rewind_target
    # response_node SUCCESS -> the in-flow review node for that artifact (not fbr_gate)
    # BUT: the fbr_return_pending flag changes where approval at the review node goes
```

Note: the response nodes (WriteBrdResponse, etc.) are SHARED between in-flow review and FBR gates. `WriteBrdResponse` is already registered. Its `(WriteBrdResponse, SUCCESS) -> ReviewBrd` edge is already in the table from Phase 2. The `fbr_return_pending` flag on JobState is what causes ReviewBrd's APPROVE to route to FBR_BrdCheck instead of WriteBddTestArch.

### Pattern 2: fbr_return_pending Flag on JobState

**What:** A boolean on `JobState` that signals "this job was bounced back from an FBR gate, so the next review approval should restart the gauntlet instead of advancing the happy path."

**When set:** When an FBR gate returns CONDITIONAL -> routed to response node. Before routing to response, set `job.fbr_return_pending = True`.

**When consumed:** When any in-flow review node returns APPROVE and `job.fbr_return_pending` is True. In `_resolve_outcome()` (or in the engine loop's transition lookup), intercept the approval and route to FBR_BrdCheck, then clear the flag.

**When cleared:** When the job enters FBR_BrdCheck (i.e., when FBR_BrdCheck is `job.current_node`). The engine can clear the flag at entry rather than at departure to handle the restart properly.

**Implementation approach (two options):**

Option A -- Engine intercepts APPROVE transition:
```python
# In run_job() after outcome is resolved and we have a next_node from TRANSITION_TABLE:
if outcome == Outcome.APPROVE and job.fbr_return_pending:
    next_node = "FBR_BrdCheck"
    job.fbr_return_pending = False
```
This handles the routing cleanly. The flag only activates on APPROVE at review nodes (not FBR gates, not work nodes).

Option B -- Separate TRANSITION_TABLE entries for FBR-return path:
This would require duplicate entries or conditional logic in the table lookup, which breaks the declarative model. **Avoid option B.**

**Recommendation: Option A.** The flag is engine-level state management, consistent with how conditional counters work -- the table says where to go, the engine decides whether to override it.

### Pattern 3: Triage Sub-Pipeline Nodes

**What:** 7 new nodes (T1-T7) registered in the node registry.

**Node classifications:**
- T1, T2: StubWorkNode -- context gathering, always advance on SUCCESS
- T3-T6: DiagnosticStubNode -- new stub subclass that returns SUCCESS ("clean") or FAILURE ("fault") via RNG AND stores its result on job state for T7 to read
- T7: TriageRouterNode -- special Node subclass that reads T3-T6 results from job state and returns a routing outcome

**DiagnosticStubNode stores result on job state:**
```python
class DiagnosticStubNode(Node):
    """Triage diagnostic stub. Records clean/fault in job.triage_results[node_name]."""

    def __init__(self, node_name: str, *, rng: random.Random | None = None) -> None:
        self.node_name = node_name
        self._rng = rng

    def execute(self, job: JobState) -> Outcome:
        if self._rng is None:
            result = "clean"
        else:
            result = self._rng.choice(["clean", "fault"])
        if not hasattr(job, "triage_results") or job.triage_results is None:
            job.triage_results = {}
        job.triage_results[self.node_name] = result
        return Outcome.SUCCESS if result == "clean" else Outcome.FAILURE
```

Wait -- there's a design problem. If T3 returns FAILURE ("fault"), what does the transition table do? The triage pipeline in the design doc says all 4 diagnostic nodes run serially (T3 -> T4 -> T5 -> T6 -> T7) regardless of individual results. The T7 router reads all results and picks the earliest fault. This means T3-T6 must ALL route to the next step on BOTH outcomes (clean or fault).

This means DiagnosticStubNode should always return SUCCESS (advance to next step) but store the fault/clean verdict separately. The "outcome" from the node is always SUCCESS (advance), but the triage verdict is stored on job state.

**Revised approach:**
```python
class DiagnosticStubNode(Node):
    """Returns SUCCESS to advance the triage pipeline, but records fault/clean verdict."""

    def execute(self, job: JobState) -> Outcome:
        verdict = self._rng.choice(["clean", "fault"]) if self._rng else "clean"
        job.triage_results[self.node_name] = verdict
        return Outcome.SUCCESS  # always advance; T7 reads the verdicts
```

`triage_results` is a new field on `JobState` (dict[str, str]).

### Pattern 4: T7 TriageRouterNode

**What:** T7 is not a regular stub -- it's orchestrator logic. After reading T3-T6 verdicts, it needs to cause a rewind to a specific node. The cleanest way to integrate with the existing engine is for T7 to set a routing override on job state, then return a special outcome that the engine processes.

**Two implementation options:**

Option A -- T7 returns a special Outcome (e.g., Outcome.TRIAGE_ROUTE), and the engine handles it:
Adds a new Outcome enum value and a triage routing block in `_resolve_outcome()`. Maintains separation between the node and the engine. The node stores the chosen rewind target on job state; the engine's triage handler does the rewind.

Option B -- T7 directly mutates `job.current_node`:
T7's execute() picks the rewind target, sets `job.current_node = rewind_target`, increments `job.main_retry_count`, and returns a "skip transition" sentinel. This is messy and violates the single-responsibility pattern.

**Recommendation: Option A** -- new Outcome.TRIAGE_ROUTE, engine handles routing in `_resolve_outcome()`. T7 stores its decision in a new `job.triage_rewind_target` field. Engine logic:

```python
if outcome == Outcome.TRIAGE_ROUTE:
    rewind_target = job.triage_rewind_target
    if rewind_target == "DEAD_LETTER":
        job.main_retry_count += 1
        job.status = "DEAD_LETTER"
    else:
        # Same rewind logic as FAIL: increment main retry, reset downstream conditionals
        job.main_retry_count += 1
        job.last_rejection_reason = f"Triage routed to {rewind_target}"
        if job.main_retry_count >= self._config.max_main_retries:
            job.status = "DEAD_LETTER"
        else:
            self._reset_downstream_conditionals(job, rewind_target)
    # No TRANSITION_TABLE lookup needed -- rewind_target is already the next node
    job.current_node = rewind_target
    continue  # skip the normal transition lookup
```

### Pattern 5: Triage Transition Table Wiring

**T1-T6 transitions (all advance on SUCCESS):**
```python
TRIAGE_PATH = [
    "Triage_ProfileData",
    "Triage_AnalyzeOgFlow",
    "Triage_CheckBrd",
    "Triage_CheckFsd",
    "Triage_CheckCode",
    "Triage_CheckProofmark",
    "Triage_Route",
]

# Entry: ExecuteProofmark FAILURE -> triage
TRANSITION_TABLE[("ExecuteProofmark", Outcome.FAILURE)] = "Triage_ProfileData"

# T1-T5: SUCCESS advances to next step
for i in range(6):  # T1 through T6
    TRANSITION_TABLE[(TRIAGE_PATH[i], Outcome.SUCCESS)] = TRIAGE_PATH[i + 1]

# T7 (Triage_Route) returns Outcome.TRIAGE_ROUTE -- no table entry needed
# Engine handles it directly
```

The placeholder `(TriageProofmarkFailures, SUCCESS) -> ExecuteProofmark` from Phase 2 should be **replaced** by this wiring. `TriageProofmarkFailures` as a node is superseded by the 7-step triage pipeline.

Actually, re-reading the transition table doc: `TriageProofmarkFailures` is the response node for the triage path -- it was a Phase 2 placeholder. In Phase 3, it may be replaced entirely by the T1-T7 nodes, OR it remains as a separate concept. The design doc shows both a "TriageProofmarkFailures" response node (in the Review Response Nodes table) AND the T1-T7 triage sub-pipeline. The T1-T7 pipeline is entered when ExecuteProofmark FAILS; `TriageProofmarkFailures` is a response node listed under review branching. These might be the same thing named differently, or they might be different nodes.

**Resolution:** The design doc's Review Response Nodes table has `TriageProofmarkFailures -> ExecuteProofmark` on SUCCESS. The Triage Sub-Pipeline enters on ExecuteProofmark FAILURE and has T1-T7. These are reconcilable: `TriageProofmarkFailures` is the T7 router -- the "route" step that ultimately sends the job back to ExecuteProofmark (on no-fault clean run) or rewinds earlier. In Phase 3, replace the Phase 2 placeholder `(TriageProofmarkFailures, SUCCESS) -> ExecuteProofmark` with the full T1-T7 wiring.

### Pattern 6: Validation Run

**What:** Run 100+ jobs with RNG and confirm via log inspection that all key paths were exercised.

**Implementation:** The existing `Engine.run()` and `EngineConfig(n_jobs=100)` already support this. The delta is:
1. Pick a seed that produces varied outcomes across all paths (or use no seed for true randomness)
2. After the run, scan the structured JSON logs to verify the required events occurred

The validation is log-based (as designed -- v1 has no automated assertions, logs are the artifact). The phase success criterion says "logs showing rewinds, conditional loops, FBR restarts, triage routing, and DEAD_LETTER exhaustion all occurred." A simple log scanner or manual inspection satisfies this.

Consider adding a lightweight post-run summary: count transitions by type, list which "interesting" events occurred. This doesn't have to be a full assertion framework (that's v2 VAL-01..VAL-03) -- just a readable summary in the run output.

### Anti-Patterns to Avoid

- **Storing triage verdicts as Outcome values in the transition table:** T3-T6 always advance; verdict is metadata, not routing. If you use FAILURE to mean "fault found, stop here," T7 never runs and TR-04 is unimplemented.
- **Making T7 mutate job.current_node directly:** Breaks the engine's single-responsibility loop. Rewind logic (counter increment, downstream reset) must happen in the engine, not the node.
- **Adding fbr_return_pending to TRANSITION_TABLE:** The flag is dynamic job state. The table is static routing data. Don't mix them.
- **Separate FBR response nodes:** FBR gates reuse the same response nodes as in-flow review. `WriteBrdResponse` handles both `ReviewBrd -> Conditional` and `FBR_BrdCheck -> Conditional`. The `fbr_return_pending` flag is what differentiates the return path.
- **Clearing fbr_return_pending in _resolve_outcome on the APPROVE:** The flag must survive through the response node execution and the review node's APPROVE. Clear it only when FBR_BrdCheck becomes current_node (or immediately before routing to it).
- **Triage re-using main retry counter:** TR-07 explicitly says triage routing increments the main retry counter. Don't add a separate triage counter -- main retry naturally bounds triage depth.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Post-run log analysis | Custom log parser | Shell one-liner on JSON logs, or print summary during run | v1 validation is log-based; no assertion framework needed yet (VAL-01..VAL-03 are v2) |
| Triage routing priority | Custom comparator/sort | Simple ordered if-chain: T3 first, then T4, T5, T6 | The priority order is fixed and has only 4 elements |
| FBR gate counter | Separate counter for FBR restarts | Reuse main_retry_count | Per REQUIREMENTS design decision: main retry naturally bounds all failure paths |

## Common Pitfalls

### Pitfall 1: fbr_return_pending Survives a Full Rewind (FBR-03)
**What goes wrong:** FBR gate returns FAIL -> rewinds to WriteBrd -> full replay to FBR_BrdCheck. If `fbr_return_pending` is True when the rewind starts, and you clear it only on APPROVE at a review node, it might still be True when FBR_BrdCheck is reached again, causing an infinite restart loop.
**Why it happens:** The flag is set on FBR Conditional, but FBR Fail (rewind) should NOT set it -- the rewind naturally returns to FBR_BrdCheck without needing the flag.
**How to avoid:** Only set `fbr_return_pending` on FBR Conditional outcome. On FBR Fail outcome (rewind), don't set the flag. When the job naturally reaches FBR_BrdCheck (whether via restart or natural replay), clear the flag at entry to FBR_BrdCheck.
**Warning signs:** Jobs entering FBR_BrdCheck and then immediately routing somewhere else instead of executing the gate.

### Pitfall 2: fbr_return_pending Fires at Wrong Review Node
**What goes wrong:** After FBR Conditional at FBR_ArtifactCheck, the job is at ReviewJobArtifacts with `fbr_return_pending=True`. ReviewJobArtifacts returns APPROVE. The engine routes to FBR_BrdCheck. But then it runs FBR_BrdCheck, FBR_BddCheck, FBR_FsdCheck again before reaching FBR_ArtifactCheck -- re-doing checks for things that already passed. This is CORRECT behavior per the design ("restart gauntlet from FBR_BrdCheck because a downstream fix could invalidate an upstream pass"). It's only a pitfall if you expect it to restart at the failed gate, not from the top.
**How to avoid:** Trust the design: restart is always FBR_BrdCheck. The test assertions should verify the job goes to FBR_BrdCheck, not the failed gate.

### Pitfall 3: DiagnosticStubNode Always-SUCCESS vs Node FAILURE Semantics
**What goes wrong:** T3 through T6 always return SUCCESS to advance the pipeline, but this means they can NEVER trigger the existing `(node, FAILURE) -> ...` transition logic. If someone wires `(Triage_CheckBrd, FAILURE) -> Triage_Route` thinking FAILURE means "fault found, skip to router," the triage pipeline breaks because T4-T6 never run.
**Why it happens:** Conflating node execution outcome (does the triage step itself succeed?) with diagnostic verdict (did it find a fault in the artifact?).
**How to avoid:** T3-T6 always return SUCCESS. Fault/clean verdict stored in `job.triage_results`. T7 reads `triage_results`, not the Outcome values.
**Warning signs:** Triage path that jumps from T3 directly to T7 when a fault is found.

### Pitfall 4: TriageProofmarkFailures Placeholder Conflict
**What goes wrong:** Phase 2 added `(TriageProofmarkFailures, SUCCESS) -> ExecuteProofmark` as a placeholder. Phase 3 now wires `(ExecuteProofmark, FAILURE) -> Triage_ProfileData`. If TriageProofmarkFailures still exists in the registry but isn't connected to anything meaningful, `validate_transition_table()` may not catch it (it only validates HAPPY_PATH nodes).
**How to avoid:** Phase 3 plan should explicitly handle the TriageProofmarkFailures placeholder -- either remove it (if it's superseded by T1-T7) or integrate it (if T7 maps to it). Document the decision explicitly.

### Pitfall 5: Response Node FAILURE Still Has No Edge
**What goes wrong:** Phase 2 deferred `(ResponseX, FAILURE) -> ...` edges. In Phase 3, a response node being used in the FBR fix loop (e.g., `WriteBrdResponse` after `FBR_BrdCheck` Conditional) can now FAIL, and there's still no transition. The engine raises ValueError.
**Why it happens:** Phase 2 deferred it; Phase 3 must decide.
**How to avoid:** Phase 3 plan must explicitly wire `(ResponseX, FAILURE)` edges. Simplest option: treat response node FAILURE as a rewind to the same target as the paired review node's FAIL. E.g., `(WriteBrdResponse, FAILURE) -> WriteBrd`. This is consistent with "a failed response is still a failed write."
**Warning signs:** ValueError crash during a validation run when a response node returns FAILURE.

### Pitfall 6: Triage Counter Scoping (TR-07 vs SM-04)
**What goes wrong:** T7 does a rewind that increments `main_retry_count`. But the main retry limit is checked BEFORE the rewind executes. If main_retry_count is already at N-1, a triage rewind pushes it to N, causing DEAD_LETTER. This is CORRECT per TR-06 ("no faults found -> DEAD_LETTER") and SM-05 ("N fails -> DEAD_LETTER"). Not a bug, but it needs to be tested explicitly.
**How to avoid:** Test that a job with max_main_retries=2, one prior FAIL, and a triage "no faults" result goes to DEAD_LETTER after T7.

### Pitfall 7: Validation Run Seed Selection
**What goes wrong:** A fixed seed that happens to produce only happy-path outcomes in 100+ jobs. The success criterion requires all major paths to have occurred.
**How to avoid:** Use a known seed that produces varied outcomes, or use no seed (random). After the run, print a path coverage summary. If the run is deterministic (seeded), verify during development that the seed exercises all paths. Alternatively, run with a small RNG probability distribution that favors non-success outcomes.

## Code Examples

### JobState New Fields
```python
# models.py -- add to JobState dataclass
fbr_return_pending: bool = False
triage_results: dict[str, str] = field(default_factory=dict)
triage_rewind_target: str | None = None
```

### Outcome Enum Extension
```python
# models.py -- add to Outcome enum
TRIAGE_ROUTE = auto()
```

### FBR_ROUTING Dict
```python
# transitions.py
FBR_ROUTING: dict[str, tuple[str, str]] = {
    "FBR_BrdCheck":      ("WriteBrdResponse",          "WriteBrd"),
    "FBR_BddCheck":      ("WriteBddResponse",          "WriteBddTestArch"),
    "FBR_FsdCheck":      ("WriteFsdResponse",          "WriteFsd"),
    "FBR_ArtifactCheck": ("BuildJobArtifactsResponse", "BuildJobArtifacts"),
    "FBR_ProofmarkCheck":("BuildProofmarkResponse",    "BuildProofmarkConfig"),
    "FBR_UnitTestCheck": ("BuildUnitTestsResponse",    "BuildUnitTests"),
}

# Add CONDITIONAL and FAIL edges for FBR gates
for fbr_gate, (response_node, rewind_target) in FBR_ROUTING.items():
    TRANSITION_TABLE[(fbr_gate, Outcome.CONDITIONAL)] = response_node
    TRANSITION_TABLE[(fbr_gate, Outcome.FAIL)] = rewind_target
    # Note: response_node SUCCESS edges already exist from Phase 2 REVIEW_ROUTING wiring
```

### fbr_return_pending Handling in Engine
```python
# engine.py -- in run_job() after resolving transition

# FBR-04: if fbr_return_pending and this is an APPROVE at an in-flow review node,
# redirect to FBR_BrdCheck and clear the flag.
if (
    outcome == Outcome.APPROVE
    and job.fbr_return_pending
    and job.current_node in REVIEW_ROUTING  # in-flow review, not FBR gate
):
    next_node = "FBR_BrdCheck"
    job.fbr_return_pending = False

# Clear fbr_return_pending flag when entering FBR_BrdCheck (handles natural replay case)
if next_node == "FBR_BrdCheck":
    job.fbr_return_pending = False
```

### FBR Conditional Sets fbr_return_pending
```python
# engine.py -- in _resolve_outcome() when an FBR gate returns CONDITIONAL
if outcome == Outcome.CONDITIONAL and node_name in FBR_ROUTING:
    job.fbr_return_pending = True
    # Counter logic for FBR gates follows same rules as in-flow review nodes
    # (conditional counter per gate, M auto-promotes to FAIL, FAIL rewinds)
```

### Triage Pipeline Transitions
```python
# transitions.py
TRIAGE_NODES: list[str] = [
    "Triage_ProfileData",
    "Triage_AnalyzeOgFlow",
    "Triage_CheckBrd",
    "Triage_CheckFsd",
    "Triage_CheckCode",
    "Triage_CheckProofmark",
    "Triage_Route",
]

# Entry point: ExecuteProofmark FAILURE -> T1
TRANSITION_TABLE[("ExecuteProofmark", Outcome.FAILURE)] = "Triage_ProfileData"

# T1-T6: SUCCESS -> next step
for i in range(6):
    TRANSITION_TABLE[(TRIAGE_NODES[i], Outcome.SUCCESS)] = TRIAGE_NODES[i + 1]

# T7 (Triage_Route): handled in engine via TRIAGE_ROUTE outcome
# No table entry needed for Triage_Route
```

### T7 TriageRouterNode
```python
# nodes.py
class TriageRouterNode(Node):
    """T7: reads T3-T6 verdicts from job state and sets the rewind target."""

    # Priority order: T3 (BRD) -> T4 (FSD) -> T5 (Code) -> T6 (Proofmark)
    FAULT_ROUTING: dict[str, str] = {
        "Triage_CheckBrd":      "WriteBrd",
        "Triage_CheckFsd":      "WriteFsd",
        "Triage_CheckCode":     "BuildJobArtifacts",
        "Triage_CheckProofmark":"BuildProofmarkConfig",
    }

    def execute(self, job: JobState) -> Outcome:
        for check_node, rewind_target in self.FAULT_ROUTING.items():
            if job.triage_results.get(check_node) == "fault":
                job.triage_rewind_target = rewind_target
                return Outcome.TRIAGE_ROUTE
        # No faults found -> DEAD_LETTER
        job.triage_rewind_target = "DEAD_LETTER"
        return Outcome.TRIAGE_ROUTE
```

### TRIAGE_ROUTE Handling in Engine
```python
# engine.py -- in _resolve_outcome() or run_job() loop

if outcome == Outcome.TRIAGE_ROUTE:
    rewind_target = job.triage_rewind_target
    job.triage_results = {}  # reset for next triage pass
    job.main_retry_count += 1
    job.last_rejection_reason = f"Triage routed to {rewind_target}"

    if rewind_target == "DEAD_LETTER" or job.main_retry_count >= self._config.max_main_retries:
        job.status = "DEAD_LETTER"
        return outcome

    self._reset_downstream_conditionals(job, rewind_target)
    # Engine loop will route to rewind_target directly
```

### Response Node FAILURE Edges
```python
# transitions.py -- add alongside REVIEW_ROUTING loop
# Treat response node FAILURE as equivalent to the paired review node FAIL (same rewind target)
for review_node, (response_node, rewind_target) in REVIEW_ROUTING.items():
    TRANSITION_TABLE[(response_node, Outcome.FAILURE)] = rewind_target

# FBR response nodes share the same response nodes -- same FAILURE edges apply
```

## State of the Art

| Old | Current | Notes |
|-----|---------|-------|
| `TriageProofmarkFailures` Phase 2 placeholder routes to ExecuteProofmark | Phase 3 replaces with full T1-T7 pipeline | The Phase 2 placeholder edge must be removed or superseded |
| 6 FBR gates have only APPROVE edges | Phase 3 adds CONDITIONAL and FAIL edges + fbr_return_pending flag | FBR gates were already in HAPPY_PATH; adding the failure paths completes them |

**Deferred/pending from Phase 2:**
- `(ResponseX, FAILURE)` edges: no transition exists. Phase 3 must wire these (see Pitfall 5).
- `TriageProofmarkFailures` placeholder: Phase 3 supersedes it with T1-T7.

## Open Questions

1. **TriageProofmarkFailures disposition**
   - What we know: Phase 2 added it as a stub with `(TriageProofmarkFailures, SUCCESS) -> ExecuteProofmark`. The design doc lists it as a response node in the review branching table.
   - What's unclear: Is it replaced entirely by T1-T7, or does it coexist as the "re-execute proofmark after triage fix" response node?
   - Recommendation: In Phase 3, `TriageProofmarkFailures` can be retired. The triage pipeline enters at `Triage_ProfileData` and exits via T7's rewind. After the rewind and replay, the job naturally re-executes `ExecuteProofmark` when it reaches that point again. Remove the Phase 2 placeholder edge from TRANSITION_TABLE.

2. **FBR gate conditional counters -- same M limit or separate?**
   - What we know: FBR gates are REVIEW nodes. The conditional counter logic in `_resolve_outcome()` applies to all nodes in `_REVIEW_NODES`.
   - What's unclear: Should FBR gates share the same `max_conditional_per_node` limit as in-flow review nodes? There's no spec distinction.
   - Recommendation: Use the same `max_conditional_per_node` limit. FBR gates are review nodes; no reason to treat them differently. If the limit is hit, auto-promote to FAIL (which rewinds, incrementing main retry).

3. **FBR FAIL counter reset scope**
   - What we know: FBR_ROUTING gives rewind targets (e.g., FBR_BrdCheck FAIL -> WriteBrd). `_reset_downstream_conditionals` uses HAPPY_PATH.index to find the boundary.
   - What's unclear: `_reset_downstream_conditionals` already handles FBR rewinds correctly via HAPPY_PATH index, since FBR gates are IN HAPPY_PATH. No code change needed.
   - Recommendation: Verify that `_reset_downstream_conditionals` is called when an FBR gate fails (rewinds). The existing code in `_resolve_outcome()` checks `if node_name in REVIEW_ROUTING` -- FBR gates are NOT in REVIEW_ROUTING. Need to either update that check to `if node_name in REVIEW_ROUTING or node_name in FBR_ROUTING`, or consolidate routing dicts.

4. **triage_results reset timing**
   - What we know: If a job hits triage multiple times (multiple ExecuteProofmark failures), triage_results from the first pass should not bleed into the second.
   - Recommendation: Clear `job.triage_results = {}` when the engine enters `Triage_ProfileData` (or when Triage_Route's rewind logic fires). Clearing on entry to T1 is cleaner.

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
| FBR-01 | 6 FBR gates execute in serial after Publish | unit | `python -m pytest tests/test_transitions.py::TestFBRGauntlet::test_fbr_gate_edges_in_transition_table -x` | No - Wave 0 |
| FBR-02 | FBR Conditional: response -> review -> approve -> FBR_BrdCheck | integration | `python -m pytest tests/test_engine.py::TestFBRGauntlet::test_fbr_conditional_restarts_gauntlet -x` | No - Wave 0 |
| FBR-03 | FBR Fail: rewinds to write node, replays, naturally hits FBR_BrdCheck | integration | `python -m pytest tests/test_engine.py::TestFBRGauntlet::test_fbr_fail_rewinds_to_write_node -x` | No - Wave 0 |
| FBR-04 | fbr_return_pending flag routes post-fix approval to FBR_BrdCheck | unit | `python -m pytest tests/test_engine.py::TestFBRGauntlet::test_fbr_return_pending_flag -x` | No - Wave 0 |
| TR-01 | ExecuteProofmark FAILURE enters triage | unit | `python -m pytest tests/test_transitions.py::TestTriage::test_proofmark_failure_enters_triage -x` | No - Wave 0 |
| TR-02 | T1-T2 are context-gathering stubs, advance on SUCCESS | unit | `python -m pytest tests/test_nodes.py::TestTriageNodes::test_t1_t2_context_gathering -x` | No - Wave 0 |
| TR-03 | T3-T6 diagnostic stubs record clean/fault in triage_results | unit | `python -m pytest tests/test_nodes.py::TestTriageNodes::test_diagnostic_stubs_record_verdict -x` | No - Wave 0 |
| TR-04 | T7 routes to earliest fault found | unit | `python -m pytest tests/test_engine.py::TestTriage::test_t7_routes_to_earliest_fault -x` | No - Wave 0 |
| TR-05 | Multiple faults route to earliest | unit | `python -m pytest tests/test_engine.py::TestTriage::test_multiple_faults_route_to_earliest -x` | No - Wave 0 |
| TR-06 | No faults -> DEAD_LETTER | unit | `python -m pytest tests/test_engine.py::TestTriage::test_no_faults_dead_letter -x` | No - Wave 0 |
| TR-07 | Triage routing increments main retry counter | unit | `python -m pytest tests/test_engine.py::TestTriage::test_triage_increments_main_retry -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_transitions.py::TestFBRGauntlet` -- FBR edge coverage (FBR_ROUTING entries, CONDITIONAL/FAIL edges for all 6 gates)
- [ ] `tests/test_transitions.py::TestTriage` -- triage entry edge, T1-T6 advance edges
- [ ] `tests/test_engine.py::TestFBRGauntlet` -- FBR-02, FBR-03, FBR-04 behavior tests using ScriptedNode
- [ ] `tests/test_engine.py::TestTriage` -- TR-04 through TR-07 using ScriptedNode + direct triage_results setup
- [ ] `tests/test_nodes.py::TestTriageNodes` -- TR-02, TR-03 node behavior
- [ ] `tests/test_models.py` -- new JobState fields (fbr_return_pending, triage_results, triage_rewind_target)

Existing test infrastructure (conftest.py, ScriptedNode, _capture_logs, pytest config) is fully sufficient. No new framework setup needed.

## Sources

### Primary (HIGH confidence)
- `/workspace/AtcStrategy/POC6/BDsNotes/state-machine-transitions.md` -- canonical transition table, FBR routing, triage sub-pipeline, T7 routing table
- `.planning/REQUIREMENTS.md` -- all 11 phase requirements (FBR-01..FBR-04, TR-01..TR-07) with exact descriptions
- `src/workflow_engine/` -- all 7 source modules read and analyzed; full Phase 2 implementation confirmed
- `.planning/phases/02-review-branching-and-counter-mechanics/02-VERIFICATION.md` -- Phase 2 verified complete, 59 tests passing, all 11 Phase 2 requirements satisfied
- `.planning/phases/02-review-branching-and-counter-mechanics/02-02-SUMMARY.md` -- Phase 2 Plan 02 decisions, including deferred response node FAILURE edges

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` -- accumulated design decisions, confirms counter model simplification
- `.planning/ROADMAP.md` -- Phase 3 success criteria verbatim

## Metadata

**Confidence breakdown:**
- FBR gauntlet: HIGH -- transition table structure and fbr_return_pending semantics are fully specified in design doc; code patterns from Phase 2 extend cleanly
- Triage sub-pipeline: HIGH -- T1-T7 structure fully specified; the DiagnosticStubNode always-SUCCESS pattern is the only non-obvious design decision, and it's driven directly by the spec
- Pitfalls: HIGH -- identified from direct spec analysis and Phase 2 implementation patterns; no speculation
- Validation run: HIGH -- existing engine already supports N-job runs; no new infrastructure needed

**Research date:** 2026-03-13
**Valid until:** Indefinite -- custom codebase, no external dependencies
