"""JSON-lines audit log with SHA-256 hash chain.

Implements FR-22..FR-27 (dev-spec §4.5). Each record is canonicalised with
``json.dumps(..., sort_keys=True, separators=(",",":"), ensure_ascii=False)``
and the hash covers every field except ``hash`` itself. ``prev_hash`` for
seq=0 is the all-zero sentinel.

All reads/writes are synchronous and append-only. Callers serialise access via
:class:`AuditLogger` which uses a lock; concurrent writers on the same file are
not supported (documented constraint).
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS_PREV_HASH = "sha256:" + "0" * 64


def canonicalize(record: dict[str, Any]) -> str:
    """Produce the canonical JSON string that feeds the chain hash.

    Excludes the ``hash`` field (which is the output). Spec: FR-23.
    """
    filtered = {k: v for k, v in record.items() if k != "hash"}
    return json.dumps(filtered, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(record_without_hash: dict[str, Any]) -> str:
    canonical = canonicalize(record_without_hash)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _utc_now_iso() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass
class AuditRecord:
    seq: int
    ts: str
    gateway_id: str
    actor: str
    event: str
    target: dict[str, Any] | None
    meta: dict[str, Any]
    prev_hash: str
    hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "gateway_id": self.gateway_id,
            "actor": self.actor,
            "event": self.event,
            "target": self.target,
            "meta": self.meta,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }


@dataclass
class VerifyResult:
    ok: bool
    lines: int
    head_seq: int | None = None
    head_hash: str | None = None
    first_mismatch_seq: int | None = None
    expected_prev_hash: str | None = None
    actual_prev_hash: str | None = None
    error: str | None = None


class AuditLogger:
    """Append-only audit log writer with SHA-256 hash chain.

    Thread-safe via :class:`threading.Lock`. On first open the latest seq/hash
    are recovered by scanning the last line of the existing file.
    """

    def __init__(self, path: str | Path, *, gateway_id: str, actor: str = "gateway") -> None:
        self.path = Path(path)
        self.gateway_id = gateway_id
        self.actor = actor
        self._lock = threading.Lock()
        self._next_seq, self._prev_hash = self._recover_state()

    def _recover_state(self) -> tuple[int, str]:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch(mode=0o600, exist_ok=True)
            return 0, GENESIS_PREV_HASH
        last: dict[str, Any] | None = None
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                last = json.loads(line)
        if last is None:
            return 0, GENESIS_PREV_HASH
        return int(last["seq"]) + 1, last["hash"]

    @property
    def head_seq(self) -> int:
        return self._next_seq - 1

    @property
    def head_hash(self) -> str:
        return self._prev_hash

    def append(
        self,
        event: str,
        *,
        target: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        ts: str | None = None,
    ) -> AuditRecord:
        """Append a single event with a fresh seq and hash. FR-22/23/24."""
        with self._lock:
            record = AuditRecord(
                seq=self._next_seq,
                ts=ts or _utc_now_iso(),
                gateway_id=self.gateway_id,
                actor=self.actor,
                event=event,
                target=target,
                meta=meta or {},
                prev_hash=self._prev_hash,
            )
            record.hash = compute_hash(record.to_dict())
            line = json.dumps(
                record.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            # Write then fsync for durability; file permission 0600 (FR-27).
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            fd = os.open(self.path, flags, 0o600)
            try:
                os.write(fd, line.encode("utf-8") + b"\n")
                os.fsync(fd)
            finally:
                os.close(fd)
            self._next_seq += 1
            self._prev_hash = record.hash
            return record


def verify_chain(path: str | Path) -> VerifyResult:
    """Re-hash every line and validate the SHA-256 chain (FR-26).

    Returns :class:`VerifyResult` with ``ok`` true when every line's prev_hash
    matches the preceding line's hash and every hash recomputes correctly.
    The first mismatch (if any) is reported.
    """
    path = Path(path)
    if not path.exists():
        return VerifyResult(ok=False, lines=0, error=f"file not found: {path}")
    prev_hash = GENESIS_PREV_HASH
    count = 0
    head_seq: int | None = None
    head_hash: str | None = None
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                count += 1
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    return VerifyResult(
                        ok=False,
                        lines=count,
                        first_mismatch_seq=head_seq + 1 if head_seq is not None else 0,
                        error=f"invalid JSON at line {count}: {exc}",
                    )
                expected_prev = prev_hash
                if record.get("prev_hash") != expected_prev:
                    return VerifyResult(
                        ok=False,
                        lines=count,
                        first_mismatch_seq=record.get("seq"),
                        expected_prev_hash=expected_prev,
                        actual_prev_hash=record.get("prev_hash"),
                    )
                recomputed = compute_hash(record)
                if recomputed != record.get("hash"):
                    return VerifyResult(
                        ok=False,
                        lines=count,
                        first_mismatch_seq=record.get("seq"),
                        expected_prev_hash=record.get("hash"),
                        actual_prev_hash=recomputed,
                        error="content hash does not match",
                    )
                prev_hash = record["hash"]
                head_seq = record["seq"]
                head_hash = record["hash"]
    except OSError as exc:
        return VerifyResult(ok=False, lines=count, error=str(exc))
    return VerifyResult(ok=True, lines=count, head_seq=head_seq, head_hash=head_hash)
