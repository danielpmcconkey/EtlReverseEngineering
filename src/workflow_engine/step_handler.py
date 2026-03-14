"""Per-step task handler: executes one state machine step per queue task.

Bridges the node registry, transition logic, and queue operations.
Each invocation: load state → execute node → resolve outcome → determine
next node → save state → enqueue next (or mark terminal).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import structlog

from workflow_engine.db import (
    complete_task,
    enqueue_task,
    fail_task,
    load_job_state,
    save_job_state,
)
from workflow_engine.models import EngineConfig, JobState, Outcome
from workflow_engine.nodes import create_agent_registry, create_node_registry
from workflow_engine.transitions import (
    FBR_ROUTING,
    HAPPY_PATH,
    REVIEW_ROUTING,
    TERMINAL_FAIL_NODES,
    TRANSITION_TABLE,
)


class StepHandler:
    """Executes one state machine step per claimed task.

    Implements the TaskHandler protocol expected by WorkerPool.
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        if config.use_agents:
            self._registry = create_agent_registry(
                blueprints_dir=Path(config.blueprints_dir),
                jobs_dir=Path(config.jobs_dir),
                model=config.agent_model,
                budget=config.agent_budget,
            )
        else:
            rng = random.Random(config.seed) if config.seed is not None else None
            self._registry = create_node_registry(rng)
        self._log = structlog.get_logger()

    def __call__(self, task: dict[str, Any]) -> None:
        """Process a single claimed task."""
        task_id = task["id"]
        job_id = task["job_id"]
        node_name = task["node_name"]
        log = self._log.bind(job_id=job_id)

        # Load current job state
        job = load_job_state(job_id)
        if job is None:
            job = JobState(job_id=job_id)

        job.current_node = node_name

        # Clear triage_results on entry to Triage_ProfileData
        if node_name == "Triage_ProfileData":
            job.triage_results = {}

        # Execute the node
        node = self._registry[node_name]
        raw_outcome = node.execute(job)
        outcome = self._resolve_outcome(job, node_name, raw_outcome)

        # Handle terminal: DEAD_LETTER
        if job.status == "DEAD_LETTER":
            log.info(
                "dead_letter",
                node=node_name,
                outcome=outcome.name,
                main_retry=job.main_retry_count,
                last_rejection=job.last_rejection_reason,
            )
            save_job_state(job)
            complete_task(task_id)
            return

        # Handle TRIAGE_ROUTE (engine-level routing, no TRANSITION_TABLE entry)
        if outcome == Outcome.TRIAGE_ROUTE:
            rewind_target = job.triage_rewind_target
            job.main_retry_count += 1
            job.last_rejection_reason = f"Triage routed to {rewind_target}"

            if (
                rewind_target == "DEAD_LETTER"
                or job.main_retry_count >= self._config.max_main_retries
            ):
                job.status = "DEAD_LETTER"
                log.info(
                    "dead_letter",
                    node=node_name,
                    outcome=outcome.name,
                    main_retry=job.main_retry_count,
                    last_rejection=job.last_rejection_reason,
                )
                save_job_state(job)
                complete_task(task_id)
                return

            self._reset_downstream_conditionals(job, rewind_target)
            log.info(
                "transition",
                node=node_name,
                outcome=outcome.name,
                next_node=rewind_target,
                main_retry=job.main_retry_count,
                conditional_counts=dict(job.conditional_counts),
                last_rejection=job.last_rejection_reason,
            )
            job.current_node = rewind_target
            save_job_state(job)
            complete_task(task_id)
            enqueue_task(job_id, rewind_target)
            return

        # Standard transition lookup
        key = (node_name, outcome)
        if key not in TRANSITION_TABLE:
            fail_task(task_id)
            raise ValueError(
                f"No transition for ({node_name}, {outcome.name})"
            )
        next_node = TRANSITION_TABLE[key]

        # FBR intercept: review APPROVE while fbr_return_pending
        if (
            outcome == Outcome.APPROVE
            and job.fbr_return_pending
            and node_name in REVIEW_ROUTING
        ):
            next_node = "FBR_BrdCheck"
            job.fbr_return_pending = False

        log.info(
            "transition",
            node=node_name,
            outcome=outcome.name,
            next_node=next_node,
            main_retry=job.main_retry_count,
            conditional_counts=dict(job.conditional_counts),
            last_rejection=job.last_rejection_reason,
        )

        if next_node == "COMPLETE":
            job.status = "COMPLETE"
            save_job_state(job)
            complete_task(task_id)
        else:
            job.current_node = next_node
            if next_node == "FBR_BrdCheck":
                job.fbr_return_pending = False
            save_job_state(job)
            complete_task(task_id)
            enqueue_task(job_id, next_node)

    def _resolve_outcome(
        self, job: JobState, node_name: str, raw_outcome: Outcome
    ) -> Outcome:
        """Apply counter logic to a raw node outcome."""
        outcome = raw_outcome

        if outcome == Outcome.APPROVE:
            job.conditional_counts[node_name] = 0
            return outcome

        if outcome == Outcome.CONDITIONAL:
            job.conditional_counts[node_name] = (
                job.conditional_counts.get(node_name, 0) + 1
            )
            job.last_rejection_reason = f"CONDITIONAL at {node_name}"

            if node_name in FBR_ROUTING:
                job.fbr_return_pending = True

            if (
                job.conditional_counts[node_name]
                >= self._config.max_conditional_per_node
            ):
                outcome = Outcome.FAIL

        if outcome == Outcome.FAIL:
            job.main_retry_count += 1
            job.last_rejection_reason = f"FAIL at {node_name}"

            if node_name in TERMINAL_FAIL_NODES:
                job.status = "DEAD_LETTER"
                return outcome

            if job.main_retry_count >= self._config.max_main_retries:
                job.status = "DEAD_LETTER"
                return outcome

            if node_name in REVIEW_ROUTING:
                _, rewind_target = REVIEW_ROUTING[node_name]
                self._reset_downstream_conditionals(job, rewind_target)
            elif node_name in FBR_ROUTING:
                _, rewind_target = FBR_ROUTING[node_name]
                self._reset_downstream_conditionals(job, rewind_target)

        return outcome

    def _reset_downstream_conditionals(
        self, job: JobState, rewind_target: str
    ) -> None:
        """Clear conditional counters for all nodes at or downstream of rewind_target."""
        try:
            target_idx = HAPPY_PATH.index(rewind_target)
        except ValueError:
            return

        downstream_nodes = set(HAPPY_PATH[target_idx:])
        for node_name in list(job.conditional_counts):
            if node_name in downstream_nodes:
                job.conditional_counts[node_name] = 0

        # Clean up stale process artifacts from re-walked nodes.
        if self._config.use_agents and self._config.jobs_dir:
            self._cleanup_stale_artifacts(job.job_id, downstream_nodes)

    def _cleanup_stale_artifacts(
        self, job_id: str, nodes_to_clean: set[str]
    ) -> None:
        """Remove process artifacts for nodes being re-walked so agents start fresh."""
        process_dir = Path(self._config.jobs_dir) / job_id / "process"
        if not process_dir.exists():
            return
        for node_name in nodes_to_clean:
            artifact = process_dir / f"{node_name}.json"
            if artifact.exists():
                artifact.unlink()
                self._log.info(
                    "artifact_cleanup",
                    job_id=job_id,
                    removed=str(artifact),
                )
