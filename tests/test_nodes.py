"""Tests for workflow_engine.nodes (HP-02, HP-03, HP-04)."""

import random

from workflow_engine.models import JobState, Outcome
from workflow_engine.nodes import (
    DiagnosticStubNode,
    Node,
    StubReviewNode,
    StubWorkNode,
    TriageRouterNode,
    create_node_registry,
)
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


_EXPECTED_RESPONSE_NODES = {
    "WriteBrdResponse",
    "WriteBddResponse",
    "WriteFsdResponse",
    "BuildJobArtifactsResponse",
    "BuildProofmarkResponse",
    "BuildUnitTestsResponse",
}


def test_response_nodes_exist() -> None:
    """create_node_registry() returns entries for all 7 response nodes (RB-05)."""
    registry = create_node_registry(rng=None)
    for node_name in _EXPECTED_RESPONSE_NODES:
        assert node_name in registry, f"Response node {node_name} missing from registry"


def test_response_nodes_are_work_type() -> None:
    """All 7 response nodes are StubWorkNode instances, not StubReviewNode."""
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
    """All 7 response nodes have non-empty descriptions."""
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
    """Registry has 28 happy-path + 6 response + 7 triage = 41 nodes total."""
    registry = create_node_registry(rng=None)
    assert len(registry) == 41, f"Expected 41 nodes, got {len(registry)}"


class TestTriageNodes:
    """Tests for triage node stubs and router (TR-02 through TR-06)."""

    def test_t1_t2_context_gathering(self) -> None:
        """TR-02: T1 and T2 are StubWorkNode instances, return SUCCESS."""
        registry = create_node_registry()
        for name in ("Triage_ProfileData", "Triage_AnalyzeOgFlow"):
            node = registry[name]
            assert isinstance(node, StubWorkNode), f"{name} should be StubWorkNode"
            job = JobState(job_id="t1t2-test")
            assert node.execute(job) == Outcome.SUCCESS

    def test_diagnostic_stubs_record_verdict(self) -> None:
        """TR-03: T3-T6 return SUCCESS but store verdict in job.triage_results."""
        check_nodes = [
            "Triage_CheckBrd", "Triage_CheckFsd",
            "Triage_CheckCode", "Triage_CheckProofmark",
        ]
        registry = create_node_registry()
        for name in check_nodes:
            node = registry[name]
            assert isinstance(node, DiagnosticStubNode), f"{name} should be DiagnosticStubNode"
            job = JobState(job_id="diag-test")
            result = node.execute(job)
            assert result == Outcome.SUCCESS
            assert name in job.triage_results

    def test_diagnostic_stubs_deterministic_clean(self) -> None:
        """Without RNG, T3-T6 store 'clean'."""
        for name in ("Triage_CheckBrd", "Triage_CheckFsd", "Triage_CheckCode", "Triage_CheckProofmark"):
            node = DiagnosticStubNode(name, "test", rng=None)
            job = JobState(job_id="clean-test")
            node.execute(job)
            assert job.triage_results[name] == "clean"

    def test_diagnostic_stubs_rng_varies(self) -> None:
        """With seeded RNG, T3-T6 produce both 'clean' and 'fault' across calls."""
        rng = random.Random(42)
        node = DiagnosticStubNode("Triage_CheckBrd", "test", rng=rng)
        verdicts = set()
        for i in range(20):
            job = JobState(job_id=f"rng-test-{i}")
            node.execute(job)
            verdicts.add(job.triage_results["Triage_CheckBrd"])
        assert verdicts == {"clean", "fault"}, f"Expected both clean and fault, got {verdicts}"

    def test_triage_router_earliest_fault(self) -> None:
        """TR-04: T3=fault, T5=fault -> routes to WriteBrd (earliest)."""
        node = TriageRouterNode()
        job = JobState(job_id="router-test")
        job.triage_results = {
            "Triage_CheckBrd": "fault",
            "Triage_CheckFsd": "clean",
            "Triage_CheckCode": "fault",
            "Triage_CheckProofmark": "clean",
        }
        result = node.execute(job)
        assert result == Outcome.TRIAGE_ROUTE
        assert job.triage_rewind_target == "WriteBrd"

    def test_triage_router_no_faults(self) -> None:
        """TR-06: All clean -> DEAD_LETTER."""
        node = TriageRouterNode()
        job = JobState(job_id="no-fault-test")
        job.triage_results = {
            "Triage_CheckBrd": "clean",
            "Triage_CheckFsd": "clean",
            "Triage_CheckCode": "clean",
            "Triage_CheckProofmark": "clean",
        }
        result = node.execute(job)
        assert result == Outcome.TRIAGE_ROUTE
        assert job.triage_rewind_target == "DEAD_LETTER"

    def test_triage_router_single_fault_t6(self) -> None:
        """Only T6=fault -> routes to BuildProofmarkConfig."""
        node = TriageRouterNode()
        job = JobState(job_id="t6-fault-test")
        job.triage_results = {
            "Triage_CheckBrd": "clean",
            "Triage_CheckFsd": "clean",
            "Triage_CheckCode": "clean",
            "Triage_CheckProofmark": "fault",
        }
        result = node.execute(job)
        assert result == Outcome.TRIAGE_ROUTE
        assert job.triage_rewind_target == "BuildProofmarkConfig"
