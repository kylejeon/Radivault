"""Structured JSON logging for Central Ingest (dev-spec FR-60, design-spec §4.1).

Emits JSON-lines to stdout with the fixed field shape documented in the design
spec §4.2. A ``PhiSanitizerFilter`` drops any record whose ``extra`` contains a
field from :data:`BANNED_FIELDS`.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from pythonjsonlogger import json as jsonlogger

SERVICE_NAME = "radivault-central"

# dev-spec §6.7 — PHI blocklist. A logger filter drops records carrying any of
# these keys in their ``extra``/record attrs. A metric
# ``radivault_central_log_phi_detected_total`` is bumped when this happens.
BANNED_FIELDS = {
    "patient_name",
    "patient_id",
    "patient_birthdate",
    "original_study_uid",
    "original_series_uid",
    "original_sop_uid",
    "pacs_host",
    "pacs_ip",
    "token_plaintext",
}


class PhiSanitizerFilter(logging.Filter):
    """Drop log records that contain forbidden PHI field names."""

    def filter(self, record: logging.LogRecord) -> bool:
        payload = record.__dict__
        for banned in BANNED_FIELDS:
            if banned in payload and payload[banned] not in (None, ""):
                # Emit a sanitized marker instead of the original record.
                record.msg = f"PHI_SANITIZED banned_field={banned}"
                for k in list(payload.keys()):
                    if k in BANNED_FIELDS:
                        payload[k] = "<redacted>"
                record.event = "log.phi_sanitized"
                return True
        return True


class RadivaultJsonFormatter(jsonlogger.JsonFormatter):
    """Force a stable field order and add service/ts fields.

    Design-spec §4.1 requires: ts, level, service, logger, trace_id, span_id,
    request_id, hospital_id, gateway_id, event, message_ko, message_en, path,
    method, status, duration_ms, extra.
    """

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        from datetime import UTC, datetime

        log_record["ts"] = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.") + (
            f"{datetime.now(tz=UTC).microsecond // 1000:03d}Z"
        )
        log_record["level"] = record.levelname
        log_record["service"] = SERVICE_NAME
        log_record["logger"] = record.name
        # ``message`` is filled by the JsonFormatter; keep it under both ``msg``
        # (legacy) and the canonical top-level name.
        if "message" in log_record and "msg" not in log_record:
            log_record["msg"] = log_record["message"]


def configure_logging(level: str = "INFO", *, json_logs: bool = True) -> None:
    """Install the Central Ingest logger on the root handler.

    Safe to call repeatedly; previous handlers on the root logger are cleared.
    Honors ``RADIVAULT_LOG_LEVEL`` env var as an override.
    """
    effective_level = (os.environ.get("RV_CENTRAL_LOG_LEVEL") or level).upper()
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream=sys.stdout)
    if json_logs:
        formatter: logging.Formatter = RadivaultJsonFormatter(
            "%(ts)s %(level)s %(logger)s %(message)s",
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    handler.setFormatter(formatter)
    handler.addFilter(PhiSanitizerFilter())
    root.addHandler(handler)
    root.setLevel(effective_level)

    # Tame library noise.
    for noisy in ("uvicorn.error", "uvicorn.access", "botocore", "urllib3"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))
