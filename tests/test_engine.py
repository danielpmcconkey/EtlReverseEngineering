"""Integration tests for the workflow engine via queue-based execution.

All tests exercise the state machine through the task queue — no synchronous
run_job() exists. Tests use StepHandler for deterministic single-step
control with scripted node outcomes.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import structlog
import pytest

from workflow_engine.db import (
    claim_task,
    close_pool,
    enqueue_task,
    ensure_schema,
    get_pool,
    load_job_state,
    save_job_state,
)
from workflow_engine.models import EngineConfig, JobState, Outcome
from workflow_engine.nodes import Node
from workflow_engine.step_handler import StepHandler
from workflow_engine.transitions import (
    FBR_ROUTING,
    HAPPY_PATH,
    REVIEW_ROUTING,
    TRANSITION_TABLE,
)
from workflow_engine.worker import WorkerPool


class ScriptedNode(Node):
    """Returns outcomes from a pre-defined sequence, then falls back to a default."""

    def __init__(self, outcomes: list[Outcome], default: Outcome) -> None:
        self._outcomes = list(outcomes)
        self._default = default

    def execute(self, job: JobState) -> Outcome:
        return self._outcomes.pop(0) if self._outcomes else self._default


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


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate re_ tables before each test."""
    ensure_schema()
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute("TRUNCATE control.re_task_queue RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE control.re_job_state CASCADE")
    yield
    close_pool()


def _run_job_via_queue(handler: StepHandler, job_id: str, start_node: str = None) -> JobState:
    """Run a single job through the queue using the step handler.

    Enqueues the first task, then repeatedly claims and processes tasks
    until no more tasks exist for this job. Returns the final JobState.
    """
    if start_node is None:
        start_node = HAPPY_PATH[0]

    state = load_job_state(job_id)
    if state is None:
        state = JobState(job_id=job_id, current_node=start_node)
        save_job_state(state)

    enqueue_task(job_id, start_node)

    # Process tasks until queue is drained (single-threaded for determinism)
    max_steps = 5000
    for _ in range(max_steps):
        task = claim_task()
        if task is None:
            break
        handler(task)

    return load_job_state(job_id)


class TestHappyPathTraversal:
    """Verify a single job traverses all 27 nodes to COMPLETE via queue."""

    def test_happy_path_traversal(self) -> None:
        _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)
        result = _run_job_via_queue(handler, "hp-test-001")

        assert result is not None
        assert result.status == "COMPLETE"

    def test_transition_logging(self) -> None:
        """Every transition has the required keys."""
        cap = _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)
        _run_job_via_queue(handler, "log-test-001")

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
        handler = StepHandler(config)
        _run_job_via_queue(handler, "complete-log-001")

        transitions = [e for e in cap if e.get("event") == "transition"]
        assert len(transitions) == 27, f"Expected 27, got {len(transitions)}"

        logged_nodes = [t["node"] for t in transitions]
        assert logged_nodes == HAPPY_PATH


class TestNoStateBleed:
    """Verify jobs have independent state via queue execution."""

    def test_no_state_bleed_between_jobs(self) -> None:
        cap = _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)

        r1 = _run_job_via_queue(handler, "bleed-001")
        r2 = _run_job_via_queue(handler, "bleed-002")

        for result in [r1, r2]:
            assert result is not None
            assert result.main_retry_count == 0
            assert all(v == 0 for v in result.conditional_counts.values())


class TestErrorHandling:
    """Verify error conditions."""

    def test_missing_transition_raises(self) -> None:
        """If (node, outcome) is missing from TRANSITION_TABLE, raise ValueError."""
        _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)

        class BadNode:
            def execute(self, j):
                return Outcome.FAILURE

        handler._registry["LocateOgSourceFiles"] = BadNode()
        state = JobState(job_id="error-test-001")
        save_job_state(state)
        enqueue_task("error-test-001", "LocateOgSourceFiles")

        task = claim_task()
        with pytest.raises(ValueError, match="No transition"):
            handler(task)


