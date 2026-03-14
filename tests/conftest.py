"""Shared fixtures for workflow engine tests."""

import pytest

from workflow_engine.db import close_pool, ensure_schema, get_pool
from workflow_engine.models import EngineConfig, JobState


@pytest.fixture
def fresh_job_state() -> JobState:
    """Return a fresh JobState with a test job_id."""
    return JobState(job_id="test-job-001")


@pytest.fixture
def default_config() -> EngineConfig:
    """Return an EngineConfig with all defaults."""
    return EngineConfig()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate re_ tables before each test, close pool after."""
    ensure_schema()
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute("TRUNCATE control.re_task_queue RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE control.re_job_state CASCADE")
    yield
    close_pool()
