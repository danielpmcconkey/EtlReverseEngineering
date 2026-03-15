"""Shared test fixtures and safety guards for the workflow engine test suite.

Safety contract:
- Tests NEVER truncate or delete production data.
- All test job IDs use the prefix TEST_JOB_ to avoid collisions.
- Cleanup only deletes rows matching TEST_JOB_%.
- A session-scoped guard refuses to run if active tasks exist in the queue.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest

from workflow_engine.models import EngineConfig, JobState

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

_CONNINFO = "host=172.18.0.1 port=5432 dbname=atc user=claude password=claude"

_TEST_JOB_PREFIX = "TEST_JOB_"


def make_test_job_id(label: str = "") -> str:
    """Generate a unique test job ID that will never collide with production data."""
    short_uuid = uuid.uuid4().hex[:8]
    if label:
        return f"{_TEST_JOB_PREFIX}{label}_{short_uuid}"
    return f"{_TEST_JOB_PREFIX}{short_uuid}"


# ---------------------------------------------------------------------------
# Session-scoped safety guard
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Refuse to run if active tasks exist in the queue.

    This prevents tests from stealing production tasks via claim_task().
    """
    try:
        with psycopg.connect(_CONNINFO) as conn:
            row = conn.execute(
                "SELECT count(*) FROM control.re_task_queue "
                "WHERE status IN ('pending', 'claimed')"
            ).fetchone()
            active = row[0] if row else 0
    except Exception as e:
        pytest.exit(f"Cannot connect to database: {e}")

    if active > 0:
        pytest.exit(
            f"SAFETY GUARD: {active} active task(s) in re_task_queue. "
            f"Don't run tests while the engine is running."
        )


# ---------------------------------------------------------------------------
# Session-scoped cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _cleanup_test_data():
    """Delete all TEST_JOB_% rows after the entire test session."""
    yield

    with psycopg.connect(_CONNINFO) as conn:
        # Task queue first (foreign key safe — no FK exists, but order is still good practice)
        conn.execute(
            "DELETE FROM control.re_task_queue WHERE job_id LIKE %s",
            (f"{_TEST_JOB_PREFIX}%",),
        )
        conn.execute(
            "DELETE FROM control.re_job_state WHERE job_id LIKE %s",
            (f"{_TEST_JOB_PREFIX}%",),
        )
        # Reset clutch to disengaged in case a test flipped it
        conn.execute(
            "UPDATE control.re_engine_config SET clutch_engaged = false WHERE id = 1"
        )


# ---------------------------------------------------------------------------
# Per-test cleanup — prevents claim_task() from grabbing stale rows
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _cleanup_test_rows_per_test():
    """Clean up TEST_JOB_ rows before AND after each test.

    Before: ensures claim_task() won't grab stale rows from a prior test.
    After: ensures the next test starts clean.
    """
    with psycopg.connect(_CONNINFO) as conn:
        conn.execute(
            "DELETE FROM control.re_task_queue WHERE job_id LIKE %s",
            (f"{_TEST_JOB_PREFIX}%",),
        )
        conn.execute(
            "DELETE FROM control.re_job_state WHERE job_id LIKE %s",
            (f"{_TEST_JOB_PREFIX}%",),
        )
        conn.execute(
            "UPDATE control.re_engine_config SET clutch_engaged = false WHERE id = 1"
        )
    yield
    with psycopg.connect(_CONNINFO) as conn:
        conn.execute(
            "DELETE FROM control.re_task_queue WHERE job_id LIKE %s",
            (f"{_TEST_JOB_PREFIX}%",),
        )
        conn.execute(
            "DELETE FROM control.re_job_state WHERE job_id LIKE %s",
            (f"{_TEST_JOB_PREFIX}%",),
        )


# ---------------------------------------------------------------------------
# Fixtures for pure-logic tests
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_job_state() -> JobState:
    return JobState(job_id="test-job-001")


@pytest.fixture
def default_config() -> EngineConfig:
    return EngineConfig()
