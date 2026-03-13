"""Workflow engine: main loop that drives jobs through the state machine.

Provides: Engine class with run_job() and run() methods.
"""

from __future__ import annotations

import random

import structlog

from workflow_engine.logging import configure_logging
from workflow_engine.models import EngineConfig, JobState, Outcome
from workflow_engine.nodes import create_node_registry
from workflow_engine.transitions import (
    FBR_ROUTING,
    HAPPY_PATH,
    REVIEW_ROUTING,
    TRANSITION_TABLE,
    validate_transition_table,
)


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

    def _resolve_outcome(
        self, job: JobState, node_name: str, raw_outcome: Outcome
    ) -> Outcome:
        """Apply counter logic to a raw node outcome.

        Processing order (critical):
        1. APPROVE -> reset conditional counter
        2. CONDITIONAL -> increment conditional counter
        3. If M reached -> auto-promote to FAIL
        4. FAIL -> increment main retry, set rejection reason
        5. If N reached -> DEAD_LETTER
        6. Reset downstream conditional counters on rewind
        """
        outcome = raw_outcome

        if outcome == Outcome.APPROVE:
            job.conditional_counts[node_name] = 0
            return outcome

        if outcome == Outcome.CONDITIONAL:
            job.conditional_counts[node_name] = (
                job.conditional_counts.get(node_name, 0) + 1
            )
            job.last_rejection_reason = f"CONDITIONAL at {node_name}"

            # Set fbr_return_pending on FBR gate CONDITIONAL (never on FAIL)
            if node_name in FBR_ROUTING:
                job.fbr_return_pending = True

            if (
                job.conditional_counts[node_name]
                >= self._config.max_conditional_per_node
            ):
                outcome = Outcome.FAIL  # auto-promote

        if outcome == Outcome.FAIL:
            job.main_retry_count += 1
            job.last_rejection_reason = f"FAIL at {node_name}"

            if job.main_retry_count >= self._config.max_main_retries:
                job.status = "DEAD_LETTER"
                return outcome

            # Reset downstream conditionals on rewind
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

    def run_job(self, job: JobState) -> JobState:
        """Run a single job through the state machine until terminal state."""
        log = self._log.bind(job_id=job.job_id)

        while job.status == "RUNNING":
            # Clear triage_results on entry to Triage_ProfileData
            if job.current_node == "Triage_ProfileData":
                job.triage_results = {}

            node = self._registry[job.current_node]
            raw_outcome = node.execute(job)
            outcome = self._resolve_outcome(job, job.current_node, raw_outcome)

            if job.status == "DEAD_LETTER":
                log.info(
                    "dead_letter",
                    node=job.current_node,
                    outcome=outcome.name,
                    main_retry=job.main_retry_count,
                    last_rejection=job.last_rejection_reason,
                )
                break

            # TRIAGE_ROUTE: engine handles routing directly (no TRANSITION_TABLE entry)
            if outcome == Outcome.TRIAGE_ROUTE:
                rewind_target = job.triage_rewind_target
                job.main_retry_count += 1
                job.last_rejection_reason = f"Triage routed to {rewind_target}"

                if rewind_target == "DEAD_LETTER" or job.main_retry_count >= self._config.max_main_retries:
                    job.status = "DEAD_LETTER"
                    log.info(
                        "dead_letter",
                        node=job.current_node,
                        outcome=outcome.name,
                        main_retry=job.main_retry_count,
                        last_rejection=job.last_rejection_reason,
                    )
                    break

                self._reset_downstream_conditionals(job, rewind_target)
                log.info(
                    "transition",
                    node=job.current_node,
                    outcome=outcome.name,
                    next_node=rewind_target,
                    main_retry=job.main_retry_count,
                    conditional_counts=dict(job.conditional_counts),
                    last_rejection=job.last_rejection_reason,
                )
                job.current_node = rewind_target
                continue

            key = (job.current_node, outcome)
            if key not in TRANSITION_TABLE:
                raise ValueError(
                    f"No transition for ({job.current_node}, {outcome.name})"
                )
            next_node = TRANSITION_TABLE[key]

            # FBR intercept: if review node approves while fbr_return_pending,
            # redirect to FBR_BrdCheck to restart the gauntlet.
            if (
                outcome == Outcome.APPROVE
                and job.fbr_return_pending
                and job.current_node in REVIEW_ROUTING
            ):
                next_node = "FBR_BrdCheck"
                job.fbr_return_pending = False

            log.info(
                "transition",
                node=job.current_node,
                outcome=outcome.name,
                next_node=next_node,
                main_retry=job.main_retry_count,
                conditional_counts=dict(job.conditional_counts),
                last_rejection=job.last_rejection_reason,
            )

            if next_node == "COMPLETE":
                job.status = "COMPLETE"
            else:
                job.current_node = next_node
                # Clear fbr_return_pending on entry to FBR_BrdCheck
                # (whether via intercept or natural replay after FAIL rewind)
                if next_node == "FBR_BrdCheck":
                    job.fbr_return_pending = False

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
