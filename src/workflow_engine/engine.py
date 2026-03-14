"""Workflow engine: queue-based execution with worker pool.

Provides: Engine class that ingests a manifest and runs jobs through
the state machine via the task queue and worker pool.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from workflow_engine.db import (
    close_pool,
    ensure_schema,
    load_job_state,
)
from workflow_engine.log_config import configure_logging
from workflow_engine.models import EngineConfig, JobState
from workflow_engine.queue_ops import ingest_manifest
from workflow_engine.step_handler import StepHandler
from workflow_engine.transitions import validate_transition_table
from workflow_engine.worker import WorkerPool


class Engine:
    """Drives jobs through the workflow state machine via queue-based execution.

    Ingests a job manifest, enqueues first tasks, and runs a worker pool
    until all jobs reach terminal state.
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self._handler = StepHandler(config)
        self._log = structlog.get_logger()

        errors = validate_transition_table()
        if errors:
            raise ValueError(f"Invalid transition table: {'; '.join(errors)}")

    def run(self, manifest_path: str | Path, timeout: float = 300.0) -> list[JobState]:
        """Ingest manifest, run worker pool until drained, return final states."""
        configure_logging()
        ensure_schema()

        task_ids = ingest_manifest(manifest_path)
        job_ids = [str(i) for i in range(len(task_ids))]

        pool = WorkerPool(
            handler=self._handler,
            n_workers=self._config.n_jobs,  # repurpose n_jobs as worker count
            poll_interval=0.02,
        )
        pool.run_until_drained(timeout=timeout)

        # Collect final states
        results: list[JobState] = []
        for job_id in job_ids:
            state = load_job_state(job_id)
            if state is not None:
                results.append(state)

        return results
