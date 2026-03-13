"""Tests for workflow_engine.logging (LOG-01)."""

import io
import json
import sys

from workflow_engine.logging import configure_logging


class TestLogging:
    def test_json_output(self) -> None:
        """configure_logging() produces JSON with event, timestamp, level keys."""
        configure_logging()
        import structlog

        capture = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = capture
        try:
            logger = structlog.get_logger()
            logger.info("test_event")
        finally:
            sys.stdout = old_stdout

        output = capture.getvalue().strip()
        data = json.loads(output)
        assert "event" in data
        assert "timestamp" in data
        assert "level" in data

    def test_bound_context(self) -> None:
        """structlog bound logger carries context across log calls."""
        configure_logging()
        import structlog

        capture = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = capture
        try:
            logger = structlog.get_logger().bind(job_id="test-123")
            logger.info("context_test")
        finally:
            sys.stdout = old_stdout

        output = capture.getvalue().strip()
        data = json.loads(output)
        assert data["job_id"] == "test-123"
        assert data["event"] == "context_test"