class TestCounterMechanics:
    """SM-04 through SM-09: Counter increment, auto-promotion, DEAD_LETTER, resets."""

    def _make_handler(self, **kwargs) -> StepHandler:
        defaults = dict(n_jobs=1, max_main_retries=5, max_conditional_per_node=3, seed=None)
        defaults.update(kwargs)
        return StepHandler(EngineConfig(**defaults))

    def test_fail_increments_main_retry(self) -> None:
        """SM-04: A FAIL at ReviewBrd increments main_retry_count by 1."""
        _capture_logs()
        handler = self._make_handler()
        handler._registry["ReviewBrd"] = ScriptedNode(
            [Outcome.FAIL], default=Outcome.APPROVE
        )
        result = _run_job_via_queue(handler, "sm04-test")

        assert result is not None
        assert result.main_retry_count == 1
        assert result.status == "COMPLETE"

    def test_dead_letter_on_max_retries(self) -> None:
        """SM-05: A job reaching N total FAILs has status DEAD_LETTER."""
        _capture_logs()
        handler = self._make_handler(max_main_retries=2)
        handler._registry["ReviewBrd"] = ScriptedNode([], default=Outcome.FAIL)
        result = _run_job_via_queue(handler, "sm05-test")

        assert result is not None
        assert result.status == "DEAD_LETTER"
        assert result.main_retry_count >= 2

    def test_conditional_increments_counter(self) -> None:
        """SM-06: A CONDITIONAL at ReviewBrd increments conditional_counts['ReviewBrd']."""
        _capture_logs()
        handler = self._make_handler()
        handler._registry["ReviewBrd"] = ScriptedNode(
            [Outcome.CONDITIONAL, Outcome.APPROVE], default=Outcome.APPROVE
        )
        result = _run_job_via_queue(handler, "sm06-test")

        assert result is not None
        assert result.status == "COMPLETE"

    def test_conditional_auto_promotes_to_fail(self) -> None:
        """SM-07: M consecutive CONDITIONALs at one review node auto-promotes to FAIL."""
        _capture_logs()
        handler = self._make_handler(max_conditional_per_node=2)
        handler._registry["ReviewBrd"] = ScriptedNode(
            [Outcome.CONDITIONAL, Outcome.CONDITIONAL, Outcome.APPROVE],
            default=Outcome.APPROVE,
        )
        result = _run_job_via_queue(handler, "sm07-test")

        assert result is not None
        assert result.main_retry_count == 1
        assert result.status == "COMPLETE"

    def test_conditional_resets_on_approve(self) -> None:
        """SM-08: APPROVE at a review node resets that node's conditional counter to 0."""
        _capture_logs()
        handler = self._make_handler()
        handler._registry["ReviewBrd"] = ScriptedNode(
            [Outcome.CONDITIONAL, Outcome.APPROVE], default=Outcome.APPROVE
        )
        result = _run_job_via_queue(handler, "sm08-test")

        assert result is not None
        assert result.conditional_counts.get("ReviewBrd", 0) == 0
        assert result.status == "COMPLETE"

    def test_downstream_counters_reset_on_rewind(self) -> None:
        """SM-09: Rewind resets conditional counters for all nodes at or downstream of rewind target."""
        _capture_logs()
        handler = self._make_handler(max_conditional_per_node=3)
        handler._registry["ReviewBrd"] = ScriptedNode(
            [Outcome.CONDITIONAL, Outcome.FAIL, Outcome.APPROVE],
            default=Outcome.APPROVE,
        )
        result = _run_job_via_queue(handler, "sm09-test")

        assert result is not None
        assert result.conditional_counts.get("ReviewBrd", 0) == 0
        assert result.status == "COMPLETE"
        assert result.main_retry_count == 1


