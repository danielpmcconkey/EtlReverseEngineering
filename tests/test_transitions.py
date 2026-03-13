"""Tests for workflow_engine.transitions (SM-02)."""

from workflow_engine.models import NodeType, Outcome
from workflow_engine.transitions import HAPPY_PATH, NODE_TYPES, TRANSITION_TABLE


class TestTransitionTable:
    def test_table_is_dict(self) -> None:
        assert isinstance(TRANSITION_TABLE, dict)

    def test_happy_path_has_27_nodes(self) -> None:
        assert len(HAPPY_PATH) == 27

    def test_happy_path_order(self) -> None:
        assert HAPPY_PATH[0] == "LocateOgSourceFiles"
        assert HAPPY_PATH[-1] == "FinalSignOff"

    def test_every_happy_path_node_has_outbound_edge(self) -> None:
        for node in HAPPY_PATH:
            keys = [k for k in TRANSITION_TABLE if k[0] == node]
            assert len(keys) >= 1, f"{node} has no outbound edge in TRANSITION_TABLE"

    def test_node_types_cover_all_nodes(self) -> None:
        for node in HAPPY_PATH:
            assert node in NODE_TYPES, f"{node} missing from NODE_TYPES"

    def test_work_nodes_use_success(self) -> None:
        work_nodes = [n for n in HAPPY_PATH if NODE_TYPES[n] == NodeType.WORK]
        for node in work_nodes:
            assert (node, Outcome.SUCCESS) in TRANSITION_TABLE, (
                f"WORK node {node} missing (node, SUCCESS) edge"
            )

    def test_review_nodes_use_approve(self) -> None:
        review_nodes = [n for n in HAPPY_PATH if NODE_TYPES[n] == NodeType.REVIEW]
        for node in review_nodes:
            assert (node, Outcome.APPROVE) in TRANSITION_TABLE, (
                f"REVIEW node {node} missing (node, APPROVE) edge"
            )
