"""Node abstractions and stub implementations for the workflow engine.

Provides: Node ABC, StubWorkNode, StubReviewNode, create_node_registry,
create_agent_registry.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from pathlib import Path

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
    "FBR_EvidenceAudit": "evidence-auditor: Mechanical verification of all traceability links and citations",
    "ExecuteJobRuns": "job-executor: Executes the ETL job against real data",
    "ExecuteProofmark": "proofmark-executor: Runs proofmark comparison against job output",
    "FinalSignOff": "signoff: Final human-equivalent sign-off on the completed job",
}


_TRIAGE_DESCRIPTIONS: dict[str, str] = {
    "Triage_ProfileData":    "data-profiler: Profiles failed row data for triage context",
    "Triage_AnalyzeOgFlow":  "og-flow-analyst: Analyzes original data flow for triage context",
    "Triage_CheckBrd":       "triage-brd-checker: Checks BRD against data flow findings",
    "Triage_CheckFsd":       "triage-fsd-checker: Checks FSD against data flow findings",
    "Triage_CheckCode":      "triage-code-checker: Checks code artifacts against data flow findings",
    "Triage_CheckProofmark": "triage-pm-checker: Checks proofmark config against data profile",
    "Triage_Route":          "triage-router: Routes to earliest fault rewind target",
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


def _blueprint_name(description: str) -> str:
    """Extract blueprint name from a node description string (e.g., 'og-locator: ...' -> 'og-locator')."""
    return description.split(":")[0].strip()


# Author nodes that get an internal code quality reviewer sub-agent.
# These nodes generate code or config — the sub-agent catches slop before
# the output reaches the dedicated reviewer node downstream.
_AUTHOR_NODES: set[str] = {
    "BuildJobArtifacts",
    "BuildJobArtifactsResponse",
    "BuildProofmarkConfig",
    "BuildProofmarkResponse",
    "BuildUnitTests",
    "BuildUnitTestsResponse",
}

# Sub-agent definition for code quality review within author nodes.
_CODE_REVIEWER_SUB_AGENT: dict[str, dict[str, str]] = {
    "code-reviewer": {
        "description": "Reviews generated code for quality issues",
        "prompt": (
            "You are a Python code quality reviewer. When invoked, review the "
            "code files you are given for:\n"
            "1. PEP 8 compliance and Pythonic idioms\n"
            "2. Type annotations on all functions and parameters\n"
            "3. pathlib instead of os.path\n"
            "4. Context managers for file/connection handling\n"
            "5. No mutable default arguments\n"
            "6. No bare except clauses\n"
            "7. Clean imports (no wildcards, proper ordering)\n"
            "8. No dead code or commented-out blocks\n\n"
            "Respond with a list of specific issues found (file, line, issue) "
            "or confirm the code is clean. Be terse and specific."
        ),
    },
}


# Per-node model assignments. Nodes not listed here fall back to the CLI default.
# Rationale documented in AtcStrategy/POC6/BDsNotes/per-node-model-map.md
MODEL_MAP: dict[str, str] = {
    # Define — spec work, adversarial review
    "WriteBrd":                  "opus",
    "ReviewBrd":                 "opus",
    "WriteBrdResponse":          "opus",
    # Design — spec work, cascading impact
    "WriteBddTestArch":          "opus",
    "ReviewBdd":                 "opus",
    "WriteBddResponse":          "opus",
    "WriteFsd":                  "opus",
    "ReviewFsd":                 "opus",
    "WriteFsdResponse":          "opus",
    # Build — code-vs-spec judgment
    "ReviewJobArtifacts":        "opus",
    # Validate — judgment, Pat
    "FinalSignOff":              "opus",
    "FBR_EvidenceAudit":         "opus",
    # Triage — OG code tracing
    "Triage_AnalyzeOgFlow":      "opus",
    # Mechanical — file copy, queue+poll
    "Publish":                   "haiku",
    "ExecuteProofmark":          "haiku",
}


def create_agent_registry(
    blueprints_dir: Path,
    jobs_dir: Path,
    *,
    model: str = "sonnet",
    etl_start_date: str | None = None,
    etl_end_date: str | None = None,
) -> dict[str, Node]:
    """Create an AgentNode for every node in the workflow.

    Each node maps to a blueprint file at blueprints_dir/{blueprint-name}.md.
    Falls back to TriageRouterNode for Triage_Route (deterministic routing, no agent needed).
    Author nodes (builders/writers) get a code quality reviewer sub-agent.
    """
    from workflow_engine.agent_node import AgentNode

    all_descriptions = {**_NODE_DESCRIPTIONS, **_RESPONSE_NODE_DESCRIPTIONS, **_TRIAGE_DESCRIPTIONS}

    registry: dict[str, Node] = {}
    for node_name, description in all_descriptions.items():
        # Triage_Route stays deterministic — it's pure routing logic, not agent work.
        if node_name == "Triage_Route":
            registry[node_name] = TriageRouterNode()
            registry[node_name].__doc__ = description
            continue

        bp_name = _blueprint_name(description)
        bp_path = blueprints_dir / f"{bp_name}.md"
        sub_agents = _CODE_REVIEWER_SUB_AGENT if node_name in _AUTHOR_NODES else None
        registry[node_name] = AgentNode(
            node_name=node_name,
            blueprint_path=bp_path,
            jobs_dir=jobs_dir,
            model=MODEL_MAP.get(node_name, model),
            sub_agents=sub_agents,
            etl_start_date=etl_start_date,
            etl_end_date=etl_end_date,
        )

    return registry
