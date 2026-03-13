"""Workflow engine: main loop that drives jobs through the state machine.

Provides: Engine class with run_job() and run() methods.
"""

from __future__ import annotations

import random

import structlog

from workflow_engine.logging import configure_logging
from workflow_engine.models import EngineConfig, JobState, Outcome
from workflow_engine.nodes import create_node_registry
from workflow_engine.transitions import TRANSITION_TABLE, validate_transition_table


class Engine:
    """Drives jobs through the workflow state machine.

    Each job starts at LocateOgSourceFiles and transitions through nodes
    until reaching COMPLETE (or DEAD_LETTER in failure scenarios).
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        rng = random.Random(config.seed) if config.seed is not None else None
        self._registry = create_node_registry(rng)
        self._log = structlog.get_logger()

        errors = validate_transition_table()
        if errors:
            raise ValueError(f"Invalid transition table: {'; '.join(errors)}")

    def run_job(self, job: JobState) -> JobState:
        """Run a single job through the state machine until terminal state."""
        log = self._log.bind(job_id=job.job_id)

        while job.status == "RUNNING":
            node = self._registry[job.current_node]
            outcome = node.execute(job)

            key = (job.current_node, outcome)
            if key not in TRANSITION_TABLE:
                raise ValueError(
                    f"No transition for ({job.current_node}, {outcome.name})"
                )
            next_node = TRANSITION_TABLE[key]

            log.info(
                "transition",
                node=job.current_node,
                outcome=outcome.name,
                next_node=next_node,
                main_retry=job.main_retry_count,
                conditional_counts=dict(job.conditional_counts),
            )

            if next_node == "COMPLETE":
                job.status = "COMPLETE"
            else:
                job.current_node = next_node

        log.info("job_complete", final_status=job.status)
        return job

    def run(self) -> list[JobState]:
        """Run n_jobs sequentially, returning all completed job states."""
        configure_logging()
        results: list[JobState] = []

        for i in range(self._config.n_jobs):
            job = JobState(job_id=f"job-{i + 1:04d}")
            result = self.run_job(job)
            results.append(result)

        return results
