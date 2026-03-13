# Architecture Patterns

**Domain:** Python deterministic state-machine workflow engine
**Researched:** 2026-03-13

## Recommended Architecture

Build a custom pure-Python state machine. No external FSM library. The project requirements (rewind semantics, FBR gauntlet restart, triage sub-pipeline routing, per-node retry counters with conditional-to-fail promotion) are domain-specific enough that fighting a library's abstraction will cost more than rolling your own. The total transition logic is roughly 200-400 lines of Python -- the complexity is in the transition table definition and the counter/rewind bookkeeping, not in the FSM mechanics themselves.

**Confidence: HIGH** -- The design docs are extremely precise. The transition table is fully specified. This is a "translate the spec into code" problem, not a "figure out what to build" problem.

### Why Not a Library?

| Library | Why Not |
|---------|---------|
| `python-statemachine` (v3.0) | Compound states and statecharts are overkill. Its guard/callback model doesn't naturally express "4th conditional auto-promotes to fail" or "rewind to node X and replay forward." You'd spend more time bending the library than writing the logic. |
| `pytransitions/transitions` | Closer to what you need (flat FSM, callback-driven), but its transition model is trigger-based ("send event X to move from A to B"). Your model is outcome-based ("node returns Approve/Conditional/Fail, engine resolves next state"). The impedance mismatch isn't worth the dependency. |
| Temporal / Prefect / Airflow | Distributed workflow engines. You're running single-threaded in-memory for v0.1. These are 50x the complexity you need. |

**Roll your own because:**
1. The transition table is already fully specified in design docs
2. Rewind semantics (replay forward from an earlier node) aren't a standard FSM concept
3. The three-outcome review model with conditional counters is custom domain logic
4. Pure Python with zero dependencies is an explicit project constraint
5. Total code is small -- testability and debuggability matter more than framework features

### Component Diagram

