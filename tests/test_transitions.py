"""Tests for workflow_engine.transitions (SM-02, RB-01, RB-02, RB-03)."""

from workflow_engine.models import NodeType, Outcome
from workflow_engine.transitions import HAPPY_PATH, NODE_TYPES, REVIEW_ROUTING, TRANSITION_TABLE, validate_transition_table


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


_EXPECTED_REVIEW_ROUTING_KEYS = {
    "ReviewBrd",
    "ReviewBdd",
    "ReviewFsd",
    "ReviewJobArtifacts",
    "ReviewProofmarkConfig",
    "ReviewUnitTests",
}


class TestReviewRouting:
    """Tests for REVIEW_ROUTING dict and expanded TRANSITION_TABLE (RB-01, RB-02, RB-03)."""

    def test_review_routing_has_exactly_6_entries(self) -> None:
        assert len(REVIEW_ROUTING) == 6

    def test_review_routing_has_correct_keys(self) -> None:
        assert set(REVIEW_ROUTING.keys()) == _EXPECTED_REVIEW_ROUTING_KEYS

    def test_review_routing_values_are_tuples_of_two_strings(self) -> None:
        for review_node, value in REVIEW_ROUTING.items():
            assert isinstance(value, tuple), f"{review_node} value is not a tuple"
            assert len(value) == 2, f"{review_node} value is not length 2"
            response_node, rewind_target = value
            assert isinstance(response_node, str) and response_node
            assert isinstance(rewind_target, str) and rewind_target

    def test_review_routing_exact_mapping(self) -> None:
        """Exact response_node and rewind_target values per spec."""
        assert REVIEW_ROUTING["ReviewBrd"] == ("WriteBrdResponse", "WriteBrd")
        assert REVIEW_ROUTING["ReviewBdd"] == ("WriteBddResponse", "WriteBddTestArch")
        assert REVIEW_ROUTING["ReviewFsd"] == ("WriteFsdResponse", "WriteFsd")
        assert REVIEW_ROUTING["ReviewJobArtifacts"] == ("BuildJobArtifactsResponse", "BuildJobArtifacts")
        assert REVIEW_ROUTING["ReviewProofmarkConfig"] == ("BuildProofmarkResponse", "BuildProofmarkConfig")
        assert REVIEW_ROUTING["ReviewUnitTests"] == ("BuildUnitTestsResponse", "BuildUnitTests")

    def test_conditional_edges_in_transition_table(self) -> None:
        """Each review node has (node, CONDITIONAL) -> response_node."""
        for review_node, (response_node, _) in REVIEW_ROUTING.items():
            key = (review_node, Outcome.CONDITIONAL)
            assert key in TRANSITION_TABLE, f"Missing CONDITIONAL edge for {review_node}"
            assert TRANSITION_TABLE[key] == response_node, (
                f"CONDITIONAL edge for {review_node} points to wrong node"
            )

    def test_fail_edges_in_transition_table(self) -> None:
        """Each review node has (node, FAIL) -> rewind_target."""
        for review_node, (_, rewind_target) in REVIEW_ROUTING.items():
            key = (review_node, Outcome.FAIL)
            assert key in TRANSITION_TABLE, f"Missing FAIL edge for {review_node}"
            assert TRANSITION_TABLE[key] == rewind_target, (
                f"FAIL edge for {review_node} points to wrong node"
            )

    def test_fail_rewind_targets_are_original_write_nodes(self) -> None:
        """Rewind targets are the original write/build nodes, not response nodes."""
        expected_rewind_targets = {
            "ReviewBrd": "WriteBrd",
            "ReviewBdd": "WriteBddTestArch",
            "ReviewFsd": "WriteFsd",
            "ReviewJobArtifacts": "BuildJobArtifacts",
            "ReviewProofmarkConfig": "BuildProofmarkConfig",
            "ReviewUnitTests": "BuildUnitTests",
        }
        for review_node, expected_target in expected_rewind_targets.items():
            _, rewind_target = REVIEW_ROUTING[review_node]
            assert rewind_target == expected_target, (
                f"Rewind target for {review_node} should be {expected_target}, got {rewind_target}"
            )

    def test_response_success_edges_in_transition_table(self) -> None:
        """Each response node has (response_node, SUCCESS) -> review_node."""
        for review_node, (response_node, _) in REVIEW_ROUTING.items():
            key = (response_node, Outcome.SUCCESS)
            assert key in TRANSITION_TABLE, f"Missing SUCCESS edge for response node {response_node}"
            assert TRANSITION_TABLE[key] == review_node, (
                f"SUCCESS edge for {response_node} should route back to {review_node}"
            )

    def test_approve_edges_still_work(self) -> None:
        """Existing APPROVE edges are not removed (RB-01 regression check)."""
        for review_node in _EXPECTED_REVIEW_ROUTING_KEYS:
            key = (review_node, Outcome.APPROVE)
            assert key in TRANSITION_TABLE, f"APPROVE edge missing for {review_node} (regression)"

    def test_response_nodes_classified_as_work_in_node_types(self) -> None:
        """All 6 response nodes (in REVIEW_ROUTING) are NodeType.WORK in NODE_TYPES."""
        for _, (response_node, _) in REVIEW_ROUTING.items():
            assert response_node in NODE_TYPES, f"{response_node} not in NODE_TYPES"
            assert NODE_TYPES[response_node] == NodeType.WORK, (
                f"{response_node} should be NodeType.WORK"
            )

    def test_transition_table_total_edge_count(self) -> None:
        """TRANSITION_TABLE has 27 happy-path edges + 18 review branching edges = 45 minimum.

        27 happy-path (WORK SUCCESS + REVIEW APPROVE)
        + 6 CONDITIONAL edges + 6 FAIL edges + 6 response SUCCESS edges = 45
        Plus optional TriageProofmarkFailures -> 46 max.
        """
        assert len(TRANSITION_TABLE) >= 45

    def test_validate_transition_table_still_passes(self) -> None:
        """validate_transition_table() must still return empty list (no regression)."""
        errors = validate_transition_table()
        assert errors == [], f"validate_transition_table() returned errors: {errors}"
