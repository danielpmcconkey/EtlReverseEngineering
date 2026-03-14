"""Queue write paths: enqueue-next-on-completion and manifest ingestion.

Bridges the transition table and the task queue — determines what to enqueue
next based on state machine logic, and bulk-loads jobs from a manifest.

Provides: enqueue_next, ingest_manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

from workflow_engine.db import (
    complete_task,
    enqueue_task,
    load_job_state,
    save_job_state,
)
from workflow_engine.models import JobState, Outcome
from workflow_engine.transitions import (
    HAPPY_PATH,
    TRANSITION_TABLE,
)


def enqueue_next(
    task_id: int,
    job_id: str,
    current_node: str,
    outcome: Outcome,
) -> int | None:
    """Complete a task and enqueue the next one based on transition lookup.

    Returns the new task id, or None if the job reached a terminal state
    (COMPLETE or DEAD_LETTER).
    """
    complete_task(task_id)

    key = (current_node, outcome)
    next_node = TRANSITION_TABLE.get(key)

    if next_node is None or next_node == "COMPLETE":
        return None

    return enqueue_task(job_id, next_node)


def ingest_manifest(manifest_path: str | Path) -> list[int]:
    """Load a job manifest and enqueue the first task for every job.

    Creates initial JobState for each job in Postgres.
    Returns a list of task IDs that were enqueued.
    """
    path = Path(manifest_path)
    data = json.loads(path.read_text())
    jobs = data["jobs"]

    first_node = HAPPY_PATH[0]
    task_ids: list[int] = []

    for entry in jobs:
        job_id = str(entry["job_id"])

        # Create initial job state in Postgres
        state = JobState(job_id=job_id)
        save_job_state(state)

        # Enqueue first node
        task_id = enqueue_task(job_id, first_node)
        task_ids.append(task_id)

    return task_ids
