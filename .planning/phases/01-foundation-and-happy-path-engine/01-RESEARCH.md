# Phase 1: Foundation and Happy Path Engine - Research

**Researched:** 2026-03-13
**Domain:** Python state machine engine -- data modeling, transition tables, structured logging
**Confidence:** HIGH

## Summary

Phase 1 builds the skeleton of the workflow engine: job state model, declarative transition table, stub nodes, engine main loop, and structured logging. The entire phase is pure Python with one external dependency (structlog). There are zero unknowns about *what* to build -- the transition table is fully specified with 27 happy-path nodes, and the requirements explicitly constrain the design (dict-based transitions, in-memory state, single-threaded, sequential execution).

The main design tension is how much future-proofing to bake in. Phase 1 only needs happy-path routing (all stubs return success/approve), but the job state model must accommodate the counter mechanics and rewind semantics coming in Phase 2. The transition table data structure must be extensible for conditional/fail edges without a rewrite. The research summary from project setup already nailed this: design the state model for the full pipeline, implement only happy-path routing.

**Primary recommendation:** Build the JobState dataclass with all counter fields from day one (main retry N, per-node conditional M dict), but only implement happy-path transition resolution. The transition table should be a dict keyed by (node_name, outcome) -> next_node, pre-populated with only Success/Approve edges for Phase 1, with the structure ready for Conditional/Fail edges in Phase 2.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SM-01 | Job state tracks current node, main retry counter, and per-node conditional counters | JobState dataclass with current_node, main_retry_count, conditional_counts dict |
| SM-02 | Transition table is declarative data (dict-based), not procedural if/else | Dict keyed by (node, outcome) tuples -- see Architecture Patterns |
| SM-03 | Main retry counter (N) and conditional limit (M) are configurable with sensible defaults | EngineConfig dataclass with max_main_retries=5, max_conditional_per_node=3 |
| HP-01 | 27 happy-path nodes execute in order from LocateOgSourceFiles through FinalSignOff -> COMPLETE | HAPPY_PATH ordered list + transition table entries for all 27 Success/Approve edges |
| HP-02 | Each node is a stub with a comment describing what the real agent will do | Node ABC with execute() -> Outcome, stubs return hardcoded Success/Approve |
| HP-03 | Non-review stubs return Success/Failure via RNG | StubWorkNode with random outcome (but happy-path test forces all-success) |
| HP-04 | Review stubs return Approve/Conditional/Fail via RNG | StubReviewNode with random outcome (but happy-path test forces all-approve) |
| ENG-01 | Engine main loop: pick job, resolve transition, execute stub, advance state, repeat | Engine.run_job() while loop -- see Code Examples |
| ENG-02 | Run N configurable jobs through the full pipeline | Engine.run(n_jobs) calling run_job() sequentially |
| ENG-03 | In-memory job state (no Postgres) | JobState is a plain dataclass, jobs list is a Python list |
| ENG-04 | Single-threaded sequential execution | Simple for loop, no threading/async |
| LOG-01 | Structured JSON logging via structlog | structlog 25.5.0 with JSONRenderer -- see Standard Stack |
| LOG-02 | Every transition logged: job ID, node name, outcome, main retry count, conditional counts | logger.bind(job_id=...) per job, log on every transition |
| LOG-03 | Logs are sufficient for post-hoc agent analysis of workflow correctness | JSON output with all counter state enables grep/jq analysis |
| PS-01 | Source lives at src/workflow_engine/ | Project structure below |
| PS-02 | Pure Python -- no external frameworks (structlog is the one runtime dependency) | Confirmed: stdlib + structlog only |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.3 | Runtime | Already in container, full typing support |
| structlog | 25.5.0 | Structured JSON logging | Explicit requirement (LOG-01), JSON-native, zero-config JSON output |

### Supporting (Dev Only)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.x (latest) | Testing | Nyquist validation, happy-path traversal verification |
| pytest-cov | latest | Coverage | Ensure all 27 nodes are hit |
| ruff | latest | Lint + format | Code quality, fast single-tool replacement for flake8+black |
| mypy | latest | Type checking | Transition table has enough structure that type errors are painful at runtime |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| structlog | stdlib logging | Would need manual JSON formatting, no bound context, more boilerplate |
| structlog | python-json-logger | Less ergonomic context binding, structlog is the explicit project choice |
| dataclasses | Pydantic | No untrusted input to validate, dataclasses are simpler and zero-dep |
| dict transition table | pytransitions | Adds dep, callback model doesn't help with rewind/retry (explicitly rejected in research) |

