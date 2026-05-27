"""Structured logging configuration.

JSON output by default — one line per event, machine-parseable.
Set CHANGEBOOK_LOG_FORMAT=text for human-readable output during development.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge structured fields passed via `extra=`
        for key in ("change_id", "actor", "action", "detail"):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        return json.dumps(entry)


def configure_logging() -> None:
    """Call once at startup to wire up the root logger."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Remove any existing handlers (e.g. from uvicorn defaults)
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s  %(message)s"))

    root.addHandler(handler)

    # Quiet noisy libraries — only our app.* loggers should be chatty
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
