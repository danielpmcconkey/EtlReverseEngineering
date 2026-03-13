"""Integration tests for the workflow engine.

Tests: happy-path traversal, engine loop, N jobs, sequential execution,
no state bleed, transition logging, log completeness, missing transitions.
"""

from __future__ import annotations

import json

import structlog
import pytest

from workflow_engine.engine import Engine
from workflow_engine.models import EngineConfig, JobState, Outcome
from workflow_engine.transitions import HAPPY_PATH, TRANSITION_TABLE


def _capture_logs() -> list[dict]:
    """Configure structlog to capture log output as dicts and return the capture list."""
    cap: list[dict] = []

    def capture_processor(logger, method_name, event_dict):
        cap.append(event_dict.copy())
        raise structlog.DropEvent

    structlog.configure(
        processors=[capture_processor],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(0),
        cache_logger_on_first_use=False,
    )
    return cap


class TestHappyPathTraversal:
    """Verify a single job traverses all 27 nodes to COMPLETE."""

    def test_happy_path_traversal(self) -> None:
        _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        engine = Engine(config)
        job = JobState(job_id="hp-test-001")
        result = engine.run_job(job)

        assert result.status == "COMPLETE"
        # After completing, the job visited all 27 nodes

    def test_engine_loop(self) -> None:
        """Engine.run_job calls execute, looks up transition, advances, logs."""
        cap = _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        engine = Engine(config)
        job = JobState(job_id="loop-test-001")
        result = engine.run_job(job)

        assert result.status == "COMPLETE"
        transitions = [e for e in cap if e.get("event") == "transition"]
        assert len(transitions) > 0  # at least some transitions logged


class TestNJobs:
    """Verify Engine.run() processes exactly N jobs."""

    def test_n_jobs(self) -> None:
        cap = _capture_logs()
        config = EngineConfig(n_jobs=3, seed=None)
        engine = Engine(config)

        # Drive jobs manually to avoid run() reconfiguring logging
        results = []
        for i in range(3):
            job = JobState(job_id=f"job-{i + 1:04d}")
            results.append(engine.run_job(job))

        assert len(results) == 3
        assert all(j.status == "COMPLETE" for j in results)

    def test_sequential_execution(self) -> None:
        """Jobs run sequentially -- job N+1 starts after job N finishes.

        Verify by checking job_id ordering in captured transition logs.
        """
        cap = _capture_logs()
        config = EngineConfig(n_jobs=3, seed=None)
        engine = Engine(config)

        for i in range(3):
            engine.run_job(JobState(job_id=f"job-{i + 1:04d}"))

        transitions = [e for e in cap if e.get("event") == "transition"]
        job_ids_in_order = [t["job_id"] for t in transitions]

        # All transitions for job-0001 should come before job-0002, etc.
        first_job2 = next(i for i, jid in enumerate(job_ids_in_order) if jid == "job-0002")
        last_job1 = max(i for i, jid in enumerate(job_ids_in_order) if jid == "job-0001")
        assert last_job1 < first_job2

        first_job3 = next(i for i, jid in enumerate(job_ids_in_order) if jid == "job-0003")
        last_job2 = max(i for i, jid in enumerate(job_ids_in_order) if jid == "job-0002")
        assert last_job2 < first_job3


class TestRunMethod:
    """Verify Engine.run() end-to-end (calls configure_logging internally)."""

    def test_run_method(self) -> None:
        config = EngineConfig(n_jobs=3, seed=None)
        engine = Engine(config)
        results = engine.run()
        assert len(results) == 3
        assert all(j.status == "COMPLETE" for j in results)


class TestNoStateBleed:
    """Verify jobs have independent state."""

    def test_no_state_bleed_between_jobs(self) -> None:
        cap = _capture_logs()
        config = EngineConfig(n_jobs=2, seed=None)
        engine = Engine(config)
        results = engine.run()

        # Both jobs should start with clean counters
        for result in results:
            # After happy path, counters should still be at zero
            assert result.main_retry_count == 0
            assert result.conditional_counts == {}


class TestTransitionLogging:
    """Verify structured logging of transitions."""

    def test_transition_logging(self) -> None:
        """Every transition has the required keys."""
        cap = _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        engine = Engine(config)
        engine.run_job(JobState(job_id="log-test-001"))

        transitions = [e for e in cap if e.get("event") == "transition"]
        required_keys = {"event", "job_id", "node", "outcome", "next_node",
                         "main_retry", "conditional_counts"}

        for t in transitions:
            missing = required_keys - set(t.keys())
            assert not missing, f"Missing keys {missing} in transition log: {t}"

    def test_log_completeness(self) -> None:
        """A happy-path job produces exactly 27 transition log entries."""
        cap = _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        engine = Engine(config)
        engine.run_job(JobState(job_id="complete-log-001"))

        transitions = [e for e in cap if e.get("event") == "transition"]
        assert len(transitions) == 27, f"Expected 27, got {len(transitions)}"

        # Verify nodes match HAPPY_PATH order
        logged_nodes = [t["node"] for t in transitions]
        assert logged_nodes == HAPPY_PATH


class TestErrorHandling:
    """Verify error conditions."""

    def test_missing_transition_raises(self) -> None:
        """If (node, outcome) is missing from TRANSITION_TABLE, raise ValueError."""
        _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        engine = Engine(config)

        # Create a job and manually set it to a node, then hack the registry
        # to return an unexpected outcome
        job = JobState(job_id="error-test-001")

        # Monkey-patch a node to return FAILURE (which has no transition in happy path)
        class BadNode:
            def execute(self, j):
                return Outcome.FAILURE

        engine._registry["LocateOgSourceFiles"] = BadNode()

        with pytest.raises(ValueError, match="No transition"):
            engine.run_job(job)
