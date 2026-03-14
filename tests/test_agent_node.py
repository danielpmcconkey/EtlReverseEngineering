"""Tests for AgentNode: CLI invocation, outcome parsing, process artifact writing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from workflow_engine.agent_node import AgentNode, _OUTCOME_MAP
from workflow_engine.models import JobState, Outcome


@pytest.fixture
def tmp_job_env(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create temp blueprints_dir, jobs_dir, and a sample blueprint."""
    blueprints_dir = tmp_path / "blueprints"
    blueprints_dir.mkdir()
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()

    bp = blueprints_dir / "og-locator.md"
    bp.write_text("You are the og-locator agent. Find original source files.")

    return blueprints_dir, jobs_dir, bp


@pytest.fixture
def agent_node(tmp_job_env: tuple[Path, Path, Path]) -> AgentNode:
    _, jobs_dir, bp = tmp_job_env
    return AgentNode(
        node_name="LocateOgSourceFiles",
        blueprint_path=bp,
        jobs_dir=jobs_dir,
        model="sonnet",
        budget=0.25,
    )


# --- _extract_outcome_json tests ---


class TestExtractOutcomeJson:
    def test_simple_json_block(self) -> None:
        text = 'I did some work.\n{"outcome": "SUCCESS", "reason": "found files"}'
        result = AgentNode._extract_outcome_json(text)
        assert result is not None
        assert result["outcome"] == "SUCCESS"

    def test_json_with_surrounding_text(self) -> None:
        text = (
            "Here is my analysis...\n\n"
            '{"outcome": "APPROVED", "reason": "BRD looks good", "conditions": []}\n\n'
            "End of output."
        )
        result = AgentNode._extract_outcome_json(text)
        assert result is not None
        assert result["outcome"] == "APPROVED"

    def test_multiple_json_blocks_picks_last_with_outcome(self) -> None:
        text = (
            '{"some": "other json"}\n'
            '{"outcome": "CONDITIONAL", "reason": "needs work", "conditions": ["fix imports"]}'
        )
        result = AgentNode._extract_outcome_json(text)
        assert result is not None
        assert result["outcome"] == "CONDITIONAL"

    def test_no_json_returns_none(self) -> None:
        assert AgentNode._extract_outcome_json("just plain text") is None

    def test_json_without_outcome_key_returns_none(self) -> None:
        assert AgentNode._extract_outcome_json('{"result": "SUCCESS"}') is None

    def test_nested_braces(self) -> None:
        text = '{"outcome": "SUCCESS", "reason": "done", "body": {"details": {"nested": true}}}'
        result = AgentNode._extract_outcome_json(text)
        assert result is not None
        assert result["outcome"] == "SUCCESS"
        assert result["body"]["details"]["nested"] is True

    def test_malformed_json_skipped(self) -> None:
        text = '{broken json}\n{"outcome": "FAIL", "reason": "bad input"}'
        result = AgentNode._extract_outcome_json(text)
        assert result is not None
        assert result["outcome"] == "FAIL"

    def test_empty_string(self) -> None:
        assert AgentNode._extract_outcome_json("") is None

    def test_rejected_maps_correctly(self) -> None:
        text = '{"outcome": "REJECTED", "reason": "does not meet spec"}'
        result = AgentNode._extract_outcome_json(text)
        assert result is not None
        assert result["outcome"] == "REJECTED"


# --- Outcome mapping tests ---


class TestOutcomeMap:
    def test_all_valid_outcomes(self) -> None:
        assert _OUTCOME_MAP["SUCCESS"] == Outcome.SUCCESS
        assert _OUTCOME_MAP["FAIL"] == Outcome.FAILURE
        assert _OUTCOME_MAP["APPROVED"] == Outcome.APPROVE
        assert _OUTCOME_MAP["CONDITIONAL"] == Outcome.CONDITIONAL
        assert _OUTCOME_MAP["REJECTED"] == Outcome.FAIL

    def test_outcome_map_has_five_entries(self) -> None:
        assert len(_OUTCOME_MAP) == 5


# --- execute() tests (mocked subprocess) ---


def _make_cli_response(outcome: str, reason: str = "test", conditions: list[str] | None = None) -> str:
    """Build a mock Claude CLI JSON response wrapping an agent outcome block."""
    agent_text = (
        f"I completed my work.\n\n"
        f'{json.dumps({"outcome": outcome, "reason": reason, "conditions": conditions or []})}'
    )
    return json.dumps({"result": agent_text, "cost_usd": 0.01})


