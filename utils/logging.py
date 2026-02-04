"""
Structured logging: JSON for cloud aggregators, readable format for dev.
Configured from env (LOG_LEVEL, LOG_JSON).
"""

import logging
import sys
from typing import Any

from core.config import get_settings


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger with app-level config applied.
    Use logger.info("event", extra={"key": "value"}) for structured fields.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, get_settings().LOG_LEVEL.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)
    if get_settings().LOG_JSON:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON for CloudWatch, Datadog, etc."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Merge extra dict into top level for structured search
        for key, value in record.__dict__.items():
            if key not in ("name", "msg", "args", "created", "filename", "funcName", "levelname", "levelno", "lineno", "module", "msecs", "pathname", "process", "processName", "relativeCreated", "stack_info", "exc_info", "message", "taskName"):
                log_obj[key] = value
        return json.dumps(log_obj, default=str)