**Installation:**
```bash
pip install structlog
pip install pytest pytest-cov ruff mypy  # dev only
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  workflow_engine/
    __init__.py
    models.py          # JobState, Outcome enum, NodeType enum, EngineConfig
    transitions.py     # TRANSITION_TABLE dict, HAPPY_PATH ordered list
    nodes.py           # Node ABC, StubWorkNode, StubReviewNode
    engine.py          # Engine class with main loop
    logging.py         # structlog configuration
    __main__.py        # CLI entry point: python -m workflow_engine
tests/
  __init__.py
  conftest.py          # Shared fixtures (engine, config, etc.)
  test_models.py       # JobState, Outcome enum tests
  test_transitions.py  # Transition table integrity tests
  test_engine.py       # Happy-path traversal, multi-job isolation
  test_logging.py      # Structured log output verification
```

### Pattern 1: Outcome-Driven Transition Table
**What:** A dict mapping (node_name, outcome) -> next_node. All routing is a lookup, never procedural.
**When to use:** Always. This is the core data structure the entire engine revolves around.
**Example:**
```python
from enum import Enum, auto
from dataclasses import dataclass, field

class Outcome(Enum):
    SUCCESS = auto()      # Non-review nodes
    FAILURE = auto()      # Non-review nodes
    APPROVE = auto()      # Review nodes
    CONDITIONAL = auto()  # Review nodes
    FAIL = auto()         # Review nodes (distinct from FAILURE)

class NodeType(Enum):
    WORK = auto()
    REVIEW = auto()

# Ordered happy path -- the canonical node sequence
HAPPY_PATH: list[str] = [
    "LocateOgSourceFiles",
    "InventoryOutputs",
    "InventoryDataSources",
    "NoteDependencies",
    "WriteBrd",
    "ReviewBrd",
    "WriteBddTestArch",
    "ReviewBdd",
    "WriteFsd",
    "ReviewFsd",
    "BuildJobArtifacts",
    "ReviewJobArtifacts",
    "BuildProofmarkConfig",
    "ReviewProofmarkConfig",
    "BuildUnitTests",
    "ReviewUnitTests",
    "ExecuteUnitTests",
    "Publish",
    "FBR_BrdCheck",
    "FBR_BddCheck",
    "FBR_FsdCheck",
    "FBR_ArtifactCheck",
    "FBR_ProofmarkCheck",
    "FBR_UnitTestCheck",
    "ExecuteJobRuns",
    "ExecuteProofmark",
    "FinalSignOff",
]

# Phase 1: Only Success/Approve edges populated
# Phase 2 adds Conditional/Fail edges
TRANSITION_TABLE: dict[tuple[str, Outcome], str] = {
    ("LocateOgSourceFiles", Outcome.SUCCESS): "InventoryOutputs",
    ("InventoryOutputs", Outcome.SUCCESS): "InventoryDataSources",
    # ... all 27 happy-path edges
    ("FinalSignOff", Outcome.APPROVE): "COMPLETE",
}

# Node type registry -- which nodes are reviews vs work
NODE_TYPES: dict[str, NodeType] = {
    "LocateOgSourceFiles": NodeType.WORK,
    "ReviewBrd": NodeType.REVIEW,
    # ... etc
}
```

### Pattern 2: JobState with Forward-Compatible Counters
**What:** JobState includes all counter fields from day one, even though Phase 1 only uses current_node.
**When to use:** From the start. Retrofitting counters causes bugs.
**Example:**
```python
@dataclass
class JobState:
    job_id: str
    current_node: str = "LocateOgSourceFiles"
    status: str = "RUNNING"  # RUNNING | COMPLETE | DEAD_LETTER
    main_retry_count: int = 0
    conditional_counts: dict[str, int] = field(default_factory=dict)
    last_rejection_reason: str | None = None
    # Phase 3 will add: fbr_return_pending, triage_context
```