```
+------------------------------------------------------------------+
|                         Engine (main loop)                        |
|                                                                   |
|  for each job:                                                    |
|    while job.state != COMPLETE and job.state != DEAD_LETTER:      |
|      node = registry[job.state]                                   |
|      outcome = node.execute(job)                                  |
|      next_state = resolver.resolve(job, job.state, outcome)       |
|      job.transition_to(next_state)                                |
+------------------------------------------------------------------+
         |              |                |               |
         v              v                v               v
+-------------+  +-------------+  +-------------+  +-------------+
| Node        |  | Transition  |  | Job State   |  | Logger      |
| Registry    |  | Resolver    |  | (per job)   |  |             |
+-------------+  +-------------+  +-------------+  +-------------+
| Maps state  |  | Centralized |  | current     |  | Structured  |
| names to    |  | transition  |  | state       |  | log of all  |
| executable  |  | table +     |  | retry       |  | transitions |
| node objects|  | counter     |  | counters    |  | and outcomes|
|             |  | logic +     |  | conditional |  |             |
|             |  | rewind      |  | counters    |  |             |
|             |  | resolution  |  | triage      |  |             |
|             |  |             |  | counters    |  |             |
|             |  |             |  | FBR depth   |  |             |
|             |  |             |  | last reject |  |             |
+-------------+  +-------------+  +-------------+  +-------------+
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Engine** | Main loop. Iterates jobs, drives execute-resolve-transition cycle. | Node Registry, Transition Resolver, Job State, Logger |
| **Node Registry** | Maps state name (str) to Node object. Lookup only. | Engine (queried by) |
| **Node (abstract)** | Executes one step. Returns an Outcome enum. Knows nothing about transitions. | Engine (called by), Job State (reads context from) |
| **ReviewNode (subclass)** | Returns Approve/Conditional/Fail. RNG in v0.1. | Engine (called by) |
| **WorkNode (subclass)** | Returns Success/Failure. RNG in v0.1. | Engine (called by) |
| **TriageRouterNode** | Pure logic node (T7). Reads triage results, returns routing decision. No agent. | Engine (called by), Job State (reads triage outputs) |
| **Transition Resolver** | Given (current_state, outcome), returns next_state. Owns ALL branching logic: happy path, conditional routing, fail rewind, FBR restart, triage routing, retry exhaustion. | Engine (called by), Job State (reads/writes counters) |
| **Job State** | Per-job mutable state bag. Current state, all counters, last rejection reason, triage outputs. | Engine, Transition Resolver, Nodes (all read/write) |
| **Logger** | Records every transition with job_id, from_state, to_state, outcome, counters. | Engine (called by) |

### Data Flow

```
1. Engine picks next job (round-robin or sequential, doesn't matter for v0.1)

2. Engine looks up current state in Node Registry
   job.state = "ReviewBrd" --> registry["ReviewBrd"] --> ReviewNode(blueprint="brd-reviewer")

3. Engine calls node.execute(job)
   - ReviewNode rolls RNG --> Outcome.CONDITIONAL
   - Node returns outcome, does NOT decide next state

4. Engine calls resolver.resolve(job, "ReviewBrd", Outcome.CONDITIONAL)
   Resolver logic:
     a. Check conditional counter for ReviewBrd
     b. counter < 3 --> increment, set job.last_rejection = "stubbed feedback"
        return "WriteBrdResponse"
     c. counter >= 3 --> auto-promote to Fail, delegate to fail logic
        return "WriteBrd" (rewind target)

5. Engine calls job.transition_to(next_state)
   - Updates job.state
   - Logger records the transition

6. Loop continues until COMPLETE or DEAD_LETTER
```

### Rewind Flow (Fail Path)

```
ReviewBrd returns Fail
  --> Resolver looks up fail rewind target: "WriteBrd"
  --> Resolver resets all downstream counters (everything after WriteBrd)
  --> job.state = "WriteBrd"
  --> Engine re-executes from WriteBrd forward through the entire happy path

The key insight: rewind doesn't need special machinery.
Setting job.state to an earlier node and clearing downstream counters IS the rewind.
The main loop naturally replays everything forward.
```

### FBR Gauntlet Flow

```
FBR_FsdCheck returns Fail
  --> Resolver looks up FBR fail target: "WriteFsdResponse"
  --> After WriteFsdResponse --> ReviewFsd --> on approve:
      Resolver checks "are we in FBR context?" (job came from an FBR gate)
      YES --> route to FBR_BrdCheck (restart gauntlet from top)
  --> Resolver increments FBR depth counter
  --> FBR depth >= cap --> DEAD_LETTER

Implementation detail: The resolver needs to know whether a review approval
should route to the normal happy path or back to FBR_BrdCheck. This is the
one piece of "context" the resolver needs beyond the current state + outcome.
Solution: a flag on JobState (e.g., job.fbr_return_pending = True) that the
resolver checks when processing review approvals.
```

### Triage Sub-Pipeline Flow

```
ExecuteProofmark returns Failure
  --> Resolver routes to Triage_ProfileData (T1)
  --> T1 through T6 execute sequentially, each storing results on JobState
  --> T7 (TriageRouterNode) reads T3-T6 results:
      - Earliest fault wins --> resolver returns rewind target
      - No faults --> DEAD_LETTER
  --> After fix and re-execution, if proofmark fails again:
      Resolver increments triage counter
      triage counter >= cap --> DEAD_LETTER
```

## Component Design Details

### Transition Resolver: The Heart of the Engine

The resolver is where all complexity lives. It should be a single class with a centralized transition table, NOT distributed logic across nodes.

```python
# Conceptual structure -- not final code

class TransitionResolver:
    """Resolves (state, outcome) --> next_state, managing all counters and rewind logic."""

    # Happy path transitions: state --> next_state (on success/approve)
    HAPPY_PATH: dict[str, str] = {
        "LocateOgSourceFiles": "InventoryOutputs",
        "InventoryOutputs": "InventoryDataSources",
        # ... all 27 nodes
    }

    # Review conditional targets: review_state --> response_node
    CONDITIONAL_TARGETS: dict[str, str] = {
        "ReviewBrd": "WriteBrdResponse",
        "ReviewBdd": "WriteBddResponse",
        # ...
    }

    # Review fail rewind targets: review_state --> rewind_to_node
    FAIL_REWIND_TARGETS: dict[str, str] = {
        "ReviewBrd": "WriteBrd",
        "ReviewBdd": "WriteBddTestArch",
        "ReviewFsd": "WriteFsd",
        # ...
    }

    # FBR gate fail targets: fbr_gate --> response_node
    FBR_FAIL_TARGETS: dict[str, str] = {
        "FBR_BrdCheck": "WriteBrdResponse",
        "FBR_BddCheck": "WriteBddResponse",
        # ...
    }

    # Triage routing: triage_layer --> rewind_target
    TRIAGE_ROUTES: dict[str, str] = {
        "brd": "WriteBrd",
        "fsd": "WriteFsd",
        "code": "BuildJobArtifacts",
        "proofmark": "BuildProofmarkConfig",
    }

    def resolve(self, job: JobState, current: str, outcome: Outcome) -> str:
        # 1. Check retry exhaustion first (any node)
        # 2. If review node + Conditional: check conditional counter
        # 3. If review node + Fail: look up rewind target
        # 4. If FBR gate + Fail: look up FBR fail target, set fbr flag
        # 5. If review node + Approve + fbr_return_pending: route to FBR_BrdCheck
        # 6. If triage router: read triage results, route accordingly
        # 7. Default: happy path lookup
        ...
```

**Why centralized:** All transition logic in one place means one place to debug, one place to test, one place to verify against the spec. Distributing routing logic across 27+ node classes would be a maintenance nightmare.

### Job State: The Per-Job State Bag

```python
@dataclass
class JobState:
    job_id: str
    state: str = "LocateOgSourceFiles"

    # Per-node retry counters (node_name -> attempts)
    retry_counts: dict[str, int] = field(default_factory=dict)

    # Per-review conditional counters (review_node -> conditional_count)
    conditional_counts: dict[str, int] = field(default_factory=dict)

    # FBR tracking
    fbr_depth: int = 0
    fbr_return_pending: bool = False

    # Triage tracking
    triage_count: int = 0
    triage_results: dict[str, tuple[str, str]] = field(default_factory=dict)
    # e.g. {"T3": ("fault", "BRD misses data flow X"), "T4": ("clean", "")}

    # Most recent rejection reason (not accumulated)
    last_rejection_reason: str = ""

    # Terminal state
    terminal: bool = False
```

### Node Hierarchy

```
Node (ABC)
  execute(job: JobState) -> Outcome

  WorkNode(Node)           -- returns Success | Failure
    StubWorkNode           -- RNG-based for v0.1

  ReviewNode(Node)         -- returns Approve | Conditional | Fail
    StubReviewNode         -- RNG-based for v0.1

  TriageNode(Node)         -- T1-T6 triage steps, returns Success | Failure
    StubTriageNode         -- RNG-based for v0.1

  TriageRouterNode(Node)   -- T7, pure logic, reads triage results
    (no stub needed -- this is always deterministic logic)
```

Nodes are dumb. They do their thing and return an outcome. They don't know about transitions, counters, or other nodes. This is critical -- the resolver owns all routing decisions.

### Outcome Enum

```python
class Outcome(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    APPROVE = "approve"
    CONDITIONAL = "conditional"
    FAIL = "fail"  # Review-specific: "fundamentally wrong, rewrite"
```

Note: SUCCESS/FAILURE for work nodes, APPROVE/CONDITIONAL/FAIL for review nodes. The resolver knows which outcomes are valid for which node types based on the transition table.

### Node Registry

Simple dict mapping state names to node instances. Built once at startup from config.

```python
registry: dict[str, Node] = {
    "LocateOgSourceFiles": StubWorkNode("og-locator"),
    "InventoryOutputs": StubWorkNode("output-analyst"),
    # ...
    "ReviewBrd": StubReviewNode("brd-reviewer"),
    # ...
    "Triage_ProfileData": StubTriageNode("data-profiler"),
    # ...
    "Triage_Route": TriageRouterNode(),
}
```

### Logger

Structured logging to stdout (or file). Each log entry:

```python
@dataclass
class TransitionLog:
    timestamp: str
    job_id: str
    from_state: str
    outcome: str
    to_state: str
    retry_count: int          # current retry count for this node
    conditional_count: int    # if review node
    fbr_depth: int
    triage_count: int
```

Use Python's `logging` module with JSON formatter. Logs are the primary validation artifact for v0.1 -- they need to be machine-parseable for post-hoc analysis.

## Patterns to Follow

### Pattern 1: Centralized Transition Table

**What:** All routing logic lives in one class (TransitionResolver) with declarative data structures (dicts) and one `resolve()` method.

**When:** Always. This is the core architectural decision.

**Why:** The transition table in the design docs IS the specification. The code should mirror it 1:1. Reviewer should be able to hold the design doc in one hand and the resolver code in the other and verify correctness line-by-line.

### Pattern 2: State as String, Not Object

**What:** States are plain strings ("ReviewBrd", "FBR_BrdCheck"), not class instances.

**When:** Always. State identity is the string name. Behavior comes from the node registry lookup.

**Why:** The transition table is a string-to-string mapping. Making states into objects adds indirection without value. You need to print states in logs, use them as dict keys, and compare them. Strings are perfect for all of this.

### Pattern 3: Counter Reset on Rewind

**What:** When a fail causes rewind to node X, clear all retry and conditional counters for nodes downstream of X.

**When:** Every fail rewind and every FBR gauntlet restart.

**Why:** A rewind means "start fresh from here." If you don't clear downstream counters, a previously-failed node that used 2 of its 3 retries will only get 1 retry on the replay. The whole point of rewind is a fresh attempt.

**Implementation:** Maintain an ordered list of happy-path nodes. On rewind to index N, clear counters for all nodes at index > N. For FBR nodes, maintain a separate ordered list and clear similarly.

### Pattern 4: Outcome Drives Everything, Not Events

**What:** Nodes return an Outcome enum. The resolver maps (state, outcome) to next state. No event/trigger system.

**When:** Always.

**Why:** Libraries like `transitions` use an event-trigger model ("send 'approve' event to machine"). Your model is simpler: node runs, returns result, resolver decides. No event bus, no event handlers, no event ordering concerns.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Smart Nodes

**What:** Nodes that know about transitions, other nodes, or the pipeline structure.

**Why bad:** A node that decides "on failure, go to WriteBrdResponse" now owns routing logic. Change the transition table and you're hunting through 27+ node classes. Testing requires mocking the whole pipeline.

**Instead:** Nodes return outcomes. Period. The resolver owns all routing.

### Anti-Pattern 2: Distributed Counter Management

**What:** Each node manages its own retry counter.

**Why bad:** Counter reset on rewind requires knowing which counters to clear. If counters are scattered across nodes, the rewind logic needs to reach into every downstream node to reset them.

**Instead:** All counters live on JobState. The resolver reads/writes them centrally. Rewind clears them by iterating the ordered node list.

### Anti-Pattern 3: Implicit FBR Context

**What:** Using the call stack or execution history to determine "are we in an FBR restart?"

**Why bad:** The engine loop is flat (while loop, not recursion). There's no call stack to inspect. Execution history requires scanning backward through logs.

**Instead:** Explicit `fbr_return_pending` flag on JobState. Set it when an FBR gate triggers a fix. Clear it when the review approves and routes back to FBR_BrdCheck.

### Anti-Pattern 4: Enum Proliferation for States

**What:** Creating a Python Enum with 35+ members for every possible state.

**Why bad:** Every time you add a state (and you will -- triage sub-pipeline alone adds 7), you're editing an enum class. String-based states with validation at startup (assert all referenced states exist in registry) is simpler and just as safe.

**Instead:** String states + startup validation that every state referenced in the transition table exists in the node registry.

## Suggested Build Order

This is the dependency chain for implementation phases:

```
Phase 1: Foundation
  JobState, Outcome enum, Node ABC, Logger
  (no dependencies, pure data + interface definitions)

Phase 2: Stub Nodes
  StubWorkNode, StubReviewNode, StubTriageNode
  Node Registry construction
  (depends on: Phase 1)

Phase 3: Transition Resolver -- Happy Path Only
  HAPPY_PATH table, resolve() for success-only
  (depends on: Phase 1)

Phase 4: Engine Main Loop
  Wire together: registry + resolver + job state + logger
  Run N jobs through happy path
  (depends on: Phases 1-3)
  ** First runnable milestone **

Phase 5: Review Branching
  Conditional routing, conditional counters, 4th-conditional-to-fail
  Fail rewind logic, counter reset on rewind
  Response nodes in registry
  (depends on: Phase 4)

Phase 6: FBR Gauntlet
  FBR gates in transition table
  FBR fail routing to response nodes
  fbr_return_pending flag
  FBR depth cap + DEAD_LETTER
  Gauntlet restart from FBR_BrdCheck
  (depends on: Phase 5)

Phase 7: Triage Sub-Pipeline
  T1-T7 nodes in registry
  Triage results storage on JobState
  TriageRouterNode (T7) deterministic logic
  Triage counter + exhaustion
  Proofmark failure -> triage entry
  (depends on: Phase 5, builds on rewind logic)

Phase 8: Retry Exhaustion + DEAD_LETTER
  Per-node retry limits (configurable)
  Exhaustion detection in resolver
  DEAD_LETTER terminal state
  (can be woven in during Phases 5-7, but worth its own validation pass)

Phase 9: Validation Run
  Run 100+ jobs, verify all paths exercised via logs
  Verify: happy path, conditional loops, fail rewinds, FBR restarts,
          triage routing, retry exhaustion, DEAD_LETTER
  (depends on: all above)
```

**Critical dependency insight:** Phases 5-7 all depend on Phase 4 (working engine with happy path). Phase 4 is the first thing that runs. Get there fast. Everything after is incremental additions to the resolver's `resolve()` method and new entries in the transition tables.

## Scalability Considerations

| Concern | v0.1 (in-memory) | Future (Postgres) | Notes |
|---------|-------------------|-------------------|-------|
| Job state persistence | Python dicts in memory | `control.task_queue` rows | JobState dataclass serializes to JSON trivially |
| Concurrency | Single-threaded, sequential | Postgres SELECT FOR UPDATE + parallelism cap | Engine loop becomes worker pool, but resolver logic is identical |
| Node execution | Stub (RNG) | `claude -p` subprocess | Node ABC stays the same, swap StubWorkNode for ClaudeCliNode |
| Logging | stdout / JSON file | Postgres + stdout | Logger interface unchanged |
| Counter storage | JobState dicts | Postgres columns or JSON column | No structural change |

The architecture is designed so that v0.1 in-memory concerns are swappable for production infrastructure without changing the core engine, resolver, or node interfaces.

## Sources

- Transition table specification: `/workspace/AtcStrategy/POC6/BDsNotes/state-machine-transitions.md`
- Architecture notes: `/workspace/AtcStrategy/POC6/BDsNotes/poc6-architecture.md`
- Agent taxonomy: `/workspace/AtcStrategy/POC6/BDsNotes/agent-taxonomy.md`
- [pytransitions/transitions](https://github.com/pytransitions/transitions) -- evaluated, not recommended
- [python-statemachine v3.0](https://python-statemachine.readthedocs.io/) -- evaluated, not recommended
- [Workflow Engine vs State Machine](https://workflowengine.io/blog/workflow-engine-vs-state-machine/) -- pattern context
- [Python 3 Patterns: StateMachine](https://python-3-patterns-idioms-test.readthedocs.io/en/latest/StateMachine.html) -- centralized transition table pattern
- [Temporal durable execution model](https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications) -- rewind/replay concepts (not used, but informed thinking)
