"""Structured JSON logging for radivault_fulfillment (dev-spec FR-82).

Banned fields from dev-spec §6.8: PHI + API keys + raw idempotency keys +
raw presigned URL signatures. Mirrors search's strict sanitizer with the
additional fulfillment-specific fields.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from pythonjsonlogger import json as jsonlogger

SERVICE_NAME = "radivault-fulfillment"

# dev-spec §6.8 banned fields.
BANNED_FIELDS = {
    # PHI
    "patient_name",
    "patient_id",
    "patient_birthdate",
    "original_study_uid",
    "original_series_uid",
    "original_sop_uid",
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPInstanceUID",
    "FrameOfReferenceUID",
    "pacs_host",
    "pacs_ip",
    # Fulfillment-specific bans.
    "api_key",
    "api_key_kid",
    "token_plaintext",
    "bearer_token",
    "idempotency_key_raw",
    "presigned_url_raw",
    "presigned_url",
}


class PhiSanitizerFilter(logging.Filter):
    """Drop/redact log records carrying forbidden fields (FR-82 strict)."""

    def filter(self, record: logging.LogRecord) -> bool:
        payload = record.__dict__
        for banned in BANNED_FIELDS:
            if banned in payload and payload[banned] not in (None, ""):
                record.msg = f"PHI_SANITIZED banned_field={banned}"
                for k in list(payload.keys()):
                    if k in BANNED_FIELDS:
                        payload[k] = "<redacted>"
                record.event = "log.phi_sanitized"
                return True
        return True


class RadivaultJsonFormatter(jsonlogger.JsonFormatter):
    """Fixed field order + service/ts fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        from datetime import UTC, datetime

        now = datetime.now(tz=UTC)
        log_record["ts"] = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        log_record["level"] = record.levelname
        log_record["service"] = SERVICE_NAME
        log_record["logger"] = record.name
        if "message" in log_record and "msg" not in log_record:
            log_record["msg"] = log_record["message"]


def configure_logging(level: str = "INFO", *, json_logs: bool = True) -> None:
    effective_level = (os.environ.get("RV_FULFILLMENT_LOG_LEVEL") or level).upper()
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

    for noisy in ("uvicorn.error", "uvicorn.access", "botocore", "urllib3"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))
