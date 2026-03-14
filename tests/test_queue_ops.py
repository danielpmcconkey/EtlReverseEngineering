"""Tests for queue write paths: enqueue_next and ingest_manifest."""

import json
import tempfile
from pathlib import Path

import pytest

from workflow_engine.db import (
    claim_task,
    close_pool,
    ensure_schema,
    get_pool,
    load_job_state,
)
from workflow_engine.models import Outcome
from workflow_engine.queue_ops import enqueue_next, ingest_manifest
from workflow_engine.transitions import HAPPY_PATH


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


# -- enqueue_next tests -------------------------------------------------------


class TestEnqueueNext:
    def _setup_task(self, job_id: str, node_name: str) -> int:
        """Enqueue and claim a task, return its id."""
        from workflow_engine.db import enqueue_task

        task_id = enqueue_task(job_id, node_name)
        claimed = claim_task()
        assert claimed is not None
        return task_id

    def test_success_enqueues_next_node(self):
        """A work node SUCCESS enqueues the next happy-path node."""
        task_id = self._setup_task("job-1", "LocateOgSourceFiles")
        new_id = enqueue_next(task_id, "job-1", "LocateOgSourceFiles", Outcome.SUCCESS)

        assert new_id is not None
        # The next task should be the second happy-path node
        claimed = claim_task()
        assert claimed is not None
        assert claimed["node_name"] == HAPPY_PATH[1]  # InventoryOutputs
        assert claimed["job_id"] == "job-1"

    def test_approve_enqueues_next_node(self):
        """A review node APPROVE enqueues the next happy-path node."""
        task_id = self._setup_task("job-1", "ReviewBrd")
        new_id = enqueue_next(task_id, "job-1", "ReviewBrd", Outcome.APPROVE)

        assert new_id is not None
        claimed = claim_task()
        assert claimed is not None
        assert claimed["node_name"] == "WriteBddTestArch"

    def test_conditional_enqueues_response_node(self):
        """A review CONDITIONAL enqueues the response node."""
        task_id = self._setup_task("job-1", "ReviewBrd")
        new_id = enqueue_next(task_id, "job-1", "ReviewBrd", Outcome.CONDITIONAL)

        assert new_id is not None
        claimed = claim_task()
        assert claimed is not None
        assert claimed["node_name"] == "WriteBrdResponse"

    def test_fail_enqueues_rewind_target(self):
        """A review FAIL enqueues the rewind target (original write node)."""
        task_id = self._setup_task("job-1", "ReviewBrd")
        new_id = enqueue_next(task_id, "job-1", "ReviewBrd", Outcome.FAIL)

        assert new_id is not None
        claimed = claim_task()
        assert claimed is not None
        assert claimed["node_name"] == "WriteBrd"

    def test_final_signoff_approve_returns_none(self):
        """FinalSignOff APPROVE -> COMPLETE, returns None (no next task)."""
        task_id = self._setup_task("job-1", "FinalSignOff")
        new_id = enqueue_next(task_id, "job-1", "FinalSignOff", Outcome.APPROVE)

        assert new_id is None

    def test_completes_current_task(self):
        """enqueue_next marks the current task as completed."""
        task_id = self._setup_task("job-1", "LocateOgSourceFiles")
        enqueue_next(task_id, "job-1", "LocateOgSourceFiles", Outcome.SUCCESS)

        pool = get_pool()
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT status FROM control.re_task_queue WHERE id = %s",
                (task_id,),
            ).fetchone()
        assert row is not None
        assert row[0] == "completed"

    def test_no_transition_returns_none(self):
        """An outcome with no transition table entry returns None."""
        task_id = self._setup_task("job-1", "Triage_Route")
        # TRIAGE_ROUTE has no TRANSITION_TABLE entry — engine handles it directly
        new_id = enqueue_next(task_id, "job-1", "Triage_Route", Outcome.TRIAGE_ROUTE)
        assert new_id is None

    def test_chain_three_nodes(self):
        """Three consecutive enqueue_next calls produce the right sequence."""
        from workflow_engine.db import enqueue_task

        # Start at node 0
        t0 = enqueue_task("job-1", HAPPY_PATH[0])
        claim_task()  # claim it

        # Complete node 0 -> enqueue node 1
        t1 = enqueue_next(t0, "job-1", HAPPY_PATH[0], Outcome.SUCCESS)
        assert t1 is not None
        c1 = claim_task()
        assert c1 is not None
        assert c1["node_name"] == HAPPY_PATH[1]

        # Complete node 1 -> enqueue node 2
        t2 = enqueue_next(t1, "job-1", HAPPY_PATH[1], Outcome.SUCCESS)
        assert t2 is not None
        c2 = claim_task()
        assert c2 is not None
        assert c2["node_name"] == HAPPY_PATH[2]


# -- ingest_manifest tests ----------------------------------------------------


class TestIngestManifest:
    def _write_manifest(self, jobs: list[dict]) -> Path:
        """Write a temporary manifest file and return its path."""
        manifest = {
            "manifest_version": "1.0",
            "created": "2026-03-14",
            "source": "test",
            "total_jobs": len(jobs),
            "status": "SEALED",
            "jobs": jobs,
        }
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(manifest, tmp)
        tmp.flush()
        return Path(tmp.name)

    def test_enqueues_first_node_for_each_job(self):
        """Each job in the manifest gets the first happy-path node enqueued."""
        path = self._write_manifest([
            {"job_id": 1, "job_name": "JobA", "job_conf_path": "/a.json"},
            {"job_id": 2, "job_name": "JobB", "job_conf_path": "/b.json"},
            {"job_id": 3, "job_name": "JobC", "job_conf_path": "/c.json"},
        ])
        task_ids = ingest_manifest(path)
        assert len(task_ids) == 3

        # All three should be claimable with the first node
        for _ in range(3):
            claimed = claim_task()
            assert claimed is not None
            assert claimed["node_name"] == HAPPY_PATH[0]

        # No more tasks
        assert claim_task() is None

    def test_creates_initial_job_state(self):
        """Each job gets a fresh JobState saved to Postgres."""
        path = self._write_manifest([
            {"job_id": 42, "job_name": "TestJob", "job_conf_path": "/t.json"},
        ])
        ingest_manifest(path)

        state = load_job_state("42")
        assert state is not None
        assert state.job_id == "42"
        assert state.current_node == "LocateOgSourceFiles"
        assert state.status == "RUNNING"
        assert state.main_retry_count == 0

    def test_returns_task_ids(self):
        """Returns a list of task IDs matching the number of jobs."""
        path = self._write_manifest([
            {"job_id": i, "job_name": f"Job{i}", "job_conf_path": f"/{i}.json"}
            for i in range(5)
        ])
        task_ids = ingest_manifest(path)
        assert len(task_ids) == 5
        assert all(isinstance(tid, int) for tid in task_ids)
        # IDs should be sequential
        assert task_ids == sorted(task_ids)

    def test_real_manifest_format(self):
        """Works with the actual manifest format (job_id as int)."""
        path = self._write_manifest([
            {"job_id": 1, "job_name": "CustomerAccountSummary",
             "job_conf_path": "{ETL_ROOT}/JobExecutor/Jobs/customer_account_summary.json"},
        ])
        task_ids = ingest_manifest(path)
        assert len(task_ids) == 1

        state = load_job_state("1")
        assert state is not None
