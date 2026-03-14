"""Postgres storage layer for the task queue and job state.

Provides: get_pool, close_pool, ensure_schema, enqueue_task, claim_task,
complete_task, fail_task, save_job_state, load_job_state.
"""

from __future__ import annotations

import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from typing import Any

from workflow_engine.models import JobState

_pool: ConnectionPool | None = None

_DEFAULT_CONNINFO = "host=172.18.0.1 port=5432 dbname=atc user=claude password=claude"


def get_pool() -> ConnectionPool:
    """Return the module-level connection pool, lazily initializing it."""
    global _pool
    if _pool is None:
        import os

        conninfo = os.environ.get("RE_DATABASE_URL", _DEFAULT_CONNINFO)
        _pool = ConnectionPool(conninfo, min_size=1, max_size=10, open=True)
    return _pool


def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def ensure_schema() -> None:
    """Apply schema.sql to the database (idempotent)."""
    sql = (Path(__file__).parent / "schema.sql").read_text()
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute(sql)


# -- Task queue CRUD ----------------------------------------------------------


def enqueue_task(job_id: str, node_name: str) -> int:
    """Insert a pending task and return its id."""
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO control.re_task_queue (job_id, node_name) "
            "VALUES (%s, %s) RETURNING id",
            (job_id, node_name),
        ).fetchone()
        if row is None:
            raise RuntimeError(
                f"INSERT INTO control.re_task_queue returned no row for job_id={job_id}"
            )
        return row[0]


def claim_task() -> dict[str, Any] | None:
    """Claim the oldest pending task via SKIP LOCKED. Returns dict or None."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, job_id, node_name "
                "FROM control.re_task_queue "
                "WHERE status = 'pending' "
                "ORDER BY created_at "
                "FOR UPDATE SKIP LOCKED "
                "LIMIT 1"
            )
            row = cur.fetchone()
            if row is None:
                return None
            cur.execute(
                "UPDATE control.re_task_queue "
                "SET status = 'claimed', claimed_at = now() "
                "WHERE id = %s",
                (row["id"],),
            )
            return dict(row)


def complete_task(task_id: int) -> None:
    """Mark a task as completed."""
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute(
            "UPDATE control.re_task_queue "
            "SET status = 'completed', completed_at = now() "
            "WHERE id = %s",
            (task_id,),
        )


def fail_task(task_id: int) -> None:
    """Mark a task as failed."""
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute(
            "UPDATE control.re_task_queue "
            "SET status = 'failed', completed_at = now() "
            "WHERE id = %s",
            (task_id,),
        )


# -- Job state CRUD -----------------------------------------------------------


def save_job_state(state: JobState) -> None:
    """Upsert job state to Postgres."""
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO control.re_job_state
                (job_id, current_node, status, main_retry_count,
                 conditional_counts, last_rejection_reason,
                 fbr_return_pending, triage_results, triage_rewind_target,
                 updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (job_id) DO UPDATE SET
                current_node = EXCLUDED.current_node,
                status = EXCLUDED.status,
                main_retry_count = EXCLUDED.main_retry_count,
                conditional_counts = EXCLUDED.conditional_counts,
                last_rejection_reason = EXCLUDED.last_rejection_reason,
                fbr_return_pending = EXCLUDED.fbr_return_pending,
                triage_results = EXCLUDED.triage_results,
                triage_rewind_target = EXCLUDED.triage_rewind_target,
                updated_at = now()
            """,
            (
                state.job_id,
                state.current_node,
                state.status,
                state.main_retry_count,
                json.dumps(state.conditional_counts),
                state.last_rejection_reason,
                state.fbr_return_pending,
                json.dumps(state.triage_results),
                state.triage_rewind_target,
            ),
        )


def load_job_state(job_id: str) -> JobState | None:
    """Load job state from Postgres. Returns None if not found."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM control.re_job_state WHERE job_id = %s",
                (job_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return JobState(
                job_id=row["job_id"],
                current_node=row["current_node"],
                status=row["status"],
                main_retry_count=row["main_retry_count"],
                conditional_counts=row["conditional_counts"],
                last_rejection_reason=row["last_rejection_reason"],
                fbr_return_pending=row["fbr_return_pending"],
                triage_results=row["triage_results"],
                triage_rewind_target=row["triage_rewind_target"],
            )