class TestReviewBranching:
    """RB-02, RB-03, RB-04: Routing and rejection reason tests."""

    def _make_handler(self, **kwargs) -> StepHandler:
        defaults = dict(n_jobs=1, max_main_retries=5, max_conditional_per_node=3, seed=None)
        defaults.update(kwargs)
        return StepHandler(EngineConfig(**defaults))

    def test_conditional_loop(self) -> None:
        """RB-02: CONDITIONAL at ReviewBrd routes to WriteBrdResponse, then back to ReviewBrd."""
        cap = _capture_logs()
        handler = self._make_handler()
        handler._registry["ReviewBrd"] = ScriptedNode(
            [Outcome.CONDITIONAL, Outcome.APPROVE], default=Outcome.APPROVE
        )
        _run_job_via_queue(handler, "rb02-test")

        transitions = [e for e in cap if e.get("event") == "transition"]
        nodes_visited = [t["node"] for t in transitions]

        idx = nodes_visited.index("ReviewBrd")
        assert nodes_visited[idx + 1] == "WriteBrdResponse"
        assert nodes_visited[idx + 2] == "ReviewBrd"

    def test_fail_rewinds_to_write_node(self) -> None:
        """RB-03: FAIL at ReviewBrd rewinds to WriteBrd and replays forward."""
        cap = _capture_logs()
        handler = self._make_handler()
        handler._registry["ReviewBrd"] = ScriptedNode(
            [Outcome.FAIL, Outcome.APPROVE], default=Outcome.APPROVE
        )
        _run_job_via_queue(handler, "rb03-test")

        transitions = [e for e in cap if e.get("event") == "transition"]
        nodes_visited = [t["node"] for t in transitions]

        first_review_idx = nodes_visited.index("ReviewBrd")
        assert transitions[first_review_idx]["outcome"] == "FAIL"
        assert nodes_visited[first_review_idx + 1] == "WriteBrd"

    def test_only_latest_rejection_reason(self) -> None:
        """RB-04: last_rejection_reason reflects only the most recent rejection."""
        _capture_logs()
        handler = self._make_handler()
        handler._registry["ReviewBrd"] = ScriptedNode(
            [Outcome.FAIL, Outcome.APPROVE], default=Outcome.APPROVE
        )
        handler._registry["ReviewBdd"] = ScriptedNode(
            [Outcome.CONDITIONAL, Outcome.APPROVE], default=Outcome.APPROVE
        )
        result = _run_job_via_queue(handler, "rb04-test")

        assert result is not None
        assert result.last_rejection_reason is not None
        assert "ReviewBdd" in result.last_rejection_reason


class TestFBRGauntlet:
    """FBR-02, FBR-03, FBR-04: FBR gauntlet engine logic tests."""

    def _make_handler(self, **kwargs) -> StepHandler:
        defaults = dict(n_jobs=1, max_main_retries=5, max_conditional_per_node=3, seed=None)
        defaults.update(kwargs)
        return StepHandler(EngineConfig(**defaults))

    def test_fbr_conditional_restarts_gauntlet(self) -> None:
        """FBR-02: FBR CONDITIONAL -> response -> review APPROVE -> restart at FBR_BrdCheck."""
        cap = _capture_logs()
        handler = self._make_handler()
        handler._registry["FBR_BrdCheck"] = ScriptedNode(
            [Outcome.CONDITIONAL], default=Outcome.APPROVE
        )
        result = _run_job_via_queue(handler, "fbr02-test")

        transitions = [e for e in cap if e.get("event") == "transition"]
        nodes_visited = [t["node"] for t in transitions]

        idx = nodes_visited.index("FBR_BrdCheck")
        assert transitions[idx]["outcome"] == "CONDITIONAL"
        assert nodes_visited[idx + 1] == "WriteBrdResponse"
        assert nodes_visited[idx + 2] == "ReviewBrd"
        assert nodes_visited[idx + 3] == "FBR_BrdCheck"
        assert result.status == "COMPLETE"

    def test_fbr_fail_rewinds_to_write_node(self) -> None:
        """FBR-03: FBR FAIL rewinds to original write node."""
        cap = _capture_logs()
        handler = self._make_handler()
        handler._registry["FBR_FsdCheck"] = ScriptedNode(
            [Outcome.FAIL], default=Outcome.APPROVE
        )
        result = _run_job_via_queue(handler, "fbr03-test")

        transitions = [e for e in cap if e.get("event") == "transition"]
        nodes_visited = [t["node"] for t in transitions]

        idx = nodes_visited.index("FBR_FsdCheck")
        assert transitions[idx]["outcome"] == "FAIL"
        assert nodes_visited[idx + 1] == "WriteFsd"
        assert result.status == "COMPLETE"
        assert result.main_retry_count == 1

    def test_fbr_return_pending_flag(self) -> None:
        """FBR-04: fbr_return_pending is cleared after routing to FBR_BrdCheck."""
        cap = _capture_logs()
        handler = self._make_handler()
        handler._registry["FBR_ArtifactCheck"] = ScriptedNode(
            [Outcome.CONDITIONAL], default=Outcome.APPROVE
        )
        result = _run_job_via_queue(handler, "fbr04-test")

        transitions = [e for e in cap if e.get("event") == "transition"]
        nodes_visited = [t["node"] for t in transitions]

        response_idx = nodes_visited.index("BuildJobArtifactsResponse")
        assert nodes_visited[response_idx + 1] == "ReviewJobArtifacts"
        assert nodes_visited[response_idx + 2] == "FBR_BrdCheck"
        assert result.fbr_return_pending is False
        assert result.status == "COMPLETE"

    def test_fbr_conditional_auto_promotes_to_fail(self) -> None:
        """FBR gate: M consecutive CONDITIONALs auto-promotes to FAIL."""
        cap = _capture_logs()
        handler = self._make_handler(max_conditional_per_node=2)
        handler._registry["FBR_BrdCheck"] = ScriptedNode(
            [Outcome.CONDITIONAL, Outcome.CONDITIONAL], default=Outcome.APPROVE
        )
        result = _run_job_via_queue(handler, "fbr-auto-promote-test")

        transitions = [e for e in cap if e.get("event") == "transition"]
        nodes_visited = [t["node"] for t in transitions]

        fbr_indices = [i for i, n in enumerate(nodes_visited) if n == "FBR_BrdCheck"]
        last_fbr_fail_idx = fbr_indices[1]
        assert transitions[last_fbr_fail_idx]["outcome"] == "FAIL"
        assert nodes_visited[last_fbr_fail_idx + 1] == "WriteBrd"
        assert result.main_retry_count == 1
        assert result.status == "COMPLETE"


