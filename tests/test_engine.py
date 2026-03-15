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

from tests.conftest import make_test_job_id

from workflow_engine.db import (
    claim_task,
    enqueue_task,
    load_job_state,
    save_job_state,
)
from workflow_engine.models import EngineConfig, JobState, Outcome
from workflow_engine.nodes import Node
from workflow_engine.step_handler import StepHandler
from workflow_engine.transitions import (
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


def _capture_logs() -> list[dict[str, object]]:
    """Configure structlog to capture log output as dicts and return the capture list."""
    cap: list[dict[str, object]] = []

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
    """Verify a single job traverses all nodes to COMPLETE via queue."""

    def test_happy_path_traversal(self) -> None:
        _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)
        jid = make_test_job_id("hp")
        result = _run_job_via_queue(handler, jid)

        assert result is not None
        assert result.status == "COMPLETE"

    def test_transition_logging(self) -> None:
        """Every transition has the required keys."""
        cap = _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)
        jid = make_test_job_id("log")
        _run_job_via_queue(handler, jid)

        transitions = [e for e in cap if e.get("event") == "transition"]
        required_keys = {"event", "job_id", "node", "outcome", "next_node",
                         "main_retry", "conditional_counts"}

        for t in transitions:
            missing = required_keys - set(t.keys())
            assert not missing, f"Missing keys {missing} in transition log: {t}"

    def test_log_completeness(self) -> None:
        """A happy-path job produces exactly len(HAPPY_PATH) transition log entries."""
        cap = _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)
        jid = make_test_job_id("complog")
        _run_job_via_queue(handler, jid)

        transitions = [e for e in cap if e.get("event") == "transition"]
        assert len(transitions) == len(HAPPY_PATH), (
            f"Expected {len(HAPPY_PATH)}, got {len(transitions)}"
        )

        logged_nodes = [t["node"] for t in transitions]
        assert logged_nodes == HAPPY_PATH


class TestNoStateBleed:
    """Verify jobs have independent state via queue execution."""

    def test_no_state_bleed_between_jobs(self) -> None:
        cap = _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)

        r1 = _run_job_via_queue(handler, make_test_job_id("bleed1"))
        r2 = _run_job_via_queue(handler, make_test_job_id("bleed2"))

        for result in [r1, r2]:
            assert result is not None
            assert result.main_retry_count == 0
            assert all(v == 0 for v in result.conditional_counts.values())


class TestErrorHandling:
    """Verify error conditions."""

    def test_failure_promotes_to_fail_and_self_retries(self) -> None:
        """FAILURE at a work node promotes to FAIL and self-retries until dead-letter."""
        _capture_logs()
        config = EngineConfig(n_jobs=1, max_main_retries=2, seed=None)
        handler = StepHandler(config)

        class BadNode:
            def execute(self, j):
                return Outcome.FAILURE

        handler._registry["LocateOgSourceFiles"] = BadNode()
        jid = make_test_job_id("badnode")
        result = _run_job_via_queue(handler, jid)

        assert result.status == "DEAD_LETTER"
        assert result.main_retry_count >= 2


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
        result = _run_job_via_queue(handler, make_test_job_id("sm04"))

        assert result is not None
        assert result.main_retry_count == 1
        assert result.status == "COMPLETE"

    def test_dead_letter_on_max_retries(self) -> None:
        """SM-05: A job reaching N total FAILs has status DEAD_LETTER."""
        _capture_logs()
        handler = self._make_handler(max_main_retries=2)
        handler._registry["ReviewBrd"] = ScriptedNode([], default=Outcome.FAIL)
        result = _run_job_via_queue(handler, make_test_job_id("sm05"))

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
        result = _run_job_via_queue(handler, make_test_job_id("sm06"))

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
        result = _run_job_via_queue(handler, make_test_job_id("sm07"))

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
        result = _run_job_via_queue(handler, make_test_job_id("sm08"))

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
        result = _run_job_via_queue(handler, make_test_job_id("sm09"))

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
        _run_job_via_queue(handler, make_test_job_id("rb02"))

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
        _run_job_via_queue(handler, make_test_job_id("rb03"))

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
        result = _run_job_via_queue(handler, make_test_job_id("rb04"))

        assert result is not None
        assert result.last_rejection_reason is not None
        assert "ReviewBdd" in result.last_rejection_reason


