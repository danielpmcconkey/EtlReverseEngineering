"""Core data models for the workflow engine.

Provides: JobState, Outcome, NodeType, EngineConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class Outcome(Enum):
    """Possible outcomes from node execution."""

    SUCCESS = auto()
    FAILURE = auto()
    APPROVE = auto()
    CONDITIONAL = auto()
    FAIL = auto()
    TRIAGE_ROUTE = auto()


class NodeType(Enum):
    """Classification of nodes in the workflow."""

    WORK = auto()
    REVIEW = auto()


@dataclass
class JobState:
    """Mutable state for a single job traversing the workflow.

    Tracks position, retry counters, and last rejection reason.
    """

    job_id: str
    current_node: str = "LocateOgSourceFiles"
    status: str = "RUNNING"
    main_retry_count: int = 0
    conditional_counts: dict[str, int] = field(default_factory=dict)
    last_rejection_reason: str | None = None
    fbr_return_pending: bool = False
    triage_results: dict[str, str] = field(default_factory=dict)
    triage_rewind_target: str | None = None


@dataclass
class EngineConfig:
    """Configuration for the workflow engine.

    Controls concurrency, retry limits, RNG seeding, and agent invocation.
    """

    n_jobs: int = 5
    max_main_retries: int = 5
    max_conditional_per_node: int = 3
    seed: int | None = None
    use_agents: bool = False
    agent_model: str = "sonnet"
    agent_budget: float = 0.50
    blueprints_dir: str = ""
    jobs_dir: str = ""