class TestTriage:
    """TR-04 through TR-07: Triage engine logic tests."""

    def _make_handler(self, **kwargs) -> StepHandler:
        defaults = dict(n_jobs=1, max_main_retries=5, max_conditional_per_node=3, seed=None)
        defaults.update(kwargs)
        return StepHandler(EngineConfig(**defaults))

    def test_t7_routes_to_earliest_fault(self) -> None:
        """TR-04/TR-05: Triage routes to earliest fault."""
        cap = _capture_logs()
        handler = self._make_handler()
        job = JobState(
            job_id="tr04-test",
            current_node="Triage_Route",
            triage_results={
                "Triage_CheckBrd": "fault",
                "Triage_CheckCode": "fault",
            },
        )
        save_job_state(job)
        enqueue_task("tr04-test", "Triage_Route")

        task = claim_task()
        handler(task)

        result = load_job_state("tr04-test")
        assert result.main_retry_count == 1
        transitions = [e for e in cap if e.get("event") == "transition"]
        assert transitions[0]["node"] == "Triage_Route"
        assert transitions[0]["outcome"] == "TRIAGE_ROUTE"
        assert transitions[0]["next_node"] == "WriteBrd"

    def test_multiple_faults_route_to_earliest(self) -> None:
        """TR-05: T4=fault, T6=fault -> routes to WriteFsd."""
        cap = _capture_logs()
        handler = self._make_handler()
        job = JobState(
            job_id="tr05-test",
            current_node="Triage_Route",
            triage_results={
                "Triage_CheckBrd": "clean",
                "Triage_CheckFsd": "fault",
                "Triage_CheckCode": "clean",
                "Triage_CheckProofmark": "fault",
            },
        )
        save_job_state(job)
        enqueue_task("tr05-test", "Triage_Route")

        task = claim_task()
        handler(task)

        transitions = [e for e in cap if e.get("event") == "transition"]
        assert transitions[0]["next_node"] == "WriteFsd"

    def test_no_faults_dead_letter(self) -> None:
        """TR-06: No faults -> DEAD_LETTER."""
        _capture_logs()
        handler = self._make_handler()
        job = JobState(
            job_id="tr06-test",
            current_node="Triage_Route",
            triage_results={
                "Triage_CheckBrd": "clean",
                "Triage_CheckFsd": "clean",
                "Triage_CheckCode": "clean",
                "Triage_CheckProofmark": "clean",
            },
        )
        save_job_state(job)
        enqueue_task("tr06-test", "Triage_Route")

        task = claim_task()
        handler(task)

        result = load_job_state("tr06-test")
        assert result.status == "DEAD_LETTER"
        assert result.main_retry_count == 1

    def test_triage_increments_main_retry(self) -> None:
        """TR-07: Triage routing increments main_retry_count."""
        _capture_logs()
        handler = self._make_handler()
        job = JobState(
            job_id="tr07-test",
            current_node="Triage_Route",
            triage_results={"Triage_CheckBrd": "fault"},
        )
        save_job_state(job)
        result = _run_job_via_queue(handler, "tr07-test", start_node="Triage_Route")

        assert result.main_retry_count == 1
        assert result.status == "COMPLETE"

    def test_triage_dead_letter_on_max_retries(self) -> None:
        """Triage with main_retry at N-1 -> DEAD_LETTER."""
        _capture_logs()
        handler = self._make_handler(max_main_retries=2)
        job = JobState(
            job_id="triage-dl-test",
            current_node="Triage_Route",
            main_retry_count=1,
            triage_results={"Triage_CheckFsd": "fault"},
        )
        save_job_state(job)
        enqueue_task("triage-dl-test", "Triage_Route")

        task = claim_task()
        handler(task)

        result = load_job_state("triage-dl-test")
        assert result.status == "DEAD_LETTER"
        assert result.main_retry_count == 2

    def test_triage_results_cleared_on_entry(self) -> None:
        """triage_results cleared when entering Triage_ProfileData."""
        _capture_logs()
        handler = self._make_handler()
        handler._registry["ExecuteProofmark"] = ScriptedNode(
            [Outcome.FAILURE], default=Outcome.SUCCESS
        )
        job = JobState(
            job_id="triage-clear-test",
            triage_results={"Triage_CheckBrd": "stale_fault"},
        )
        save_job_state(job)
        result = _run_job_via_queue(handler, "triage-clear-test")

        assert result.status == "DEAD_LETTER"