### Pattern 3: Engine Main Loop
**What:** Simple while loop: execute current node, resolve next node, advance state, log.
**When to use:** The engine's run_job method.
**Example:**
```python
class Engine:
    def __init__(self, config: EngineConfig):
        self.config = config
        self.logger = structlog.get_logger()

    def run_job(self, job: JobState) -> JobState:
        log = self.logger.bind(job_id=job.job_id)
        while job.status == "RUNNING":
            node = self.node_registry[job.current_node]
            outcome = node.execute(job)
            next_node = self.resolve_transition(job, outcome)
            log.info("transition",
                     node=job.current_node,
                     outcome=outcome.name,
                     next_node=next_node,
                     main_retry=job.main_retry_count,
                     conditional_counts=job.conditional_counts)
            if next_node == "COMPLETE":
                job.status = "COMPLETE"
            else:
                job.current_node = next_node
        return job

    def resolve_transition(self, job: JobState, outcome: Outcome) -> str:
        key = (job.current_node, outcome)
        if key not in TRANSITION_TABLE:
            raise ValueError(f"No transition for {key}")
        return TRANSITION_TABLE[key]
```

### Pattern 4: structlog Configuration
**What:** Minimal structlog setup for JSON output with bound context.
**Example:**
```python
import structlog

def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),  # DEBUG and above
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

### Anti-Patterns to Avoid
- **Procedural routing:** Never use if/elif chains to decide the next node. Always look up from the transition table. The table IS the spec.
- **Node-aware-of-transitions:** Nodes must not know where they route to. They return an Outcome, period. The engine resolves transitions.
- **Mutable shared state:** Each job gets its own JobState instance. No class-level state, no globals that bleed between jobs.
- **Logging as afterthought:** Log the transition *with full counter state* on every step. This is the primary validation artifact for the entire project.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON logging | Custom JSON formatter | structlog JSONRenderer | Handles serialization edge cases, timestamp formatting, bound context |
| Unique job IDs | Custom counter/UUID logic | `uuid.uuid4()` or `f"job-{i:04d}"` | Sequential IDs are fine for v0.1, uuid4 if you want uniqueness guarantees |
| Enum validation | String comparison for outcomes | Python Enum class | Type safety, exhaustive matching, IDE support |

**Key insight:** Almost everything in this phase IS hand-rolled by design. The whole point is a custom engine with no framework dependencies. The "don't hand-roll" list is intentionally short because structlog is genuinely the only thing worth importing.

## Common Pitfalls

### Pitfall 1: State Bleed Between Jobs
**What goes wrong:** Job 2 inherits leftover state from Job 1 because of shared mutable objects.
**Why it happens:** Default mutable arguments in dataclass fields, or reusing a single JobState instance.
**How to avoid:** Every job creates a fresh JobState with `field(default_factory=dict)` for the conditional_counts dict. Never reuse job instances.
**Warning signs:** Running the same job twice produces different results. Job N+1 starts with non-zero counters.

### Pitfall 2: Transition Table Missing Edges
**What goes wrong:** A node/outcome combo has no entry in the transition table, causing a runtime crash.
**Why it happens:** Forgetting to add edges for all 27 nodes, or mismatching Outcome types (SUCCESS for reviews, APPROVE for work nodes).
**How to avoid:** Build a validation function that checks every node has at least one outbound edge. Use NodeType to enforce correct Outcome types per node.
**Warning signs:** KeyError during engine execution.

### Pitfall 3: Review Nodes Using Wrong Outcome Type
**What goes wrong:** Review stubs return SUCCESS instead of APPROVE, or work stubs return APPROVE instead of SUCCESS.
**Why it happens:** Mixing up the two outcome families.
**How to avoid:** NodeType enum constrains which Outcomes are valid. StubWorkNode returns SUCCESS/FAILURE. StubReviewNode returns APPROVE/CONDITIONAL/FAIL.
**Warning signs:** Transition table lookup misses because the key uses the wrong Outcome variant.

### Pitfall 4: Logging Without Counter State
**What goes wrong:** Logs show transitions but omit counter values, making them useless for Phase 2+ debugging.
**Why it happens:** Phase 1 counters are always zero, so it feels pointless to log them.
**How to avoid:** Log counters from day one. The log format should be stable across phases.
**Warning signs:** Phase 2 adds counters and suddenly the log format changes, breaking any analysis scripts.

### Pitfall 5: Over-Engineering the Node Hierarchy
**What goes wrong:** Building an elaborate node class hierarchy with mixins, decorators, and abstract methods for things that don't exist yet.
**Why it happens:** Anticipating Phase 2/3 complexity and trying to design for it now.
**How to avoid:** Node ABC with one method: `execute(job: JobState) -> Outcome`. Two concrete stubs: StubWorkNode, StubReviewNode. That's it. Phase 2 adds response nodes. Phase 3 adds triage nodes. Don't build them now.
**Warning signs:** More than 3 node classes in Phase 1.

## Code Examples

### Entry Point (__main__.py)
```python
import structlog
from workflow_engine.engine import Engine
from workflow_engine.models import EngineConfig
from workflow_engine.logging import configure_logging

