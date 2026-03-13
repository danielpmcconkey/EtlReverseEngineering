"""Node abstractions and stub implementations for the workflow engine.

Provides: Node ABC, StubWorkNode, StubReviewNode, create_node_registry.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod

from workflow_engine.models import JobState, NodeType, Outcome
from workflow_engine.transitions import FBR_ROUTING, HAPPY_PATH, NODE_TYPES, REVIEW_ROUTING, TRIAGE_NODES


class Node(ABC):
    """Abstract base class for all workflow nodes."""

    @abstractmethod
    def execute(self, job: JobState) -> Outcome:
        """Execute this node for the given job, returning an Outcome."""
        ...


class StubWorkNode(Node):
    """Stub for WORK-type nodes. Returns SUCCESS deterministically, or random SUCCESS/FAILURE with RNG."""

    def __init__(self, node_name: str, description: str, *, rng: random.Random | None = None) -> None:
        self.node_name = node_name
        self.__doc__ = description
        self._rng = rng

    def execute(self, job: JobState) -> Outcome:
        if self._rng is None:
            return Outcome.SUCCESS
        return self._rng.choice([Outcome.SUCCESS, Outcome.FAILURE])


class StubReviewNode(Node):
    """Stub for REVIEW-type nodes. Returns APPROVE deterministically, or random APPROVE/CONDITIONAL/FAIL with RNG."""

    def __init__(self, node_name: str, description: str, *, rng: random.Random | None = None) -> None:
        self.node_name = node_name
        self.__doc__ = description
        self._rng = rng

    def execute(self, job: JobState) -> Outcome:
        if self._rng is None:
            return Outcome.APPROVE
        return self._rng.choice([Outcome.APPROVE, Outcome.CONDITIONAL, Outcome.FAIL])


class DiagnosticStubNode(Node):
    """Stub for triage diagnostic nodes (T3-T6). Always returns SUCCESS, stores verdict in job.triage_results."""

    def __init__(self, node_name: str, description: str, *, rng: random.Random | None = None) -> None:
        self.node_name = node_name
        self.__doc__ = description
        self._rng = rng

    def execute(self, job: JobState) -> Outcome:
        if self._rng is None:
            verdict = "clean"
        else:
            verdict = self._rng.choice(["clean", "fault"])
        job.triage_results[self.node_name] = verdict
        return Outcome.SUCCESS


class TriageRouterNode(Node):
    """T7: Reads triage_results, sets triage_rewind_target to earliest fault, returns TRIAGE_ROUTE."""

    # Priority order: T3 (BRD) before T4 (FSD) before T5 (code) before T6 (proofmark).
    FAULT_ROUTING: list[tuple[str, str]] = [
        ("Triage_CheckBrd",       "WriteBrd"),
        ("Triage_CheckFsd",       "WriteFsd"),
        ("Triage_CheckCode",      "BuildJobArtifacts"),
        ("Triage_CheckProofmark", "BuildProofmarkConfig"),
    ]

    def execute(self, job: JobState) -> Outcome:
        for check_node, rewind_target in self.FAULT_ROUTING:
            if job.triage_results.get(check_node) == "fault":
                job.triage_rewind_target = rewind_target
                return Outcome.TRIAGE_ROUTE
        job.triage_rewind_target = "DEAD_LETTER"
        return Outcome.TRIAGE_ROUTE


# Descriptions for each node, referencing stage and blueprint from the transition table.
_NODE_DESCRIPTIONS: dict[str, str] = {
    "LocateOgSourceFiles": "og-locator: Locates original source files for the ETL job",
    "InventoryOutputs": "output-analyst: Inventories all output targets produced by the ETL job",
    "InventoryDataSources": "source-analyst: Inventories all data sources consumed by the ETL job",
    "NoteDependencies": "dependency-analyst: Documents inter-job and external dependencies",
    "WriteBrd": "brd-writer: Writes the Business Requirements Document from plan artifacts",
    "ReviewBrd": "brd-reviewer: Reviews the Business Requirements Document for correctness",
    "WriteBddTestArch": "bdd-writer: Writes BDD test architecture from the approved BRD",
    "ReviewBdd": "bdd-reviewer: Reviews BDD test architecture for completeness and correctness",
    "WriteFsd": "fsd-writer: Writes the Functional Specification Document from BDD and BRD",
    "ReviewFsd": "fsd-reviewer: Reviews the Functional Specification Document for accuracy",
    "BuildJobArtifacts": "builder: Builds job configuration and external module artifacts from the FSD",
    "ReviewJobArtifacts": "artifact-reviewer: Reviews built job artifacts against the FSD",
    "BuildProofmarkConfig": "proofmark-builder: Builds proofmark comparison configuration",
    "ReviewProofmarkConfig": "proofmark-reviewer: Reviews proofmark config for correct match rules",
    "BuildUnitTests": "test-writer: Writes unit tests from BDD test architecture",
    "ReviewUnitTests": "test-reviewer: Reviews unit tests for coverage and correctness",
    "ExecuteUnitTests": "test-executor: Executes the unit test suite and reports results",
    "Publish": "publisher: Publishes built artifacts to the target environment",
    "FBR_BrdCheck": "brd-reviewer: Final build review gate verifying BRD consistency",
    "FBR_BddCheck": "bdd-reviewer: Final build review gate verifying BDD consistency",
    "FBR_FsdCheck": "fsd-reviewer: Final build review gate verifying FSD consistency",
    "FBR_ArtifactCheck": "artifact-reviewer: Final build review gate verifying artifact consistency",
    "FBR_ProofmarkCheck": "proofmark-reviewer: Final build review gate verifying proofmark config",
    "FBR_UnitTestCheck": "test-reviewer: Final build review gate verifying unit test coverage",
    "ExecuteJobRuns": "job-executor: Executes the ETL job against real data",
    "ExecuteProofmark": "proofmark-executor: Runs proofmark comparison against job output",
    "FinalSignOff": "signoff: Final human-equivalent sign-off on the completed job",
}


# Response node descriptions (WORK type -- write/build, never review).
_RESPONSE_NODE_DESCRIPTIONS: dict[str, str] = {
    "WriteBrdResponse":          "brd-writer: Revises BRD based on reviewer feedback",
    "WriteBddResponse":          "bdd-writer: Revises BDD test architecture based on reviewer feedback",
    "WriteFsdResponse":          "fsd-writer: Revises FSD based on reviewer feedback",
    "BuildJobArtifactsResponse": "builder: Revises job artifacts based on reviewer feedback",
    "BuildProofmarkResponse":    "proofmark-builder: Revises proofmark config based on reviewer feedback",
    "BuildUnitTestsResponse":    "test-writer: Revises unit tests based on reviewer feedback",
}


def create_node_registry(rng: random.Random | None = None) -> dict[str, Node]:
    """Create a stub node for every node in HAPPY_PATH plus all response nodes.

    Uses NODE_TYPES to pick StubWorkNode vs StubReviewNode for happy-path nodes.
    Response nodes are always StubWorkNode (they write/build, never review).
    When rng is None, all stubs run deterministically (happy path).
    """
    # WORK nodes that have FAILURE edges (can meaningfully fail with RNG).
    _FAILABLE_WORK_NODES = {"ExecuteProofmark"} | set(_RESPONSE_NODE_DESCRIPTIONS)
    # REVIEW nodes that have CONDITIONAL/FAIL edges (can meaningfully fail with RNG).
    # FinalSignOff is a review node but has no failure edges -- always deterministic.
    _FAILABLE_REVIEW_NODES = set(REVIEW_ROUTING) | set(FBR_ROUTING)

    registry: dict[str, Node] = {}
    for node_name in HAPPY_PATH:
        description = _NODE_DESCRIPTIONS[node_name]
        if NODE_TYPES[node_name] == NodeType.REVIEW and node_name in _FAILABLE_REVIEW_NODES:
            registry[node_name] = StubReviewNode(node_name, description, rng=rng)
        elif NODE_TYPES[node_name] == NodeType.REVIEW:
            registry[node_name] = StubReviewNode(node_name, description)
        elif node_name in _FAILABLE_WORK_NODES:
            registry[node_name] = StubWorkNode(node_name, description, rng=rng)
        else:
            registry[node_name] = StubWorkNode(node_name, description)
    for node_name, description in _RESPONSE_NODE_DESCRIPTIONS.items():
        registry[node_name] = StubWorkNode(node_name, description, rng=rng)

    # Triage pipeline nodes.
    _TRIAGE_DESCRIPTIONS: dict[str, str] = {
        "Triage_ProfileData":    "data-profiler: Profiles failed row data for triage context",
        "Triage_AnalyzeOgFlow":  "og-flow-analyst: Analyzes original data flow for triage context",
        "Triage_CheckBrd":       "triage-brd-checker: Checks BRD against data flow findings",
        "Triage_CheckFsd":       "triage-fsd-checker: Checks FSD against data flow findings",
        "Triage_CheckCode":      "triage-code-checker: Checks code artifacts against data flow findings",
        "Triage_CheckProofmark": "triage-pm-checker: Checks proofmark config against data profile",
        "Triage_Route":          "triage-router: Routes to earliest fault rewind target",
    }
    # T1-T2: context gathering (StubWorkNode, deterministic without RNG)
    for t_node in TRIAGE_NODES[:2]:
        registry[t_node] = StubWorkNode(t_node, _TRIAGE_DESCRIPTIONS[t_node])
    # T3-T6: diagnostic stubs
    for t_node in TRIAGE_NODES[2:6]:
        registry[t_node] = DiagnosticStubNode(t_node, _TRIAGE_DESCRIPTIONS[t_node], rng=rng)
    # T7: router
    registry["Triage_Route"] = TriageRouterNode()
    registry["Triage_Route"].__doc__ = _TRIAGE_DESCRIPTIONS["Triage_Route"]

    return registry
