"""Tests for the worker pool."""

import os
import threading
import time

import pytest

from workflow_engine.db import (
    complete_task,
    enqueue_task,
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

        def handler(task):
            with lock:
                processed.append(task["job_id"])
            complete_task(task["id"])

        for i in range(5):
            enqueue_task(f"job-{i}", "NodeA")

        wp = WorkerPool(handler=handler, n_workers=2, poll_interval=0.05)
        wp.run_until_drained(timeout=5.0)

        assert sorted(processed) == [f"job-{i}" for i in range(5)]

    def test_no_double_processing(self):
        """Each task is processed by exactly one worker."""
        seen = []
        lock = threading.Lock()

        def handler(task):
            with lock:
                seen.append((task["id"], threading.current_thread().name))
            complete_task(task["id"])

        for i in range(10):
            enqueue_task(f"job-{i}", "NodeA")

        wp = WorkerPool(handler=handler, n_workers=4, poll_interval=0.05)
        wp.run_until_drained(timeout=5.0)

        task_ids = [s[0] for s in seen]
        assert len(task_ids) == 10
        assert len(set(task_ids)) == 10  # no duplicates

    def test_multiple_workers_active(self):
        """Multiple workers actually run concurrently."""
        active_threads = set()
        lock = threading.Lock()

        def handler(task):
            with lock:
                active_threads.add(threading.current_thread().name)
            time.sleep(0.05)  # hold the task briefly
            complete_task(task["id"])

        for i in range(8):
            enqueue_task(f"job-{i}", "NodeA")

        wp = WorkerPool(handler=handler, n_workers=4, poll_interval=0.02)
        wp.run_until_drained(timeout=5.0)

        # At least 2 distinct worker threads should have participated
        assert len(active_threads) >= 2

    def test_any_worker_any_job(self):
        """Workers are fungible — multiple workers process different jobs."""
        worker_jobs = {}
        lock = threading.Lock()

        def handler(task):
            thread_name = threading.current_thread().name
            with lock:
                worker_jobs.setdefault(thread_name, []).append(task["job_id"])
            complete_task(task["id"])

        for i in range(12):
            enqueue_task(f"job-{i}", "NodeA")

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

        def handler(task):
            with lock:
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise ValueError("boom")
                processed.append(task["job_id"])
            complete_task(task["id"])

        # First task will error, second should still get processed
        enqueue_task("job-err", "NodeA")
        enqueue_task("job-ok", "NodeB")

        wp = WorkerPool(handler=handler, n_workers=1, poll_interval=0.05)
        wp.run_until_drained(timeout=5.0)

        assert "job-ok" in processed

    def test_stop_signals_workers(self):
        """stop() causes workers to exit their loop."""
        wp = WorkerPool(handler=lambda t: None, n_workers=2, poll_interval=0.05)
        wp.start()
        time.sleep(0.1)  # let them start polling
        wp.stop(timeout=2.0)
        # All threads should be dead
        for t in wp._threads:
            assert not t.is_alive()
