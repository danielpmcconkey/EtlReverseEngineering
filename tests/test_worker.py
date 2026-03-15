"""Tests for the worker pool."""

import threading
import time

import pytest

from tests.conftest import make_test_job_id

from workflow_engine.db import (
    complete_task,
    enqueue_task,
    get_pool,
)
from workflow_engine.worker import WorkerPool


class TestWorkerPoolConfig:
    def test_default_worker_count(self):
        """Default is 6 workers."""
        wp = WorkerPool(handler=lambda t: None)
        assert wp.n_workers == 6

    def test_explicit_worker_count(self):
        """Can set worker count explicitly."""
        wp = WorkerPool(handler=lambda t: None, n_workers=3)
        assert wp.n_workers == 3

    def test_env_var_worker_count(self, monkeypatch):
        """RE_WORKER_COUNT env var overrides default."""
        monkeypatch.setenv("RE_WORKER_COUNT", "12")
        wp = WorkerPool(handler=lambda t: None)
        assert wp.n_workers == 12

    def test_explicit_overrides_env(self, monkeypatch):
        """Explicit n_workers takes priority over env var."""
        monkeypatch.setenv("RE_WORKER_COUNT", "12")
        wp = WorkerPool(handler=lambda t: None, n_workers=4)
        assert wp.n_workers == 4


class TestWorkerExecution:
    def test_workers_process_tasks(self):
        """Workers claim and process enqueued tasks."""
        processed = []
        lock = threading.Lock()
        jids = [make_test_job_id(f"wp{i}") for i in range(5)]

        def handler(task):
            with lock:
                processed.append(task["job_id"])
            complete_task(task["id"])

        for jid in jids:
            enqueue_task(jid, "NodeA")

        wp = WorkerPool(handler=handler, n_workers=2, poll_interval=0.05)
        wp.run_until_drained(timeout=5.0)

        assert sorted(processed) == sorted(jids)

    def test_no_double_processing(self):
        """Each task is processed by exactly one worker."""
        seen = []
        lock = threading.Lock()
        jids = [make_test_job_id(f"nd{i}") for i in range(10)]

        def handler(task):
            with lock:
                seen.append((task["id"], threading.current_thread().name))
            complete_task(task["id"])

        for jid in jids:
            enqueue_task(jid, "NodeA")

        wp = WorkerPool(handler=handler, n_workers=4, poll_interval=0.05)
        wp.run_until_drained(timeout=5.0)

        task_ids = [s[0] for s in seen]
        assert len(task_ids) == 10
        assert len(set(task_ids)) == 10  # no duplicates

    def test_multiple_workers_active(self):
        """Multiple workers actually run concurrently."""
        active_threads = set()
        lock = threading.Lock()
        jids = [make_test_job_id(f"mw{i}") for i in range(8)]

        def handler(task):
            with lock:
                active_threads.add(threading.current_thread().name)
            time.sleep(0.05)  # hold the task briefly
            complete_task(task["id"])

        for jid in jids:
            enqueue_task(jid, "NodeA")

        wp = WorkerPool(handler=handler, n_workers=4, poll_interval=0.02)
        wp.run_until_drained(timeout=5.0)

        # At least 2 distinct worker threads should have participated
        assert len(active_threads) >= 2

    def test_any_worker_any_job(self):
        """Workers are fungible — multiple workers process different jobs."""
        worker_jobs = {}
        lock = threading.Lock()
        jids = [make_test_job_id(f"aw{i}") for i in range(12)]

        def handler(task):
            thread_name = threading.current_thread().name
            with lock:
                worker_jobs.setdefault(thread_name, []).append(task["job_id"])
            complete_task(task["id"])

        for jid in jids:
            enqueue_task(jid, "NodeA")

        wp = WorkerPool(handler=handler, n_workers=3, poll_interval=0.02)
        wp.run_until_drained(timeout=5.0)

        # All 12 jobs processed
        all_jobs = []
        for jobs in worker_jobs.values():
            all_jobs.extend(jobs)
        assert len(all_jobs) == 12

    def test_handler_error_doesnt_crash_worker(self):
        """A handler exception is caught — the worker keeps running."""
        processed = []
        lock = threading.Lock()
        call_count = {"n": 0}
        jid_err = make_test_job_id("err")
        jid_ok = make_test_job_id("ok")

        def handler(task):
            with lock:
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise ValueError("boom")
                processed.append(task["job_id"])
            complete_task(task["id"])

        # First task will error, second should still get processed
        enqueue_task(jid_err, "NodeA")
        enqueue_task(jid_ok, "NodeB")

        wp = WorkerPool(handler=handler, n_workers=1, poll_interval=0.05)
        wp.run_until_drained(timeout=5.0)

        assert jid_ok in processed

    def test_stop_signals_workers(self):
        """stop() causes workers to exit their loop."""
        wp = WorkerPool(handler=lambda t: None, n_workers=2, poll_interval=0.05)
        wp.start()
        time.sleep(0.1)  # let them start polling
        wp.stop(timeout=2.0)
        # All threads should be dead
        for t in wp._threads:
            assert not t.is_alive()


class TestClutchIntegration:
    def test_clutch_blocks_task_claiming(self):
        """When clutch is engaged, workers sleep instead of claiming tasks."""
        processed = []
        lock = threading.Lock()
        jid = make_test_job_id("clutch")

        def handler(task):
            with lock:
                processed.append(task["job_id"])
            complete_task(task["id"])

        enqueue_task(jid, "NodeA")

        # Engage the clutch
        pool = get_pool()
        with pool.connection() as conn:
            conn.execute(
                "UPDATE control.re_engine_config SET clutch_engaged = true WHERE id = 1"
            )

        wp = WorkerPool(
            handler=handler, n_workers=1, poll_interval=0.05, clutch_interval=0.2
        )
        wp.start()
        time.sleep(0.3)  # give the worker time to hit the clutch check

        # Task should NOT have been processed
        with lock:
            assert len(processed) == 0

        # Disengage the clutch — worker wakes after short clutch_interval
        with pool.connection() as conn:
            conn.execute(
                "UPDATE control.re_engine_config SET clutch_engaged = false WHERE id = 1"
            )

        time.sleep(0.5)  # wait for clutch sleep to expire and task to process
        wp.stop(timeout=2.0)

        with lock:
            assert processed == [jid]
