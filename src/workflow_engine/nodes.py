"""Node abstractions and stub implementations for the workflow engine.

Provides: Node ABC, StubWorkNode, StubReviewNode, create_node_registry.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod

from workflow_engine.models import JobState, NodeType, Outcome
from workflow_engine.transitions import HAPPY_PATH, NODE_TYPES


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


def create_node_registry(rng: random.Random | None = None) -> dict[str, Node]:
    """Create a stub node for every node in HAPPY_PATH.

    Uses NODE_TYPES to pick StubWorkNode vs StubReviewNode.
    When rng is None, all stubs run deterministically (happy path).
    """
    registry: dict[str, Node] = {}
    for node_name in HAPPY_PATH:
        description = _NODE_DESCRIPTIONS[node_name]
        if NODE_TYPES[node_name] == NodeType.REVIEW:
            registry[node_name] = StubReviewNode(node_name, description, rng=rng)
        else:
            registry[node_name] = StubWorkNode(node_name, description, rng=rng)
    return registry
