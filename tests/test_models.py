"""Tests for workflow_engine.models (SM-01, SM-03, ENG-03)."""

import dataclasses

from workflow_engine.models import EngineConfig, JobState, NodeType, Outcome


class TestJobState:
    def test_job_state_fields(self, fresh_job_state: JobState) -> None:
        assert fresh_job_state.job_id == "test-job-001"
        assert fresh_job_state.current_node == "LocateOgSourceFiles"
        assert fresh_job_state.status == "RUNNING"
        assert fresh_job_state.main_retry_count == 0
        assert fresh_job_state.conditional_counts == {}
        assert fresh_job_state.last_rejection_reason is None

    def test_job_state_is_dataclass(self) -> None:
        assert dataclasses.is_dataclass(JobState)

    def test_no_state_bleed(self) -> None:
        a = JobState(job_id="a")
        b = JobState(job_id="b")
        a.conditional_counts["ReviewBrd"] = 2
        assert b.conditional_counts == {}
        assert a.conditional_counts is not b.conditional_counts


class TestEngineConfig:
    def test_engine_config_defaults(self, default_config: EngineConfig) -> None:
        assert default_config.n_jobs == 5
        assert default_config.max_main_retries == 5
        assert default_config.max_conditional_per_node == 3


class TestOutcome:
    def test_outcome_enum(self) -> None:
        members = list(Outcome)
        assert len(members) == 5
        names = {m.name for m in members}
        assert names == {"SUCCESS", "FAILURE", "APPROVE", "CONDITIONAL", "FAIL"}


class TestJobStateFields:
    def test_fbr_return_pending_default(self) -> None:
        """FBR-01: JobState has fbr_return_pending field, defaults to False."""
        job = JobState(job_id="fbr-field-test")
        assert hasattr(job, "fbr_return_pending")
        assert job.fbr_return_pending is False


class TestNodeType:
    def test_node_type_enum(self) -> None:
        members = list(NodeType)
        assert len(members) == 2
        names = {m.name for m in members}
        assert names == {"WORK", "REVIEW"}
