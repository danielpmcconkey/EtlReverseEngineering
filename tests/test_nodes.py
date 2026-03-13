"""Tests for workflow_engine.nodes (HP-02, HP-03, HP-04)."""

import random

from workflow_engine.models import JobState, Outcome
from workflow_engine.nodes import Node, StubReviewNode, StubWorkNode, create_node_registry
from workflow_engine.transitions import HAPPY_PATH, NODE_TYPES


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
