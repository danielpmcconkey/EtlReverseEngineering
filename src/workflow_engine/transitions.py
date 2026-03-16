"""Transition table and node classification for the Ogre workflow state machine.

Provides: TRANSITION_TABLE, HAPPY_PATH, NODE_TYPES, validate_transition_table.
"""

from __future__ import annotations

from workflow_engine.models import NodeType, Outcome

# All happy-path nodes in execution order.
HAPPY_PATH: list[str] = [
    "LocateOgSourceFiles",      # 1  - Plan
    "InventoryOutputs",         # 2  - Plan
    "InventoryDataSources",     # 3  - Plan
    "NoteDependencies",         # 4  - Plan
    "WriteBrd",                 # 5  - Define
    "ReviewBrd",                # 6  - Define
    "WriteBddTestArch",         # 7  - Design
    "ReviewBdd",                # 8  - Design
    "WriteFsd",                 # 9  - Design
    "ReviewFsd",                # 10 - Design
    "BuildJobArtifacts",        # 11 - Build
    "ReviewJobArtifacts",       # 12 - Build
    "BuildProofmarkConfig",     # 13 - Build
    "ReviewProofmarkConfig",    # 14 - Build
    "BuildUnitTests",           # 15 - Build
    "ReviewUnitTests",          # 16 - Build
    "ExecuteUnitTests",         # 17 - Build
    "Publish",                  # 18 - Build
    "ExecuteJobRuns",           # 19 - Validate
    "ExecuteProofmark",         # 20 - Validate
    "FBR_EvidenceAudit",        # 21 - Validate (terminal gate)
]

# Node type classification: REVIEW for review/gate nodes, WORK for everything else.
_REVIEW_NODES: set[str] = {
    "ReviewBrd",
    "ReviewBdd",
    "ReviewFsd",
    "ReviewJobArtifacts",
    "ReviewProofmarkConfig",
    "ReviewUnitTests",
    "FBR_EvidenceAudit",
}

# Review routing: review_node -> (response_node, rewind_target).
# Used to expand TRANSITION_TABLE with Conditional/Fail/response-SUCCESS edges.
REVIEW_ROUTING: dict[str, tuple[str, str]] = {
    "ReviewBrd":             ("WriteBrdResponse",          "WriteBrd"),
    "ReviewBdd":             ("WriteBddResponse",          "WriteBddTestArch"),
    "ReviewFsd":             ("WriteFsdResponse",          "WriteFsd"),
    "ReviewJobArtifacts":    ("BuildJobArtifactsResponse", "BuildJobArtifacts"),
    "ReviewProofmarkConfig": ("BuildProofmarkResponse",    "BuildProofmarkConfig"),
    "ReviewUnitTests":       ("BuildUnitTestsResponse",    "BuildUnitTests"),
}

# All response node names (NodeType.WORK -- they write/build, not review).
_RESPONSE_NODES: set[str] = {response for response, _ in REVIEW_ROUTING.values()}

NODE_TYPES: dict[str, NodeType] = {
    node: NodeType.REVIEW if node in _REVIEW_NODES else NodeType.WORK
    for node in HAPPY_PATH
}
# Response nodes are WORK type (not in HAPPY_PATH, so must be added separately).
for _response_node in _RESPONSE_NODES:
    NODE_TYPES[_response_node] = NodeType.WORK

# Happy-path transition table: (node_name, Outcome) -> next_node.
# WORK nodes transition on SUCCESS, REVIEW nodes on APPROVE.
TRANSITION_TABLE: dict[tuple[str, Outcome], str] = {}

for i, node in enumerate(HAPPY_PATH):
    next_node = HAPPY_PATH[i + 1] if i + 1 < len(HAPPY_PATH) else "COMPLETE"
    outcome = Outcome.APPROVE if NODE_TYPES[node] == NodeType.REVIEW else Outcome.SUCCESS
    TRANSITION_TABLE[(node, outcome)] = next_node

