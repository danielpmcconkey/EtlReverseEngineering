"""Tests for queue write paths: ingest_manifest."""

import json
import tempfile
from pathlib import Path

import pytest

from tests.conftest import make_test_job_id

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
        jids = [make_test_job_id(f"mf{i}") for i in range(3)]
        path = self._write_manifest([
            {"job_id": jids[0], "job_name": "JobA", "job_conf_path": "/a.json"},
            {"job_id": jids[1], "job_name": "JobB", "job_conf_path": "/b.json"},
            {"job_id": jids[2], "job_name": "JobC", "job_conf_path": "/c.json"},
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
        jid = make_test_job_id("initst")
        path = self._write_manifest([
            {"job_id": jid, "job_name": "TestJob", "job_conf_path": "/t.json"},
        ])
        ingest_manifest(path)

        state = load_job_state(jid)
        assert state is not None
        assert state.job_id == jid
        assert state.current_node == "LocateOgSourceFiles"
        assert state.status == "RUNNING"
        assert state.main_retry_count == 0

    def test_returns_job_ids(self):
        """Returns a list of job IDs matching the number of jobs."""
        jids = [make_test_job_id(f"ret{i}") for i in range(5)]
        path = self._write_manifest([
            {"job_id": jid, "job_name": f"Job{i}", "job_conf_path": f"/{i}.json"}
            for i, jid in enumerate(jids)
        ])
        result_ids = ingest_manifest(path)
        assert len(result_ids) == 5
        assert all(isinstance(jid, str) for jid in result_ids)

    def test_real_manifest_format(self):
        """Works with the actual manifest format (job_id as int)."""
        jid = make_test_job_id("real")
        path = self._write_manifest([
            {"job_id": jid, "job_name": "CustomerAccountSummary",
             "job_conf_path": "{ETL_ROOT}/JobExecutor/Jobs/customer_account_summary.json"},
        ])
        job_ids = ingest_manifest(path)
        assert len(job_ids) == 1

        state = load_job_state(jid)
        assert state is not None