def main():
    configure_logging()
    config = EngineConfig(n_jobs=5, max_main_retries=5, max_conditional=3)
    engine = Engine(config)
    engine.run()

if __name__ == "__main__":
    main()
```

### Expected Log Output
```json
{"event": "transition", "job_id": "job-0001", "node": "LocateOgSourceFiles", "outcome": "SUCCESS", "next_node": "InventoryOutputs", "main_retry": 0, "conditional_counts": {}, "timestamp": "2026-03-13T12:00:00Z", "level": "info"}
{"event": "transition", "job_id": "job-0001", "node": "InventoryOutputs", "outcome": "SUCCESS", "next_node": "InventoryDataSources", "main_retry": 0, "conditional_counts": {}, "timestamp": "2026-03-13T12:00:01Z", "level": "info"}
```

### Transition Table Validation (startup check)
```python
def validate_transition_table() -> list[str]:
    """Check every happy-path node has at least one outbound edge."""
    errors = []
    for node in HAPPY_PATH:
        node_type = NODE_TYPES[node]
        if node_type == NodeType.WORK:
            if (node, Outcome.SUCCESS) not in TRANSITION_TABLE:
                errors.append(f"{node}: missing SUCCESS edge")
        elif node_type == NodeType.REVIEW:
            if (node, Outcome.APPROVE) not in TRANSITION_TABLE:
                errors.append(f"{node}: missing APPROVE edge")
    return errors
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| stdlib logging + JSON formatter | structlog with JSONRenderer | structlog 21.x+ (2021) | Bound context, processor pipeline, zero-config JSON |
| NamedTuple for state | dataclass with field() | Python 3.7+ (2018) | Mutable state, default factories, type hints |
| String-based state names | Enum + string keys hybrid | Convention | Enums for outcomes (finite set), strings for node names (27+ names, enum would be noisy) |

**Deprecated/outdated:**
- structlog < 21.x had different configuration API. Use 25.5.0 patterns.
- `typing.Dict` / `typing.List` -- use `dict` / `list` directly (Python 3.9+)

## Open Questions

1. **RNG seeding for deterministic tests**
   - What we know: HP-03/HP-04 say stubs use RNG for outcomes. Success criteria say happy path should traverse all 27 nodes.
   - What's unclear: Should stubs default to all-success and use RNG only when explicitly configured? Or always RNG with a seed?
   - Recommendation: Default to deterministic (all-success/approve). Add a `seed` parameter to EngineConfig for RNG mode. This way happy-path verification is guaranteed, and Phase 3's validation run can use seeded RNG for coverage.

2. **FinalSignOff node type**
   - What we know: It's the last node before COMPLETE. The transition table lists it with blueprint "signoff".
   - What's unclear: Is it a review node (Approve/Conditional/Fail) or a work node (Success/Failure)?
   - Recommendation: Treat as review node (Approve -> COMPLETE). The name "sign off" implies approval semantics. Phase 2 will need Conditional/Fail edges for it.

