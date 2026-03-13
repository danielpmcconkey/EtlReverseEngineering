"""Transition table and node classification for the workflow state machine.

Provides: TRANSITION_TABLE, HAPPY_PATH, NODE_TYPES, validate_transition_table.
"""

from __future__ import annotations

from workflow_engine.models import NodeType, Outcome

# All 27 happy-path nodes in execution order.
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
    "FinalSignOff",
}

NODE_TYPES: dict[str, NodeType] = {
    node: NodeType.REVIEW if node in _REVIEW_NODES else NodeType.WORK
    for node in HAPPY_PATH
}

# Happy-path transition table: (node_name, Outcome) -> next_node.
# WORK nodes transition on SUCCESS, REVIEW nodes on APPROVE.
TRANSITION_TABLE: dict[tuple[str, Outcome], str] = {}

for i, node in enumerate(HAPPY_PATH):
    next_node = HAPPY_PATH[i + 1] if i + 1 < len(HAPPY_PATH) else "COMPLETE"
    outcome = Outcome.APPROVE if NODE_TYPES[node] == NodeType.REVIEW else Outcome.SUCCESS
    TRANSITION_TABLE[(node, outcome)] = next_node


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
