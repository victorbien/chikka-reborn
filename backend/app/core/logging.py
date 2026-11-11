import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.request_context import get_request_id

# Attributes every LogRecord has; anything else was passed via `extra=`.
_STANDARD_ATTRIBUTES = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    # color_message is uvicorn's ANSI duplicate of message.
    | {"message", "asctime", "color_message"}
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the request ID attached when available.

    Callers must never pass message bodies, tokens or unmasked phone numbers as extras.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRIBUTES:
                payload[key] = value
        if record.exc_info:
            # Type only: tracebacks can embed user data and must not reach shared logs.
            payload["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Route uvicorn through the same JSON handler; we log requests ourselves.
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers = []
    access.propagate = False
