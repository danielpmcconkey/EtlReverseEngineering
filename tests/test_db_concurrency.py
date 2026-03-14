"""Concurrency tests proving SKIP LOCKED and one-active-per-job constraints.

Uses raw psycopg connections to control transaction boundaries manually.
"""

import psycopg
import psycopg.errors
import pytest

from workflow_engine.db import (
    complete_task,
    enqueue_task,
    get_pool,
)

_CONNINFO = "host=172.18.0.1 port=5432 dbname=atc user=claude password=claude"

_CLAIM_SQL = (
    "SELECT id, job_id, node_name "
    "FROM control.re_task_queue "
    "WHERE status = 'pending' "
    "ORDER BY created_at "
    "FOR UPDATE SKIP LOCKED "
    "LIMIT 1"
)


# -- SKIP LOCKED tests --------------------------------------------------------


class TestSkipLocked:
    def test_double_claim_one_task(self):
        """Two connections claim the same single task — one wins, one gets None."""
        enqueue_task("job-A", "NodeA")

        conn1 = psycopg.connect(_CONNINFO, autocommit=False)
        conn2 = psycopg.connect(_CONNINFO, autocommit=False)
        try:
            row1 = conn1.execute(_CLAIM_SQL).fetchone()
            row2 = conn2.execute(_CLAIM_SQL).fetchone()

            assert row1 is not None, "First claimer should get the task"
            assert row2 is None, "Second claimer should get None (SKIP LOCKED)"
        finally:
            conn1.rollback()
            conn2.rollback()
            conn1.close()
            conn2.close()

    def test_two_claimers_get_different_tasks(self):
        """Three tasks enqueued, two concurrent claimers each get a different one."""
        enqueue_task("job-1", "NodeA")
        enqueue_task("job-2", "NodeB")
        enqueue_task("job-3", "NodeC")

        conn1 = psycopg.connect(_CONNINFO, autocommit=False)
        conn2 = psycopg.connect(_CONNINFO, autocommit=False)
        try:
            row1 = conn1.execute(_CLAIM_SQL).fetchone()
            row2 = conn2.execute(_CLAIM_SQL).fetchone()

            assert row1 is not None
            assert row2 is not None
            assert row1[0] != row2[0], "Claimers must get different task IDs"
            assert row1[1] != row2[1], "Claimers must get different job IDs"
        finally:
            conn1.rollback()
            conn2.rollback()
            conn1.close()
            conn2.close()


# -- One-active-per-job tests --------------------------------------------------


class TestOneActivePerJob:
    def test_pending_blocks_second_enqueue(self):
        """Can't enqueue for a job that already has a pending task."""
        enqueue_task("job-X", "NodeA")
        with pytest.raises(psycopg.errors.UniqueViolation):
            enqueue_task("job-X", "NodeB")

    def test_claimed_blocks_second_enqueue(self):
        """Can't enqueue for a job that has a claimed (in-progress) task."""
        enqueue_task("job-Y", "NodeA")
        # Claim it via raw SQL to set status='claimed'
        pool = get_pool()
        with pool.connection() as conn:
            row = conn.execute(_CLAIM_SQL).fetchone()
            assert row is not None
            conn.execute(
                "UPDATE control.re_task_queue "
                "SET status = 'claimed', claimed_at = now() "
                "WHERE id = %s",
                (row[0],),
            )
        with pytest.raises(psycopg.errors.UniqueViolation):
            enqueue_task("job-Y", "NodeB")

    def test_completed_allows_new_enqueue(self):
        """After a task is completed, a new one for the same job is allowed."""
        task_id = enqueue_task("job-Z", "NodeA")
        # Claim and complete
        pool = get_pool()
        with pool.connection() as conn:
            conn.execute(
                "UPDATE control.re_task_queue "
                "SET status = 'claimed', claimed_at = now() "
                "WHERE id = %s",
                (task_id,),
            )
        complete_task(task_id)
        # Should not raise
        new_id = enqueue_task("job-Z", "NodeB")
        assert new_id > task_id