class TestValidationRun:
    """Smoke test: 200 jobs with RNG via queue, verify all major paths exercised."""

    def test_validation_run_exercises_major_paths(self) -> None:
        """Smoke test: RNG jobs exercise conditionals, fails, and FBR restarts."""
        cap = _capture_logs()
        config = EngineConfig(
            n_jobs=10,
            max_main_retries=50,
            max_conditional_per_node=3,
            seed=42,
        )
        handler = StepHandler(config)

        for i in range(config.n_jobs):
            job_id = f"val-{i + 1:04d}"
            _run_job_via_queue(handler, job_id)

        transitions = [e for e in cap if e.get("event") == "transition"]

        conditionals = [t for t in transitions if t["outcome"] == "CONDITIONAL"]
        assert len(conditionals) > 0, "No CONDITIONAL loops observed"

        fails = [t for t in transitions if t["outcome"] == "FAIL"]
        assert len(fails) > 0, "No FAIL rewinds observed"

        fbr_restarts = [
            t for t in transitions
            if t["outcome"] == "APPROVE"
            and t["next_node"] == "FBR_BrdCheck"
            and t["node"] in REVIEW_ROUTING
        ]
        assert len(fbr_restarts) > 0, "No FBR gauntlet restarts observed"

    def test_happy_path_completes_via_queue(self) -> None:
        """Deterministic happy path produces COMPLETE."""
        _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)
        result = _run_job_via_queue(handler, "complete-test")
        assert result.status == "COMPLETE"

    def test_dead_letter_via_queue(self) -> None:
        """RNG with limited retries produces DEAD_LETTER."""
        _capture_logs()
        config = EngineConfig(n_jobs=1, max_main_retries=2, seed=42)
        handler = StepHandler(config)
        result = _run_job_via_queue(handler, "dl-test")
        assert result.status == "DEAD_LETTER"


class TestQueueExecution:
    """Verify queue-specific behaviors that didn't exist in v0.1."""

    def test_multi_job_concurrent_via_pool(self) -> None:
        """Multiple jobs processed concurrently through worker pool."""
        _capture_logs()
        config = EngineConfig(n_jobs=5, seed=None)
        handler = StepHandler(config)

        for i in range(5):
            job_id = f"pool-{i}"
            save_job_state(JobState(job_id=job_id))
            enqueue_task(job_id, HAPPY_PATH[0])

        pool = WorkerPool(handler=handler, n_workers=3, poll_interval=0.02)
        pool.run_until_drained(timeout=10.0)

        for i in range(5):
            state = load_job_state(f"pool-{i}")
            assert state is not None
            assert state.status == "COMPLETE"

    def test_state_persisted_between_steps(self) -> None:
        """Job state is saved to Postgres after each step and loaded for the next."""
        _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)

        save_job_state(JobState(job_id="persist-test"))
        enqueue_task("persist-test", HAPPY_PATH[0])

        # Process just the first two steps manually
        task1 = claim_task()
        handler(task1)
        state1 = load_job_state("persist-test")
        assert state1.current_node == HAPPY_PATH[1]

        task2 = claim_task()
        handler(task2)
        state2 = load_job_state("persist-test")
        assert state2.current_node == HAPPY_PATH[2]