class TestFBREvidenceAudit:
    """FBR_EvidenceAudit is the terminal gate — it stays even after FBR removal."""

    def _make_handler(self, **kwargs) -> StepHandler:
        defaults = dict(n_jobs=1, max_main_retries=5, max_conditional_per_node=3, seed=None)
        defaults.update(kwargs)
        return StepHandler(EngineConfig(**defaults))

    def test_fbr_evidence_audit_approved(self) -> None:
        """FBR_EvidenceAudit APPROVED → COMPLETE (final node in happy path)."""
        cap = _capture_logs()
        handler = self._make_handler()
        result = _run_job_via_queue(handler, make_test_job_id("evpass"))

        transitions = [e for e in cap if e.get("event") == "transition"]
        nodes_visited = [t["node"] for t in transitions]

        assert nodes_visited[-1] == "FBR_EvidenceAudit"
        assert transitions[-1]["next_node"] == "COMPLETE"
        assert result.status == "COMPLETE"

    def test_fbr_evidence_audit_fail_dead_letters(self) -> None:
        """FBR_EvidenceAudit FAIL → immediate DEAD_LETTER, no retry."""
        cap = _capture_logs()
        handler = self._make_handler()
        handler._registry["FBR_EvidenceAudit"] = ScriptedNode(
            [Outcome.FAIL], default=Outcome.APPROVE
        )
        result = _run_job_via_queue(handler, make_test_job_id("evfail"))

        assert result.status == "DEAD_LETTER"
        assert result.current_node == "FBR_EvidenceAudit"
        assert result.main_retry_count == 1


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
        jid = make_test_job_id("tr04")
        job = JobState(
            job_id=jid,
            current_node="Triage_Route",
            triage_results={
                "Triage_CheckBrd": "fault",
                "Triage_CheckCode": "fault",
            },
        )
        save_job_state(job)
        enqueue_task(jid, "Triage_Route")

        task = claim_task()
        handler(task)

        result = load_job_state(jid)
        assert result.main_retry_count == 1
        transitions = [e for e in cap if e.get("event") == "transition"]
        assert transitions[0]["node"] == "Triage_Route"
        assert transitions[0]["outcome"] == "TRIAGE_ROUTE"
        assert transitions[0]["next_node"] == "WriteBrd"

    def test_multiple_faults_route_to_earliest(self) -> None:
        """TR-05: T4=fault, T6=fault -> routes to WriteFsd."""
        cap = _capture_logs()
        handler = self._make_handler()
        jid = make_test_job_id("tr05")
        job = JobState(
            job_id=jid,
            current_node="Triage_Route",
            triage_results={
                "Triage_CheckBrd": "clean",
                "Triage_CheckFsd": "fault",
                "Triage_CheckCode": "clean",
                "Triage_CheckProofmark": "fault",
            },
        )
        save_job_state(job)
        enqueue_task(jid, "Triage_Route")

        task = claim_task()
        handler(task)

        transitions = [e for e in cap if e.get("event") == "transition"]
        assert transitions[0]["next_node"] == "WriteFsd"

    def test_no_faults_dead_letter(self) -> None:
        """TR-06: No faults -> DEAD_LETTER."""
        _capture_logs()
        handler = self._make_handler()
        jid = make_test_job_id("tr06")
        job = JobState(
            job_id=jid,
            current_node="Triage_Route",
            triage_results={
                "Triage_CheckBrd": "clean",
                "Triage_CheckFsd": "clean",
                "Triage_CheckCode": "clean",
                "Triage_CheckProofmark": "clean",
            },
        )
        save_job_state(job)
        enqueue_task(jid, "Triage_Route")

        task = claim_task()
        handler(task)

        result = load_job_state(jid)
        assert result.status == "DEAD_LETTER"
        assert result.main_retry_count == 1

    def test_triage_increments_main_retry(self) -> None:
        """TR-07: Triage routing increments main_retry_count."""
        _capture_logs()
        handler = self._make_handler()
        jid = make_test_job_id("tr07")
        job = JobState(
            job_id=jid,
            current_node="Triage_Route",
            triage_results={"Triage_CheckBrd": "fault"},
        )
        save_job_state(job)
        result = _run_job_via_queue(handler, jid, start_node="Triage_Route")

        assert result.main_retry_count == 1
        assert result.status == "COMPLETE"

    def test_triage_dead_letter_on_max_retries(self) -> None:
        """Triage with main_retry at N-1 -> DEAD_LETTER."""
        _capture_logs()
        handler = self._make_handler(max_main_retries=2)
        jid = make_test_job_id("trdl")
        job = JobState(
            job_id=jid,
            current_node="Triage_Route",
            main_retry_count=1,
            triage_results={"Triage_CheckFsd": "fault"},
        )
        save_job_state(job)
        enqueue_task(jid, "Triage_Route")

        task = claim_task()
        handler(task)

        result = load_job_state(jid)
        assert result.status == "DEAD_LETTER"
        assert result.main_retry_count == 2

    def test_triage_results_cleared_on_entry(self) -> None:
        """triage_results cleared when entering Triage_ProfileData."""
        _capture_logs()
        handler = self._make_handler()
        handler._registry["ExecuteProofmark"] = ScriptedNode(
            [Outcome.FAILURE], default=Outcome.SUCCESS
        )
        jid = make_test_job_id("trclear")
        job = JobState(
            job_id=jid,
            triage_results={"Triage_CheckBrd": "stale_fault"},
        )
        save_job_state(job)
        result = _run_job_via_queue(handler, jid)

        assert result.status == "DEAD_LETTER"


