"""Audit log hash chain tests — FR-22..FR-27."""

from __future__ import annotations

import json
from pathlib import Path

from radivault_gateway.audit import (
    GENESIS_PREV_HASH,
    AuditLogger,
    canonicalize,
    compute_hash,
    verify_chain,
)


def test_genesis_prev_hash_is_all_zero() -> None:
    assert GENESIS_PREV_HASH == "sha256:" + "0" * 64


def test_append_and_verify_ok(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    logger = AuditLogger(path, gateway_id="gw_x")
    logger.append("agent.started", meta={"version": "0.1.0"})
    logger.append("pacs.query", meta={"returned": 3})
    logger.append("upload.completed", target={"pseudo_study_uid": "2.25.x"})

    result = verify_chain(path)
    assert result.ok is True
    assert result.lines == 3
    assert result.head_seq == 2


def test_first_line_genesis_prev_hash(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    logger = AuditLogger(path, gateway_id="gw_x")
    logger.append("agent.started")
    first = json.loads(path.read_text().splitlines()[0])
    assert first["prev_hash"] == GENESIS_PREV_HASH


def test_tampering_detected(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    logger = AuditLogger(path, gateway_id="gw_x")
    for i in range(5):
        logger.append(f"event.{i}", meta={"i": i})
    lines = path.read_text().splitlines()
    # Corrupt the middle line's meta.
    victim = json.loads(lines[2])
    victim["meta"]["i"] = 999
    # Don't recompute hash → chain should break at seq=2
    lines[2] = json.dumps(victim, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")
    result = verify_chain(path)
    assert result.ok is False
    assert result.first_mismatch_seq == 2


def test_hash_covers_all_fields_except_hash(tmp_path: Path) -> None:
    record = {
        "seq": 0,
        "ts": "2026-04-22T00:00:00.000Z",
        "gateway_id": "gw_x",
        "actor": "gateway",
        "event": "agent.started",
        "target": None,
        "meta": {"version": "0.1.0"},
        "prev_hash": GENESIS_PREV_HASH,
        "hash": "sha256:dummy",
    }
    # Canonical form excludes the hash field itself.
    canonical = canonicalize(record)
    assert '"hash"' not in canonical
    # Recomputing yields the same hex regardless of the stored hash value.
    h1 = compute_hash(record)
    record["hash"] = "anything-else"
    h2 = compute_hash(record)
    assert h1 == h2


def test_recovery_after_reopen(tmp_path: Path) -> None:
    path = tmp_path / "audit.log"
    first_logger = AuditLogger(path, gateway_id="gw_x")
    first_logger.append("a")
    first_logger.append("b")
    # Simulate restart: new logger reads existing file tail.
    second_logger = AuditLogger(path, gateway_id="gw_x")
    second_logger.append("c")
    assert verify_chain(path).ok is True
    assert verify_chain(path).lines == 3


def test_verify_missing_file(tmp_path: Path) -> None:
    result = verify_chain(tmp_path / "nope.log")
    assert result.ok is False
