"""Idempotent stderr logging in text or JSON format."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Literal


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str, log_format: Literal["text", "json"] = "text") -> None:
    """Replace root handlers, never write operational logs to stdout."""
    numeric_level = logging.getLevelNamesMapping().get(level.upper())
    if numeric_level is None:
        raise ValueError("Unknown logging level")
    if log_format not in ("text", "json"):
        raise ValueError("Unknown logging format")
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    handler = logging.StreamHandler(sys.stderr)
    formatter: logging.Formatter = (
        JsonFormatter()
        if log_format == "json"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(numeric_level)
    for name in ("httpx", "httpcore", "urllib3", "asyncio", "kaggle", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)
