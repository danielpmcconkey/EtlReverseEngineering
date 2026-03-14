"""Agent node: invokes Claude CLI with a blueprint to execute workflow steps.

Replaces stub nodes with real Claude CLI agent invocations.
Each agent gets a blueprint as system prompt, job context as user prompt,
and must return a structured JSON outcome block.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import structlog

from workflow_engine.models import JobState, Outcome
from workflow_engine.nodes import Node

log = structlog.get_logger()

# Maps the outcome strings agents return to internal Outcome enum values.
_OUTCOME_MAP: dict[str, Outcome] = {
    "SUCCESS": Outcome.SUCCESS,
    "FAIL": Outcome.FAILURE,
    "APPROVED": Outcome.APPROVE,
    "CONDITIONAL": Outcome.CONDITIONAL,
    "REJECTED": Outcome.FAIL,
}


class AgentNode(Node):
    """Executes a workflow step by invoking Claude CLI with a blueprint."""

    # Nodes that need ETL effective date range in their prompt.
    _DATE_AWARE_NODES: set[str] = {
        "ExecuteJobRuns",
        "ExecuteProofmark",
        "FinalSignOff",
        "FBR_EvidenceAudit",
    }

    def __init__(
        self,
        node_name: str,
        blueprint_path: Path,
        jobs_dir: Path,
        *,
        model: str = "sonnet",
        sub_agents: dict[str, Any] | None = None,
        etl_start_date: str | None = None,
        etl_end_date: str | None = None,
    ) -> None:
        self.node_name = node_name
        self.blueprint_path = blueprint_path
        self.jobs_dir = jobs_dir
        self.model = model
        self.sub_agents = sub_agents
        self.etl_start_date = etl_start_date
        self.etl_end_date = etl_end_date

    def execute(self, job: JobState) -> Outcome:
        job_dir = self.jobs_dir / job.job_id
        process_dir = job_dir / "process"
        artifacts_dir = job_dir / "artifacts"
        process_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        blueprint_text = self.blueprint_path.read_text()

        prompt = (
            f"You are working on job {job.job_id}.\n"
            f"Job directory: {job_dir}\n"
            f"Process artifacts (read prior nodes): {process_dir}\n"
            f"Product artifacts (read/write deliverables): {artifacts_dir}\n"
            f"Current node: {self.node_name}\n"
            f"Current state: {job.current_node}\n"
            f"Retry count: {job.main_retry_count}\n"
        )

        if job.last_rejection_reason:
            prompt += f"Last rejection reason: {job.last_rejection_reason}\n"

        if self.node_name in self._DATE_AWARE_NODES:
            if self.etl_start_date and self.etl_end_date:
                prompt += (
                    f"ETL effective date range: {self.etl_start_date} through {self.etl_end_date}\n"
                    f"Run/validate ALL dates in this range. No sampling, no skipping.\n"
                )
            else:
                prompt += (
                    "WARNING: No ETL effective date range provided via CLI. "
                    "Cannot execute without --etl-start-date and --etl-end-date.\n"
                )

        cmd = [
            "claude",
            "-p",
            "--append-system-prompt", blueprint_text,
            "--output-format", "json",
            "--model", self.model,
            "--dangerously-skip-permissions",
            "--no-session-persistence",
        ]

        if self.sub_agents:
            cmd.extend(["--agents", json.dumps(self.sub_agents)])

        cmd.append(prompt)

        log.info(
            "agent_invoke",
            node=self.node_name,
            job_id=job.job_id,
            blueprint=str(self.blueprint_path),
            model=self.model,
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(self.jobs_dir.parent),
            )
        except subprocess.TimeoutExpired:
            log.error("agent_timeout", node=self.node_name, job_id=job.job_id)
            return Outcome.FAILURE

        if result.returncode != 0:
            log.error(
                "agent_error",
                node=self.node_name,
                job_id=job.job_id,
                returncode=result.returncode,
                stderr=result.stderr[:500] if result.stderr else "",
            )
            return Outcome.FAILURE

        return self._parse_outcome(result.stdout, job)

    def _parse_outcome(self, stdout: str, job: JobState) -> Outcome:
        """Parse the Claude CLI JSON output and extract the outcome enum."""
        try:
            cli_response = json.loads(stdout)
        except json.JSONDecodeError:
            log.error(
                "agent_parse_error",
                node=self.node_name,
                job_id=job.job_id,
                error="Failed to parse CLI JSON response",
                raw=stdout[:500],
            )
            return Outcome.FAILURE

        # Claude CLI --output-format json wraps the response.
        # The agent's actual text is in the "result" field.
        agent_text = cli_response.get("result", "")

        # Find the last JSON block in the agent's output.
        outcome_data = self._extract_outcome_json(agent_text)
        if outcome_data is None:
            log.error(
                "agent_no_outcome",
                node=self.node_name,
                job_id=job.job_id,
                error="No outcome JSON block found in agent output",
                raw=agent_text[:500],
            )
            return Outcome.FAILURE

        outcome_str = outcome_data.get("outcome", "").upper()
        if outcome_str not in _OUTCOME_MAP:
            log.error(
                "agent_bad_outcome",
                node=self.node_name,
                job_id=job.job_id,
                error=f"Unknown outcome value: {outcome_str}",
                valid=list(_OUTCOME_MAP.keys()),
            )
            return Outcome.FAILURE

        # Write the process artifact for the next agent.
        outcome = _OUTCOME_MAP[outcome_str]
        if outcome in (Outcome.SUCCESS, Outcome.APPROVE, Outcome.CONDITIONAL):
            process_file = self.jobs_dir / job.job_id / "process" / f"{self.node_name}.json"
            try:
                process_file.write_text(json.dumps(outcome_data, indent=2))
            except OSError as e:
                log.error(
                    "process_artifact_write_error",
                    node=self.node_name,
                    job_id=job.job_id,
                    error=str(e),
                )

        log.info(
            "agent_result",
            node=self.node_name,
            job_id=job.job_id,
            outcome=outcome_str,
            reason=outcome_data.get("reason", ""),
        )

        return outcome

    @staticmethod
    def _extract_outcome_json(text: str) -> dict[str, Any] | None:
        """Extract the last JSON object from agent text that contains an 'outcome' key.

        Splits on '{', attempts json.loads on each '{...}' candidate, and
        returns the last one containing an 'outcome' key.
        """
        result: dict[str, Any] | None = None
        parts = text.split("{")
        for i in range(1, len(parts)):
            candidate = "{" + "{".join(parts[i:])
            # Try progressively shorter suffixes starting from the full remainder.
            # Walk backwards through closing braces to find valid JSON.
            search_start = 0
            while True:
                close = candidate.find("}", search_start)
                if close == -1:
                    break
                snippet = candidate[: close + 1]
                try:
                    data = json.loads(snippet)
                    if isinstance(data, dict) and "outcome" in data:
                        result = data
                    break  # valid parse — move to next split
                except json.JSONDecodeError:
                    search_start = close + 1
        return result
