"""Structured logging configuration for the workflow engine.

Provides: configure_logging.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging() -> None:
    """Configure structlog for JSON output with timestamps and log levels.

    Outputs to:
    - stderr (unbuffered — worker threads flush immediately)
    - engine.log file (persistent record)
    """
    # File handler for persistent log.
    file_handler = logging.FileHandler("engine.log", mode="a")
    file_handler.setLevel(logging.DEBUG)

    # stderr handler.
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.DEBUG)

    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG,
        handlers=[stderr_handler, file_handler],
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(0),
        cache_logger_on_first_use=False,
    )
