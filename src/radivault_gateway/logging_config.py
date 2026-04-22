"""Structured logging configuration for the gateway.

Design-spec §5 mandates two streams: a console/app log (human or JSON) and a
separate hash-chained audit log. This module covers the console/app stream.
Audit is handled by :mod:`radivault_gateway.audit`.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record on a single line.

    Field order: ts, level, logger, event, ...extras. PHI fields (original UIDs,
    plaintext patient_id, patient name, PACS internal hostnames) are forbidden
    per dev-spec §12.5 — callers are responsible.
    """

    _RESERVED = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )[:-4] + "Z"
        # Strip the trailing 'Z' double; above trick produces e.g. 2026-04-22T01:03:22.341Z
        ts = ts.replace("ZZ", "Z")
        payload: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class HumanFormatter(logging.Formatter):
    """Human-readable line formatter matching design-spec §5.2."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        level = record.levelname.ljust(5)
        logger = record.name.ljust(22)
        return f"{ts}  {level}  {logger}  {record.getMessage()}"


def configure_logging(*, level: str = "INFO", json_output: bool = False) -> None:
    """Idempotently configure the root logger for the gateway process.

    Subsequent calls replace handlers so that CLI ``--log-level`` overrides win.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())
    for existing in list(root.handlers):
        root.removeHandler(existing)
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(JsonFormatter() if json_output else HumanFormatter())
    root.addHandler(handler)