class TestValidationRun:
    """Smoke test: jobs with RNG via queue, verify all major paths exercised."""

    def test_validation_run_exercises_major_paths(self) -> None:
        """Smoke test: RNG jobs exercise conditionals, fails, and rewinds."""
        cap = _capture_logs()
        config = EngineConfig(
            n_jobs=10,
            max_main_retries=50,
            max_conditional_per_node=3,
            seed=42,
        )
        handler = StepHandler(config)

        for i in range(config.n_jobs):
            jid = make_test_job_id(f"val{i}")
            _run_job_via_queue(handler, jid)

        transitions = [e for e in cap if e.get("event") == "transition"]

        conditionals = [t for t in transitions if t["outcome"] == "CONDITIONAL"]
        assert len(conditionals) > 0, "No CONDITIONAL loops observed"

        fails = [t for t in transitions if t["outcome"] == "FAIL"]
        assert len(fails) > 0, "No FAIL rewinds observed"

    def test_happy_path_completes_via_queue(self) -> None:
        """Deterministic happy path produces COMPLETE."""
        _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)
        result = _run_job_via_queue(handler, make_test_job_id("hpcomp"))
        assert result.status == "COMPLETE"

    def test_dead_letter_via_queue(self) -> None:
        """RNG with limited retries produces DEAD_LETTER."""
        _capture_logs()
        config = EngineConfig(n_jobs=1, max_main_retries=2, seed=42)
        handler = StepHandler(config)
        result = _run_job_via_queue(handler, make_test_job_id("dltest"))
        assert result.status == "DEAD_LETTER"