# Review branching edges: CONDITIONAL -> response, FAIL -> rewind, response SUCCESS -> reviewer.
for _review_node, (_response_node, _rewind_target) in REVIEW_ROUTING.items():
    TRANSITION_TABLE[(_review_node, Outcome.CONDITIONAL)] = _response_node
    TRANSITION_TABLE[(_review_node, Outcome.FAIL)] = _rewind_target
    TRANSITION_TABLE[(_response_node, Outcome.SUCCESS)] = _review_node

# Response node FAILURE edges: (response_node, FAILURE) -> rewind_target.
# Deferred from Phase 2 -- a response node that fails routes to the same rewind target
# as the paired review node's FAIL edge.
for _review_node, (_response_node, _rewind_target) in REVIEW_ROUTING.items():
    TRANSITION_TABLE[(_response_node, Outcome.FAILURE)] = _rewind_target

# FBR routing removed in session 22. FBR gates (19-24) cut from the happy path.
# See AtcStrategy/POC6/BDsNotes/session22-fbr-removal.md for rationale.
# FBR_EvidenceAudit (terminal gate) is NOT routed through FBR_ROUTING — it stays.
FBR_ROUTING: dict[str, tuple[str, str]] = {}

# FBR_EvidenceAudit: APPROVED → COMPLETE, REJECTED → DEAD_LETTER.
# CONDITIONAL → PatFix: Pat identified fixable documentation/test drift.
# PatFix updates FSD, syncs artifacts, rebuilds & runs UTs. On SUCCESS → COMPLETE
# (no re-review — Pat's conditions are specific and mechanical).
# PatFix FAIL → DEAD_LETTER (if Pat's conditions can't be resolved, it's a human problem).
TRANSITION_TABLE[("FBR_EvidenceAudit", Outcome.CONDITIONAL)] = "PatFix"
TRANSITION_TABLE[("PatFix", Outcome.SUCCESS)] = "COMPLETE"
NODE_TYPES["PatFix"] = NodeType.WORK

# Nodes where FAIL immediately triggers DEAD_LETTER (no retry count check).
# FBR_EvidenceAudit is a terminal gate — if traceability is broken, the whole
# RE attempt is suspect. No rewind, no retry. Human triages from the findings.
TERMINAL_FAIL_NODES: set[str] = {
    "FBR_EvidenceAudit",
    "PatFix",
}

# Triage: single autonomous node. Replaces the old 7-node diagnostic pipeline (T1-T7).
# The triage orchestrator manages its own sub-agents (RCA, Fix, Reset) and directly
# manipulates job state in the database. The engine fires it and walks away.
# See AtcStrategy/POC6/BDsNotes/ for the redesign rationale (session 24).
AUTONOMOUS_NODES: set[str] = {"Triage"}
NODE_TYPES["Triage"] = NodeType.WORK

# ExecuteProofmark FAILURE enters triage.
TRANSITION_TABLE[("ExecuteProofmark", Outcome.FAILURE)] = "Triage"

# Work-node self-retry on FAIL: any WORK node (happy-path or response) that
# doesn't already have a (node, FAIL) edge gets a self-retry transition.
# TERMINAL_FAIL_NODES and AUTONOMOUS_NODES are excluded.
_ALL_WORK_NODES = (
    [n for n in HAPPY_PATH if NODE_TYPES[n] == NodeType.WORK]
    + list(_RESPONSE_NODES)
)
for _work_node in _ALL_WORK_NODES:
    if _work_node in TERMINAL_FAIL_NODES:
        continue
    if (_work_node, Outcome.FAIL) not in TRANSITION_TABLE:
        TRANSITION_TABLE[(_work_node, Outcome.FAIL)] = _work_node


def validate_transition_table() -> list[str]:
    """Check that every HAPPY_PATH node has the correct outbound edge.

    Returns a list of error strings. Empty list means valid.
    """
    errors: list[str] = []
    for node in HAPPY_PATH:
        expected_outcome = (
            Outcome.APPROVE if NODE_TYPES[node] == NodeType.REVIEW else Outcome.SUCCESS
        )
        if (node, expected_outcome) not in TRANSITION_TABLE:
            errors.append(
                f"{node} missing ({node}, {expected_outcome.name}) edge"
            )
    return errors
