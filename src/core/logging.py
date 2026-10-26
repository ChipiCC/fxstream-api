"""Structured logging configuration built on top of structlog."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
]


def configure_logging(*, log_level: str = "INFO", json_logs: bool = True) -> None:
    """Configure stdlib logging + structlog for the whole application.

    Call this once during application startup. The stdlib root logger is
    redirected through structlog so third-party logs share the same formatting.
    """

    def _add_stdlib_fields(
        _logger: Any, _method: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        record = event_dict.get("_record")
        if record is not None:
            event_dict.setdefault("logger", record.name)
            event_dict.setdefault("level", record.levelname)
        return event_dict

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    shared_processors = [*_SHARED_PROCESSORS, _add_stdlib_fields]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

    # Tame noisy third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine.Engine"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