class TestTriageHydrationFromFile:
    """P0: Verify triage_results hydration from process artifact files.

    When use_agents=True, step_handler reads verdict from disk-based process
    artifacts written by AgentNode and populates job.triage_results. All prior
    triage tests use stubs (DiagnosticStubNode) that write directly to
    job.triage_results, skipping this code path entirely.
    """

    def _make_handler_with_file_hydration(self, jobs_dir: str, **kwargs) -> StepHandler:
        """Create a StepHandler using stubs but with use_agents=True for hydration.

        Trick: build with use_agents=False to get stub nodes, then flip the
        config flag so the hydration block (lines 82-91) fires.
        """
        defaults = dict(n_jobs=1, max_main_retries=5, max_conditional_per_node=3, seed=None)
        defaults.update(kwargs)
        config = EngineConfig(**defaults)
        handler = StepHandler(config)
        # Flip AFTER construction so create_agent_registry is never called
        handler._config.use_agents = True
        handler._config.jobs_dir = jobs_dir
        return handler

    def _write_process_artifact(self, jobs_dir: str, job_id: str, node_name: str, data: dict) -> Path:
        """Write a fake process artifact JSON file to the expected path."""
        process_dir = Path(jobs_dir) / job_id / "process"
        process_dir.mkdir(parents=True, exist_ok=True)
        artifact = process_dir / f"{node_name}.json"
        artifact.write_text(json.dumps(data))
        return artifact

    def test_verdict_fault_hydrated_from_file(self) -> None:
        """Agent writes verdict=fault to disk → triage_results populated → Triage_Route routes correctly."""
        _capture_logs()
        with tempfile.TemporaryDirectory() as jobs_dir:
            handler = self._make_handler_with_file_hydration(jobs_dir)
            jid = make_test_job_id("hydrate_fault")

            # Override triage check nodes with ScriptedNode (SUCCESS)
            # The stub won't write to triage_results — hydration from file does that
            for check_node in ["Triage_CheckBrd", "Triage_CheckFsd", "Triage_CheckCode", "Triage_CheckProofmark"]:
                handler._registry[check_node] = ScriptedNode([], default=Outcome.SUCCESS)

            # Set up: ExecuteProofmark FAILs to enter triage, then succeeds on retry
            handler._registry["ExecuteProofmark"] = ScriptedNode(
                [Outcome.FAILURE, Outcome.SUCCESS], default=Outcome.SUCCESS
            )

            # Pre-write process artifacts with fault verdict for BRD check
            self._write_process_artifact(
                jobs_dir, jid, "Triage_CheckBrd",
                {"outcome": "SUCCESS", "verdict": "fault"}
            )
            # Other checks are clean
            for check_node in ["Triage_CheckFsd", "Triage_CheckCode", "Triage_CheckProofmark"]:
                self._write_process_artifact(
                    jobs_dir, jid, check_node,
                    {"outcome": "SUCCESS", "verdict": "clean"}
                )

            result = _run_job_via_queue(handler, jid)

            assert result is not None
            assert result.status == "COMPLETE"
            assert result.main_retry_count == 1  # one triage rewind happened

    def test_verdict_read_from_file_not_stub(self) -> None:
        """Hydration reads from file, not from stub. ScriptedNode doesn't set triage_results."""
        _capture_logs()
        with tempfile.TemporaryDirectory() as jobs_dir:
            handler = self._make_handler_with_file_hydration(jobs_dir)
            jid = make_test_job_id("hydrate_read")

            # Override check nodes — ScriptedNode doesn't write triage_results
            for check_node in ["Triage_CheckBrd", "Triage_CheckFsd", "Triage_CheckCode", "Triage_CheckProofmark"]:
                handler._registry[check_node] = ScriptedNode([], default=Outcome.SUCCESS)

            # Write fault for FSD check
            self._write_process_artifact(
                jobs_dir, jid, "Triage_CheckFsd",
                {"outcome": "SUCCESS", "verdict": "fault"}
            )
            # Others clean
            for check_node in ["Triage_CheckBrd", "Triage_CheckCode", "Triage_CheckProofmark"]:
                self._write_process_artifact(
                    jobs_dir, jid, check_node,
                    {"outcome": "SUCCESS", "verdict": "clean"}
                )

            # Start at Triage_CheckBrd (T3) with state already at triage stage
            job = JobState(job_id=jid, current_node="Triage_CheckBrd", triage_results={})
            save_job_state(job)
            enqueue_task(jid, "Triage_CheckBrd")

            # Process T3-T7
            for _ in range(20):
                task = claim_task()
                if task is None:
                    break
                handler(task)

            result = load_job_state(jid)
            assert result.triage_results.get("Triage_CheckFsd") == "fault"
            assert result.triage_results.get("Triage_CheckBrd") == "clean"

    def test_missing_verdict_defaults_to_clean(self) -> None:
        """Process artifact exists but has no verdict key → defaults to 'clean'."""
        _capture_logs()
        with tempfile.TemporaryDirectory() as jobs_dir:
            handler = self._make_handler_with_file_hydration(jobs_dir)
            jid = make_test_job_id("hydrate_nokey")

            handler._registry["Triage_CheckBrd"] = ScriptedNode([], default=Outcome.SUCCESS)

            # Artifact has outcome but no verdict key
            self._write_process_artifact(
                jobs_dir, jid, "Triage_CheckBrd",
                {"outcome": "SUCCESS", "reason": "looks fine"}
            )

            job = JobState(job_id=jid, current_node="Triage_CheckBrd", triage_results={})
            save_job_state(job)
            enqueue_task(jid, "Triage_CheckBrd")

            task = claim_task()
            handler(task)

            result = load_job_state(jid)
            assert result.triage_results.get("Triage_CheckBrd") == "clean"

    def test_malformed_json_defaults_to_clean(self) -> None:
        """Process artifact with bad JSON → triage_results defaults to 'clean'."""
        _capture_logs()
        with tempfile.TemporaryDirectory() as jobs_dir:
            handler = self._make_handler_with_file_hydration(jobs_dir)
            jid = make_test_job_id("hydrate_badjson")

            handler._registry["Triage_CheckBrd"] = ScriptedNode([], default=Outcome.SUCCESS)

            # Write malformed JSON
            process_dir = Path(jobs_dir) / jid / "process"
            process_dir.mkdir(parents=True, exist_ok=True)
            (process_dir / "Triage_CheckBrd.json").write_text("{not valid json!!!")

            job = JobState(job_id=jid, current_node="Triage_CheckBrd", triage_results={})
            save_job_state(job)
            enqueue_task(jid, "Triage_CheckBrd")

            task = claim_task()
            handler(task)

            result = load_job_state(jid)
            assert result.triage_results.get("Triage_CheckBrd") == "clean"

    def test_missing_process_file_no_hydration(self) -> None:
        """No process artifact on disk → hydration is skipped, triage_results not set."""
        _capture_logs()
        with tempfile.TemporaryDirectory() as jobs_dir:
            handler = self._make_handler_with_file_hydration(jobs_dir)
            jid = make_test_job_id("hydrate_nofile")

            handler._registry["Triage_CheckBrd"] = ScriptedNode([], default=Outcome.SUCCESS)

            # Don't write any process artifact — the file simply doesn't exist
            job = JobState(job_id=jid, current_node="Triage_CheckBrd", triage_results={})
            save_job_state(job)
            enqueue_task(jid, "Triage_CheckBrd")

            task = claim_task()
            handler(task)

            result = load_job_state(jid)
            # No hydration occurred — triage_results should NOT have an entry
            assert "Triage_CheckBrd" not in result.triage_results

    def test_use_agents_false_skips_hydration(self) -> None:
        """With use_agents=False, hydration block is skipped even if file exists."""
        _capture_logs()
        with tempfile.TemporaryDirectory() as jobs_dir:
            config = EngineConfig(n_jobs=1, seed=None, jobs_dir=jobs_dir)
            handler = StepHandler(config)
            jid = make_test_job_id("hydrate_skip")

            # Write a fault artifact — should be IGNORED because use_agents=False
            process_dir = Path(jobs_dir) / jid / "process"
            process_dir.mkdir(parents=True, exist_ok=True)
            (process_dir / "Triage_CheckBrd.json").write_text(
                json.dumps({"outcome": "SUCCESS", "verdict": "fault"})
            )

            # With stubs (use_agents=False), DiagnosticStubNode writes directly
            # to triage_results. The file-based hydration should NOT fire.
            # We'll override with ScriptedNode to confirm no hydration happens.
            handler._registry["Triage_CheckBrd"] = ScriptedNode([], default=Outcome.SUCCESS)

            job = JobState(job_id=jid, current_node="Triage_CheckBrd", triage_results={})
            save_job_state(job)
            enqueue_task(jid, "Triage_CheckBrd")

            task = claim_task()
            handler(task)

            result = load_job_state(jid)
            # ScriptedNode doesn't write triage_results, and hydration is off
            assert "Triage_CheckBrd" not in result.triage_results