3. **Node descriptions for stubs (HP-02)**
   - What we know: Each stub should have "a comment describing what the real agent will do."
   - What's unclear: How detailed? One-liner or paragraph?
   - Recommendation: One-line docstring per stub referencing the blueprint name from the transition table. E.g., `"""Stub for og-locator: Locates original source files for the ETL job."""`

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | none -- Wave 0 creates pyproject.toml with [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v --tb=short` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SM-01 | JobState has current_node, main_retry_count, conditional_counts | unit | `python -m pytest tests/test_models.py::test_job_state_fields -x` | No -- Wave 0 |
| SM-02 | Transition table is a dict, not procedural code | unit | `python -m pytest tests/test_transitions.py::test_table_is_dict -x` | No -- Wave 0 |
| SM-03 | N and M are configurable with defaults | unit | `python -m pytest tests/test_models.py::test_engine_config_defaults -x` | No -- Wave 0 |
| HP-01 | 27 nodes traverse in order to COMPLETE | integration | `python -m pytest tests/test_engine.py::test_happy_path_traversal -x` | No -- Wave 0 |
| HP-02 | Stubs have docstrings describing real agent work | unit | `python -m pytest tests/test_nodes.py::test_stubs_have_descriptions -x` | No -- Wave 0 |
| HP-03 | Non-review stubs can return Success/Failure | unit | `python -m pytest tests/test_nodes.py::test_work_stub_outcomes -x` | No -- Wave 0 |
| HP-04 | Review stubs can return Approve/Conditional/Fail | unit | `python -m pytest tests/test_nodes.py::test_review_stub_outcomes -x` | No -- Wave 0 |
| ENG-01 | Engine loop: pick, resolve, execute, advance, repeat | integration | `python -m pytest tests/test_engine.py::test_engine_loop -x` | No -- Wave 0 |
| ENG-02 | Run N jobs through pipeline | integration | `python -m pytest tests/test_engine.py::test_n_jobs -x` | No -- Wave 0 |
| ENG-03 | In-memory state, no Postgres | unit | `python -m pytest tests/test_models.py::test_job_state_is_dataclass -x` | No -- Wave 0 |
| ENG-04 | Single-threaded sequential execution | integration | `python -m pytest tests/test_engine.py::test_sequential_execution -x` | No -- Wave 0 |
| LOG-01 | Structured JSON via structlog | unit | `python -m pytest tests/test_logging.py::test_json_output -x` | No -- Wave 0 |
| LOG-02 | Every transition logged with full state | integration | `python -m pytest tests/test_engine.py::test_transition_logging -x` | No -- Wave 0 |
| LOG-03 | Logs sufficient for correctness analysis | integration | `python -m pytest tests/test_engine.py::test_log_completeness -x` | No -- Wave 0 |
| PS-01 | Source at src/workflow_engine/ | smoke | `python -c "import workflow_engine"` | No -- Wave 0 |
| PS-02 | Pure Python + structlog only | smoke | `python -m pytest tests/test_models.py -x` (no extra imports) | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pyproject.toml` -- project config with [tool.pytest.ini_options], [tool.ruff], [tool.mypy]
- [ ] `src/workflow_engine/__init__.py` -- package init
- [ ] `tests/__init__.py` -- test package init
- [ ] `tests/conftest.py` -- shared fixtures (default EngineConfig, fresh JobState factory)
- [ ] `tests/test_models.py` -- SM-01, SM-03, ENG-03
- [ ] `tests/test_transitions.py` -- SM-02
- [ ] `tests/test_nodes.py` -- HP-02, HP-03, HP-04
- [ ] `tests/test_engine.py` -- HP-01, ENG-01, ENG-02, ENG-04, LOG-02, LOG-03
- [ ] `tests/test_logging.py` -- LOG-01
- [ ] Framework install: `pip install structlog pytest pytest-cov ruff mypy`

## Sources

### Primary (HIGH confidence)
- Transition table: `/workspace/AtcStrategy/POC6/BDsNotes/state-machine-transitions.md` -- all 27 nodes, node types, happy-path edges
- Project research: `.planning/research/SUMMARY.md` -- stack decisions, architecture, pitfalls
- Requirements: `.planning/REQUIREMENTS.md` -- all 16 Phase 1 requirement IDs
- [structlog official docs](https://www.structlog.org/en/stable/getting-started.html) -- configuration, JSONRenderer, bound loggers
- [structlog PyPI](https://pypi.org/project/structlog/) -- version 25.5.0 confirmed current

### Secondary (MEDIUM confidence)
- [Better Stack structlog guide](https://betterstack.com/community/guides/logging/structlog/) -- usage patterns, processor pipeline examples

### Tertiary (LOW confidence)
- None -- this phase is straightforward enough that primary sources cover everything.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- explicit project constraint (pure Python + structlog), no decisions to make
- Architecture: HIGH -- transition table is the spec, four-component architecture is obvious fit
- Pitfalls: HIGH -- derived from actual transition table mechanics and counter model
- Validation: HIGH -- pytest is standard, test map covers all 16 requirements

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable domain, nothing time-sensitive)
