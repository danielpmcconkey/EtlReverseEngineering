"""Tests for queue write paths: ingest_manifest."""

import json
import tempfile
from pathlib import Path

import pytest

from workflow_engine.db import (
    claim_task,
    load_job_state,
)
from workflow_engine.queue_ops import ingest_manifest
from workflow_engine.transitions import HAPPY_PATH


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