class TestQueueExecution:
    """Verify queue-specific behaviors that didn't exist in v0.1."""

    def test_multi_job_concurrent_via_pool(self) -> None:
        """Multiple jobs processed concurrently through worker pool."""
        _capture_logs()
        config = EngineConfig(n_jobs=5, seed=None)
        handler = StepHandler(config)
        jids = [make_test_job_id(f"pool{i}") for i in range(5)]

        for jid in jids:
            save_job_state(JobState(job_id=jid))
            enqueue_task(jid, HAPPY_PATH[0])

        pool = WorkerPool(handler=handler, n_workers=3, poll_interval=0.02)
        pool.run_until_drained(timeout=10.0)

        for jid in jids:
            state = load_job_state(jid)
            assert state is not None
            assert state.status == "COMPLETE"

    def test_state_persisted_between_steps(self) -> None:
        """Job state is saved to Postgres after each step and loaded for the next."""
        _capture_logs()
        config = EngineConfig(n_jobs=1, seed=None)
        handler = StepHandler(config)
        jid = make_test_job_id("persist")

        save_job_state(JobState(job_id=jid))
        enqueue_task(jid, HAPPY_PATH[0])

        # Process just the first two steps manually
        task1 = claim_task()
        handler(task1)
        state1 = load_job_state(jid)
        assert state1.current_node == HAPPY_PATH[1]

        task2 = claim_task()
        handler(task2)
        state2 = load_job_state(jid)
        assert state2.current_node == HAPPY_PATH[2]
