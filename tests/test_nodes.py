"""Tests for workflow_engine.nodes (HP-02, HP-03, HP-04)."""

import random

from workflow_engine.models import JobState, Outcome
from workflow_engine.nodes import (
    Node,
    StubReviewNode,
    StubWorkNode,
    create_node_registry,
)
from workflow_engine.transitions import AUTONOMOUS_NODES, HAPPY_PATH, NODE_TYPES


class TestNodeABC:
    def test_node_abc(self) -> None:
        """Node is abstract -- cannot be instantiated directly."""
        try:
            Node()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass


class TestStubWorkNode:
    def test_work_stub_outcomes(self) -> None:
        """StubWorkNode.execute() returns only SUCCESS or FAILURE."""
        rng = random.Random(42)
        stub = StubWorkNode("TestWork", "test work node", rng=rng)
        job = JobState(job_id="test")
        outcomes = {stub.execute(job) for _ in range(50)}
        assert outcomes <= {Outcome.SUCCESS, Outcome.FAILURE}

    def test_deterministic_mode_work(self) -> None:
        """When no RNG, StubWorkNode always returns SUCCESS."""
        stub = StubWorkNode("TestWork", "test work node")
        job = JobState(job_id="test")
        results = [stub.execute(job) for _ in range(10)]
        assert all(r == Outcome.SUCCESS for r in results)


class TestStubReviewNode:
    def test_review_stub_outcomes(self) -> None:
        """StubReviewNode.execute() returns only APPROVE, CONDITIONAL, or FAIL."""
        rng = random.Random(42)
        stub = StubReviewNode("TestReview", "test review node", rng=rng)
        job = JobState(job_id="test")
        outcomes = {stub.execute(job) for _ in range(50)}
        assert outcomes <= {Outcome.APPROVE, Outcome.CONDITIONAL, Outcome.FAIL}

    def test_deterministic_mode_review(self) -> None:
        """When no RNG, StubReviewNode always returns APPROVE."""
        stub = StubReviewNode("TestReview", "test review node")
        job = JobState(job_id="test")
        results = [stub.execute(job) for _ in range(10)]
        assert all(r == Outcome.APPROVE for r in results)


class TestNodeRegistry:
    def test_stubs_have_descriptions(self) -> None:
        """Every stub in the registry has a non-empty docstring."""
        registry = create_node_registry(rng=None)
        for name, node in registry.items():
            assert node.__doc__, f"Node {name} has no docstring"
            assert len(node.__doc__.strip()) > 0, f"Node {name} has empty docstring"

    def test_registry_covers_happy_path(self) -> None:
        """Registry has an entry for every HAPPY_PATH node."""
        registry = create_node_registry(rng=None)
        for node in HAPPY_PATH:
            assert node in registry, f"{node} missing from registry"

    def test_registry_covers_autonomous_nodes(self) -> None:
        """Registry has an entry for every AUTONOMOUS_NODES node."""
        registry = create_node_registry(rng=None)
        for node in AUTONOMOUS_NODES:
            assert node in registry, f"{node} missing from registry"

    def test_rng_mode(self) -> None:
        """When seed is set, stubs produce varied outcomes across multiple calls."""
        rng = random.Random(42)
        registry = create_node_registry(rng=rng)
        job = JobState(job_id="test")
        # Run enough times that RNG should produce variation
        all_outcomes: set[Outcome] = set()
        for node_name, node in registry.items():
            for _ in range(20):
                all_outcomes.add(node.execute(job))
        # Should have more than one unique outcome across all nodes and calls
        assert len(all_outcomes) > 1


_EXPECTED_RESPONSE_NODES = {
    "WriteBrdResponse",
    "WriteBddResponse",
    "WriteFsdResponse",
    "BuildJobArtifactsResponse",
    "BuildProofmarkResponse",
    "BuildUnitTestsResponse",
}


