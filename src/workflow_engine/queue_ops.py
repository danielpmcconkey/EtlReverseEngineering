"""Queue write paths: manifest ingestion.

Bridges the transition table and the task queue — bulk-loads jobs from a manifest.

Provides: ingest_manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

from workflow_engine.db import (
    enqueue_task,
    save_job_state,
)
from workflow_engine.models import JobState
from workflow_engine.transitions import (
    HAPPY_PATH,
)


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
