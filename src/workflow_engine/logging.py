"""Structured logging configuration for the workflow engine.

Provides: configure_logging.
"""

from __future__ import annotations

import structlog


def configure_logging() -> None:
    """Configure structlog for JSON output with timestamps and log levels.

    Sets up:
    - ISO-format timestamps
    - Log level in output
    - JSON rendering
    - PrintLogger factory (writes to stdout)
    - Filtering bound logger at DEBUG level and above
    """
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(0),
        cache_logger_on_first_use=False,
    )