def test_response_nodes_exist() -> None:
    """create_node_registry() returns entries for all 6 response nodes (RB-05)."""
    registry = create_node_registry(rng=None)
    for node_name in _EXPECTED_RESPONSE_NODES:
        assert node_name in registry, f"Response node {node_name} missing from registry"


def test_response_nodes_are_work_type() -> None:
    """All 6 response nodes are StubWorkNode instances, not StubReviewNode."""
    registry = create_node_registry(rng=None)
    for node_name in _EXPECTED_RESPONSE_NODES:
        node = registry[node_name]
        assert isinstance(node, StubWorkNode), (
            f"{node_name} should be StubWorkNode, got {type(node).__name__}"
        )
        assert not isinstance(node, StubReviewNode), (
            f"{node_name} must not be StubReviewNode"
        )


def test_response_nodes_have_descriptions() -> None:
    """All 6 response nodes have non-empty descriptions."""
    registry = create_node_registry(rng=None)
    for node_name in _EXPECTED_RESPONSE_NODES:
        node = registry[node_name]
        assert node.__doc__, f"Response node {node_name} has no docstring"
        assert len(node.__doc__.strip()) > 0, f"Response node {node_name} has empty docstring"


def test_response_nodes_deterministic_returns_success() -> None:
    """In deterministic mode (rng=None), all response nodes return SUCCESS."""
    registry = create_node_registry(rng=None)
    job = JobState(job_id="test")
    for node_name in _EXPECTED_RESPONSE_NODES:
        node = registry[node_name]
        for _ in range(5):
            result = node.execute(job)
            assert result == Outcome.SUCCESS, (
                f"{node_name} should return SUCCESS in deterministic mode, got {result}"
            )


def test_response_nodes_rng_mode_returns_success_or_failure() -> None:
    """In RNG mode, response nodes return only SUCCESS or FAILURE (never APPROVE/CONDITIONAL/FAIL)."""
    rng = random.Random(99)
    registry = create_node_registry(rng=rng)
    job = JobState(job_id="test")
    valid_outcomes = {Outcome.SUCCESS, Outcome.FAILURE}
    for node_name in _EXPECTED_RESPONSE_NODES:
        node = registry[node_name]
        outcomes = {node.execute(job) for _ in range(50)}
        assert outcomes <= valid_outcomes, (
            f"{node_name} returned invalid outcomes: {outcomes - valid_outcomes}"
        )


def test_registry_total_size() -> None:
    """Registry has 22 happy-path + 6 response + 1 autonomous (Triage) = 29 nodes total."""
    registry = create_node_registry(rng=None)
    assert len(registry) == 29, f"Expected 29 nodes, got {len(registry)}"


class TestTriageNode:
    """Tests for the single autonomous Triage node (session 24 redesign)."""

    def test_triage_in_registry(self) -> None:
        """Triage node exists in the registry."""
        registry = create_node_registry(rng=None)
        assert "Triage" in registry

    def test_triage_is_stub_work_node(self) -> None:
        """Triage is a StubWorkNode (returns SUCCESS in stub mode)."""
        registry = create_node_registry(rng=None)
        node = registry["Triage"]
        assert isinstance(node, StubWorkNode)

    def test_triage_deterministic_returns_success(self) -> None:
        """In deterministic mode, Triage returns SUCCESS."""
        registry = create_node_registry(rng=None)
        node = registry["Triage"]
        job = JobState(job_id="triage-test")
        assert node.execute(job) == Outcome.SUCCESS

    def test_old_triage_nodes_not_in_registry(self) -> None:
        """Old T1-T7 nodes are not in the registry."""
        registry = create_node_registry(rng=None)
        old_nodes = [
            "Triage_ProfileData", "Triage_AnalyzeOgFlow",
            "Triage_CheckBrd", "Triage_CheckFsd",
            "Triage_CheckCode", "Triage_CheckProofmark",
            "Triage_Route",
        ]
        for node in old_nodes:
            assert node not in registry, f"Old node {node} still in registry"
