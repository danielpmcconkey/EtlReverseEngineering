"""Queue write paths: manifest ingestion.

Bridges the transition table and the task queue — bulk-loads jobs from a manifest.

Provides: ingest_manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from workflow_engine.db import (
    enqueue_task,
    load_job_state,
    save_job_state,
)
from workflow_engine.models import JobState
from workflow_engine.transitions import (
    HAPPY_PATH,
)

log = structlog.get_logger()


def ingest_manifest(manifest_path: str | Path) -> list[str]:
    """Load a job manifest and enqueue tasks for every job.

    For new jobs, creates initial state and enqueues the first node.
    For existing RUNNING jobs, enqueues their current_node — assumes
    a human has already cleaned up state to the right resume point.
    Completed and dead-lettered jobs are skipped.
    Returns a list of job IDs that were enqueued.
    """
    path = Path(manifest_path)
    data = json.loads(path.read_text())
    jobs = data["jobs"]

    first_node = HAPPY_PATH[0]
    job_ids: list[str] = []

    for entry in jobs:
        job_id = str(entry["job_id"])
        existing = load_job_state(job_id)

        if existing is not None:
            if existing.status in ("COMPLETE", "DEAD_LETTER"):
                log.info(
                    "ingest_skip",
                    job_id=job_id,
                    status=existing.status,
                )
                continue

            # Resume: trust that state has been set to the right node externally.
            log.info(
                "ingest_resume",
                job_id=job_id,
                node=existing.current_node,
                retry=existing.main_retry_count,
            )
            enqueue_task(job_id, existing.current_node)
            job_ids.append(job_id)
        else:
            state = JobState(job_id=job_id)
            save_job_state(state)
            enqueue_task(job_id, first_node)
            job_ids.append(job_id)

    return job_ids
