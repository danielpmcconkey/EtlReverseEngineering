"""Shared fixtures for workflow engine tests."""

import pytest

from workflow_engine.models import EngineConfig, JobState


@pytest.fixture
def fresh_job_state() -> JobState:
    """Return a fresh JobState with a test job_id."""
    return JobState(job_id="test-job-001")


@pytest.fixture
def default_config() -> EngineConfig:
    """Return an EngineConfig with all defaults."""
    return EngineConfig()
