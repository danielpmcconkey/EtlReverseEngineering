"""Worker pool: N threads running the claim-execute-enqueue loop.

Provides: WorkerPool.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Protocol

import structlog

from workflow_engine.db import claim_task, close_pool, ensure_schema, get_pool, is_clutch_engaged


class TaskHandler(Protocol):
    """Protocol for task handlers invoked by workers.

    Receives a claimed task dict with keys: id, job_id, node_name.
    Responsible for executing the node, updating state, and enqueuing
    the next task (or marking terminal).
    """

    def __call__(self, task: dict[str, Any]) -> None: ...


class WorkerPool:
    """Pool of N worker threads that claim and process tasks from the queue.

    Each worker independently loops: claim a task, invoke the handler,
    repeat. When no tasks are available, workers poll with a short sleep.
    """

    def __init__(
        self,
        handler: TaskHandler,
        n_workers: int | None = None,
        poll_interval: float = 0.1,
        clutch_interval: float = 300.0,
    ) -> None:
        if n_workers is None:
            n_workers = int(os.environ.get("RE_WORKER_COUNT", "6"))
        self._handler = handler
        self._n_workers = n_workers
        self._poll_interval = poll_interval
        self._clutch_interval = clutch_interval
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._log = structlog.get_logger()

    @property
    def n_workers(self) -> int:
        return self._n_workers

    def start(self) -> None:
        """Start all worker threads."""
        self._stop_event.clear()
        for i in range(self._n_workers):
            t = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                name=f"re-worker-{i}",
                daemon=True,
            )
            self._threads.append(t)
            t.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal all workers to stop and wait for them to finish."""
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=timeout)
        self._threads.clear()

    def _worker_loop(self, worker_id: int) -> None:
        """Main loop for a single worker thread."""
        log = self._log.bind(worker_id=worker_id)
        log.debug("worker_started")

        while not self._stop_event.is_set():
            # Token-budget clutch: sleep until disengaged.
            if is_clutch_engaged():
                log.info("clutch_engaged", sleep_seconds=self._clutch_interval)
                self._stop_event.wait(self._clutch_interval)
                continue

            task = claim_task()
            if task is None:
                self._stop_event.wait(self._poll_interval)
                continue

            log.info(
                "task_claimed",
                task_id=task["id"],
                job_id=task["job_id"],
                node_name=task["node_name"],
            )
            try:
                self._handler(task)
            except Exception:
                log.exception(
                    "task_handler_error",
                    task_id=task["id"],
                    job_id=task["job_id"],
                    node_name=task["node_name"],
                )

        log.debug("worker_stopped")

    def run_until_drained(self, timeout: float = 30.0) -> None:
        """Start workers and block until the queue is empty, then stop.

        Useful for testing and batch runs. Checks for an empty queue
        by polling — stops when no tasks are claimed by any worker for
        a full poll cycle.
        """
        self.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pool = get_pool()
            with pool.connection() as conn:
                # Check both queue activity AND running jobs to avoid
                # the race between complete_task and enqueue_task.
                queue_row = conn.execute(
                    "SELECT count(*) FROM control.re_task_queue "
                    "WHERE status IN ('pending', 'claimed')"
                ).fetchone()
                running_row = conn.execute(
                    "SELECT count(*) FROM control.re_job_state "
                    "WHERE status = 'RUNNING'"
                ).fetchone()
            queue_active = queue_row is not None and queue_row[0] > 0
            jobs_running = running_row is not None and running_row[0] > 0
            if not queue_active and not jobs_running:
                break
            time.sleep(self._poll_interval)
        self.stop()