class TestAgentNodeExecute:
    def test_success_outcome(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-001")
        mock_result = _make_cli_response("SUCCESS", "found all source files")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_result
            mock_run.return_value.stderr = ""

            outcome = agent_node.execute(job)

        assert outcome == Outcome.SUCCESS
        # Process artifact should be written
        process_file = agent_node.jobs_dir / "job-001" / "process" / "LocateOgSourceFiles.json"
        assert process_file.exists()
        data = json.loads(process_file.read_text())
        assert data["outcome"] == "SUCCESS"

    def test_fail_outcome_no_process_artifact(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-002")
        mock_result = _make_cli_response("FAIL", "could not locate files")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_result
            mock_run.return_value.stderr = ""

            outcome = agent_node.execute(job)

        assert outcome == Outcome.FAILURE
        # No process artifact on failure
        process_file = agent_node.jobs_dir / "job-002" / "process" / "LocateOgSourceFiles.json"
        assert not process_file.exists()

    def test_approved_outcome(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-003")
        mock_result = _make_cli_response("APPROVED", "looks good")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_result
            mock_run.return_value.stderr = ""

            outcome = agent_node.execute(job)

        assert outcome == Outcome.APPROVE

    def test_conditional_outcome(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-004")
        mock_result = _make_cli_response("CONDITIONAL", "needs fixes", ["fix imports", "add docstring"])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_result
            mock_run.return_value.stderr = ""

            outcome = agent_node.execute(job)

        assert outcome == Outcome.CONDITIONAL
        process_file = agent_node.jobs_dir / "job-004" / "process" / "LocateOgSourceFiles.json"
        data = json.loads(process_file.read_text())
        assert data["conditions"] == ["fix imports", "add docstring"]

    def test_rejected_maps_to_fail(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-005")
        mock_result = _make_cli_response("REJECTED", "does not meet spec")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_result
            mock_run.return_value.stderr = ""

            outcome = agent_node.execute(job)

        assert outcome == Outcome.FAIL

    def test_cli_nonzero_exit_returns_failure(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-006")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "API error"

            outcome = agent_node.execute(job)

        assert outcome == Outcome.FAILURE

    def test_timeout_returns_failure(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-007")

        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired("claude", 600)):
            outcome = agent_node.execute(job)

        assert outcome == Outcome.FAILURE

    def test_unparseable_stdout_returns_failure(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-008")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "not json at all"
            mock_run.return_value.stderr = ""

            outcome = agent_node.execute(job)

        assert outcome == Outcome.FAILURE

    def test_no_outcome_in_agent_text_returns_failure(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-009")
        # Valid CLI JSON, but agent text has no outcome block
        cli_response = json.dumps({"result": "I did stuff but forgot the outcome block"})

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = cli_response
            mock_run.return_value.stderr = ""

            outcome = agent_node.execute(job)

        assert outcome == Outcome.FAILURE

    def test_unknown_outcome_value_returns_failure(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-010")
        mock_result = _make_cli_response("MAYBE", "not a real outcome")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_result
            mock_run.return_value.stderr = ""

            outcome = agent_node.execute(job)

        assert outcome == Outcome.FAILURE

    def test_job_directories_created(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-011")
        mock_result = _make_cli_response("SUCCESS")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_result
            mock_run.return_value.stderr = ""

            agent_node.execute(job)

        assert (agent_node.jobs_dir / "job-011" / "process").is_dir()
        assert (agent_node.jobs_dir / "job-011" / "artifacts").is_dir()

    def test_cli_command_structure(self, agent_node: AgentNode) -> None:
        """Verify the CLI command is assembled correctly."""
        job = JobState(job_id="job-012")
        mock_result = _make_cli_response("SUCCESS")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_result
            mock_run.return_value.stderr = ""

            agent_node.execute(job)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "--output-format" in cmd
        assert cmd[cmd.index("--output-format") + 1] == "json"
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "sonnet"
        assert "--max-budget-usd" in cmd
        assert "--dangerously-skip-permissions" in cmd
        assert "--append-system-prompt" in cmd

    def test_rejection_reason_included_in_prompt(self, agent_node: AgentNode) -> None:
        job = JobState(job_id="job-013", last_rejection_reason="CONDITIONAL at ReviewBrd")
        mock_result = _make_cli_response("SUCCESS")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_result
            mock_run.return_value.stderr = ""

            agent_node.execute(job)

        # The prompt is the last positional arg
        cmd = mock_run.call_args[0][0]
        prompt = cmd[-1]
        assert "CONDITIONAL at ReviewBrd" in prompt
