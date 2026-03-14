"""Transition table and node classification for the workflow state machine.

Provides: TRANSITION_TABLE, HAPPY_PATH, NODE_TYPES, validate_transition_table.
"""

from __future__ import annotations

from workflow_engine.models import NodeType, Outcome

# All 28 happy-path nodes in execution order.
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
    "FBR_BrdCheck",             # 19 - Build
    "FBR_BddCheck",             # 20 - Build
    "FBR_FsdCheck",             # 21 - Build
    "FBR_ArtifactCheck",        # 22 - Build
    "FBR_ProofmarkCheck",       # 23 - Build
    "FBR_UnitTestCheck",        # 24 - Build
    "ExecuteJobRuns",           # 25 - Validate
    "ExecuteProofmark",         # 26 - Validate
    "FinalSignOff",             # 27 - Validate
    "FBR_EvidenceAudit",        # 28 - Validate (terminal gate)
]

# Node type classification: REVIEW for review/gate nodes, WORK for everything else.
_REVIEW_NODES: set[str] = {
    "ReviewBrd",
    "ReviewBdd",
    "ReviewFsd",
    "ReviewJobArtifacts",
    "ReviewProofmarkConfig",
    "ReviewUnitTests",
    "FBR_BrdCheck",
    "FBR_BddCheck",
    "FBR_FsdCheck",
    "FBR_ArtifactCheck",
    "FBR_ProofmarkCheck",
    "FBR_UnitTestCheck",
    "FBR_EvidenceAudit",
    "FinalSignOff",
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

# FBR routing: fbr_gate -> (response_node, rewind_target).
# FBR gates reuse the same response nodes as in-flow review. No new response nodes needed.
FBR_ROUTING: dict[str, tuple[str, str]] = {
    "FBR_BrdCheck":       ("WriteBrdResponse",          "WriteBrd"),
    "FBR_BddCheck":       ("WriteBddResponse",          "WriteBddTestArch"),
    "FBR_FsdCheck":       ("WriteFsdResponse",          "WriteFsd"),
    "FBR_ArtifactCheck":  ("BuildJobArtifactsResponse", "BuildJobArtifacts"),
    "FBR_ProofmarkCheck": ("BuildProofmarkResponse",    "BuildProofmarkConfig"),
    "FBR_UnitTestCheck":  ("BuildUnitTestsResponse",    "BuildUnitTests"),
}

# FBR branching edges: CONDITIONAL -> response, FAIL -> rewind.
# Note: NO (response_node, SUCCESS) edges added here -- they already exist from REVIEW_ROUTING wiring.
# The fbr_return_pending flag (engine.py) handles post-fix routing back to FBR_BrdCheck.
for _fbr_gate, (_response_node, _rewind_target) in FBR_ROUTING.items():
    TRANSITION_TABLE[(_fbr_gate, Outcome.CONDITIONAL)] = _response_node
    TRANSITION_TABLE[(_fbr_gate, Outcome.FAIL)] = _rewind_target

# FBR_EvidenceAudit: terminal gate. APPROVED advances, FAIL/REJECTED → DEAD_LETTER.
# Not in FBR_ROUTING — no response node, no rewind, no retry.
# CONDITIONAL is not a valid outcome for this gate (blueprint enforces APPROVED/REJECTED only).

# Executor failure routing: ExecuteUnitTests and ExecuteJobRuns FAIL → DEAD_LETTER.
# These agents have a built-in 3-attempt leash; if they return FAIL, it's beyond
# autonomous repair. No orchestrator retry.

# Nodes where FAIL immediately triggers DEAD_LETTER (no retry count check).
# Nodes where FAIL immediately triggers DEAD_LETTER (no retry count check).
# FBR_EvidenceAudit is a terminal gate — if traceability is broken, the whole
# RE attempt is suspect. No rewind, no retry. Human triages from the findings.
TERMINAL_FAIL_NODES: set[str] = {
    "FBR_EvidenceAudit",
}

# Triage pipeline: 7-step diagnostic sub-pipeline entered on ExecuteProofmark FAILURE.
TRIAGE_NODES: list[str] = [
    "Triage_ProfileData",       # T1 - context gathering
    "Triage_AnalyzeOgFlow",     # T2 - context gathering
    "Triage_CheckBrd",          # T3 - diagnostic
    "Triage_CheckFsd",          # T4 - diagnostic
    "Triage_CheckCode",         # T5 - diagnostic
    "Triage_CheckProofmark",    # T6 - diagnostic
    "Triage_Route",             # T7 - router (returns TRIAGE_ROUTE, engine handles directly)
]

# All 7 triage nodes are WORK type.
for _triage_node in TRIAGE_NODES:
    NODE_TYPES[_triage_node] = NodeType.WORK

# ExecuteProofmark FAILURE enters triage.
TRANSITION_TABLE[("ExecuteProofmark", Outcome.FAILURE)] = "Triage_ProfileData"

# T1-T6 SUCCESS advance to next triage node.
for _i in range(len(TRIAGE_NODES) - 1):
    TRANSITION_TABLE[(TRIAGE_NODES[_i], Outcome.SUCCESS)] = TRIAGE_NODES[_i + 1]

# Note: Triage_Route has NO TRANSITION_TABLE entry -- engine handles TRIAGE_ROUTE directly.


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
