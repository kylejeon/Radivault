"""SQLite state database (dev-spec §6.1).

Schema is created on first open (idempotent). WAL mode + ``PRAGMA
foreign_keys=ON``. Connections are created per-thread via :mod:`sqlite3`'s
``check_same_thread=False`` — callers must serialise writes themselves; for
the v0.1 orchestrator the pipeline is single-threaded per study.
"""

from __future__ import annotations

import enum
import hashlib
import sqlite3
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_identity (
    gateway_id     TEXT PRIMARY KEY,
    hospital_id    TEXT NOT NULL,
    org_root_oid   TEXT NOT NULL,
    salt_version   INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS uid_map (
    original_uid   TEXT PRIMARY KEY,
    pseudo_uid     TEXT NOT NULL UNIQUE,
    uid_kind       TEXT NOT NULL,
    salt_version   INTEGER NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_uid_map_pseudo ON uid_map(pseudo_uid);

CREATE TABLE IF NOT EXISTS patient_date_offset (
    patient_id_hash TEXT PRIMARY KEY,
    offset_days     INTEGER NOT NULL,
    salt_version    INTEGER NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_job (
    pseudo_study_uid          TEXT PRIMARY KEY,
    state                     TEXT NOT NULL,
    modalities                TEXT,
    n_instances               INTEGER,
    n_bytes                   INTEGER,
    first_seen_at             TEXT NOT NULL,
    deided_at                 TEXT,
    uploaded_at               TEXT,
    last_error                TEXT,
    retry_count               INTEGER NOT NULL DEFAULT 0,
    central_job_id            TEXT,
    original_study_uid_hash   TEXT
);
CREATE INDEX IF NOT EXISTS idx_study_job_state ON study_job(state);
CREATE INDEX IF NOT EXISTS idx_study_job_first_seen ON study_job(first_seen_at);
-- idx_study_job_original_hash is created in _migrate() after the
-- ``original_study_uid_hash`` column is guaranteed present (handles both
-- fresh DBs and legacy DBs that predate the column).

CREATE TABLE IF NOT EXISTS quarantine (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    pseudo_study_uid  TEXT NOT NULL,
    pseudo_sop_uid    TEXT,
    reason            TEXT NOT NULL,
    payload_path      TEXT NOT NULL,
    flagged_at        TEXT NOT NULL,
    reviewed          INTEGER NOT NULL DEFAULT 0,
    reviewer_note     TEXT
);

CREATE TABLE IF NOT EXISTS upload_retry (
    pseudo_study_uid  TEXT PRIMARY KEY REFERENCES study_job(pseudo_study_uid),
    next_attempt_at   TEXT NOT NULL,
    attempt_count     INTEGER NOT NULL DEFAULT 0
);

-- v0.2 de-id-pixel: structured pixel stage events (dev-spec §6.2, FR-39).
-- Forbidden columns per FR-38: plaintext OCR text, absolute pixel coords,
-- original SOP/patient identifiers.
CREATE TABLE IF NOT EXISTS pixel_audit_event (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    pseudo_study_uid     TEXT NOT NULL,
    sop_instance_uid     TEXT,
    op                   TEXT NOT NULL,
    outcome              TEXT NOT NULL,
    library              TEXT,
    library_version      TEXT,
    duration_ms          INTEGER,
    box_count            INTEGER,
    avg_confidence       REAL,
    min_confidence       REAL,
    max_confidence       REAL,
    removed_voxel_ratio  REAL,
    reason               TEXT,
    audit_seq            INTEGER,
    created_at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pixel_audit_study   ON pixel_audit_event(pseudo_study_uid);
CREATE INDEX IF NOT EXISTS idx_pixel_audit_op      ON pixel_audit_event(op);
CREATE INDEX IF NOT EXISTS idx_pixel_audit_outcome ON pixel_audit_event(outcome);
CREATE INDEX IF NOT EXISTS idx_pixel_audit_created ON pixel_audit_event(created_at);

CREATE TABLE IF NOT EXISTS schema_version (
    id  INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);
INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 1);
"""


class StudyState(enum.StrEnum):
    QUEUED = "queued"
    FETCHING = "fetching"
    FETCHED = "fetched"
    DEIDING = "deiding"
    DEIDED = "deided"
    QUARANTINED = "quarantined"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED_FETCH = "failed_fetch"
    FAILED_DEID = "failed_deid"
    FAILED_REVERIFY = "failed_reverify"
    FAILED_UPLOAD = "failed_upload"
    # v0.2 de-id-pixel extension (dev-spec §6.1, FR-32).
    PIXEL_PROCESSING = "pixel_processing"
    PIXEL_DEIDED = "pixel_deided"
    PIXEL_FAILED = "pixel_failed"


def _utcnow() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_original_uid(original_uid: str) -> str:
    """16-char SHA-256 prefix of the original Study Instance UID.

    Used as a Gateway-only short-circuit key so we can decide whether a study
    has already been uploaded to Central without reversing the one-way pseudo
    UID derivation. The 16-char prefix is collision-safe at any realistic
    Gateway scale (2^32 studies before a 50% collision chance) while staying
    small enough for a compact sqlite index.
    """
    return hashlib.sha256(original_uid.encode("utf-8")).hexdigest()[:16]


class StateDB:
    """Facade over the SQLite state database.

    Intentionally thin — business logic lives in the orchestrator. The DB is
    created on first use; the caller supplies a path.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript("PRAGMA journal_mode=WAL;\nPRAGMA foreign_keys=ON;\n" + SCHEMA)
            # gateway-sync-skip-uploaded: ensure the ``original_study_uid_hash``
            # column exists on legacy DBs (pre-migration) before we declare the
            # index on it. On fresh DBs the column is already in SCHEMA; on
            # legacy DBs we ALTER TABLE to add it NULLable — backfill is
            # intentionally skipped (the pseudo UID is one-way, we cannot
            # recover the original Study Instance UID from it).
            existing_cols = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info('study_job')").fetchall()
            }
            if "original_study_uid_hash" not in existing_cols:
                self._conn.execute(
                    "ALTER TABLE study_job ADD COLUMN original_study_uid_hash TEXT"
                )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_study_job_original_hash "
                "ON study_job(original_study_uid_hash)"
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- agent identity ----

    def set_agent_identity(
        self,
        *,
        gateway_id: str,
        hospital_id: str,
        org_root_oid: str,
        salt_version: int,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO agent_identity
                    (gateway_id, hospital_id, org_root_oid, salt_version, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(gateway_id) DO UPDATE SET
                    hospital_id=excluded.hospital_id,
                    org_root_oid=excluded.org_root_oid,
                    salt_version=excluded.salt_version
                """,
                (gateway_id, hospital_id, org_root_oid, salt_version, _utcnow()),
            )

    def get_agent_identity(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM agent_identity LIMIT 1").fetchone()
        return dict(row) if row else None

    # ---- uid map ----

    def upsert_uid_map(
        self, original_uid: str, pseudo_uid: str, *, kind: str, salt_version: int
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO uid_map (original_uid, pseudo_uid, uid_kind, salt_version, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(original_uid) DO NOTHING
                """,
                (original_uid, pseudo_uid, kind, salt_version, _utcnow()),
            )

    def lookup_pseudo_uid(self, original_uid: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT pseudo_uid FROM uid_map WHERE original_uid = ?",
                (original_uid,),
            ).fetchone()
        return row["pseudo_uid"] if row else None

    # ---- patient offset ----

    def upsert_patient_offset(
        self, patient_id_hash: str, offset_days: int, *, salt_version: int
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO patient_date_offset
                    (patient_id_hash, offset_days, salt_version, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(patient_id_hash) DO NOTHING
                """,
                (patient_id_hash, offset_days, salt_version, _utcnow()),
            )

    def lookup_patient_offset(self, patient_id_hash: str) -> int | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT offset_days FROM patient_date_offset WHERE patient_id_hash = ?",
                (patient_id_hash,),
            ).fetchone()
        return int(row["offset_days"]) if row else None

    # ---- study job ----

    def upsert_study_job(
        self,
        pseudo_study_uid: str,
        *,
        state: StudyState,
        modalities: Iterable[str] | None = None,
        n_instances: int | None = None,
        n_bytes: int | None = None,
        last_error: str | None = None,
        central_job_id: str | None = None,
    ) -> None:
        modalities_str = ",".join(sorted(set(modalities))) if modalities is not None else None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO study_job (
                    pseudo_study_uid, state, modalities, n_instances, n_bytes,
                    first_seen_at, last_error, central_job_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pseudo_study_uid) DO UPDATE SET
                    state=excluded.state,
                    modalities=COALESCE(excluded.modalities, study_job.modalities),
                    n_instances=COALESCE(excluded.n_instances, study_job.n_instances),
                    n_bytes=COALESCE(excluded.n_bytes, study_job.n_bytes),
                    last_error=excluded.last_error,
                    central_job_id=COALESCE(excluded.central_job_id, study_job.central_job_id)
                """,
                (
                    pseudo_study_uid,
                    state.value,
                    modalities_str,
                    n_instances,
                    n_bytes,
                    _utcnow(),
                    last_error,
                    central_job_id,
                ),
            )

    def mark_state(
        self,
        pseudo_study_uid: str,
        state: StudyState,
        *,
        last_error: str | None = None,
        original_uid: str | None = None,
    ) -> None:
        """Update the state column (and timestamp columns) for a study_job row.

        When ``original_uid`` is supplied we also persist its 16-char SHA-256
        hash so a later ``is_study_uploaded()`` lookup can short-circuit the
        fetch/de-id work. Callers should supply ``original_uid`` whenever they
        have it available — most importantly on the UPLOADED transition — so
        the skip check survives Gateway restarts. Other transitions tolerate
        the extra bookkeeping harmlessly (UPDATE-with-COALESCE preserves an
        existing hash if this call omits it).
        """
        ts_field_map = {
            StudyState.DEIDED: "deided_at",
            StudyState.UPLOADED: "uploaded_at",
        }
        now = _utcnow()
        orig_hash = _hash_original_uid(original_uid) if original_uid is not None else None
        with self._lock:
            if state in ts_field_map:
                field = ts_field_map[state]
                self._conn.execute(
                    f"UPDATE study_job SET state=?, {field}=?, last_error=?, "
                    "original_study_uid_hash=COALESCE(?, original_study_uid_hash) "
                    "WHERE pseudo_study_uid=?",
                    (state.value, now, last_error, orig_hash, pseudo_study_uid),
                )
            else:
                self._conn.execute(
                    "UPDATE study_job SET state=?, last_error=?, "
                    "original_study_uid_hash=COALESCE(?, original_study_uid_hash) "
                    "WHERE pseudo_study_uid=?",
                    (state.value, last_error, orig_hash, pseudo_study_uid),
                )

    def is_study_uploaded(self, original_study_uid: str) -> bool:
        """Return True when this original Study Instance UID has a completed
        UPLOADED row in the state DB.

        Looks up by 16-char SHA-256 prefix (same hash scheme ``mark_state``
        writes). Rows where ``original_study_uid_hash`` is NULL — typically
        rows persisted before this column existed — are treated as "unknown"
        and will be re-processed on the first run after the migration. This
        is intentional: we cannot reverse the pseudo UID to backfill the
        hash, so existing rows pay a one-off re-fetch cost and skip works
        from the second run onwards (§8 dev-spec notes).
        """
        key = _hash_original_uid(original_study_uid)
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM study_job "
                "WHERE original_study_uid_hash = ? AND state = ? LIMIT 1",
                (key, StudyState.UPLOADED.value),
            ).fetchone()
        return row is not None

    def increment_retry(self, pseudo_study_uid: str) -> int:
        with self._lock:
            self._conn.execute(
                "UPDATE study_job SET retry_count = retry_count + 1 WHERE pseudo_study_uid = ?",
                (pseudo_study_uid,),
            )
            row = self._conn.execute(
                "SELECT retry_count FROM study_job WHERE pseudo_study_uid = ?",
                (pseudo_study_uid,),
            ).fetchone()
        return int(row["retry_count"]) if row else 0

    def get_study_job(self, pseudo_study_uid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM study_job WHERE pseudo_study_uid = ?",
                (pseudo_study_uid,),
            ).fetchone()
        return dict(row) if row else None

    def list_study_jobs(
        self, *, state: StudyState | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._lock:
            if state is None:
                rows = self._conn.execute(
                    "SELECT * FROM study_job ORDER BY first_seen_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM study_job WHERE state = ? ORDER BY first_seen_at DESC LIMIT ?",
                    (state.value, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def counts_by_state(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT state, COUNT(*) as n FROM study_job GROUP BY state"
            ).fetchall()
        return {row["state"]: int(row["n"]) for row in rows}

    # ---- quarantine ----

    def add_quarantine(
        self,
        pseudo_study_uid: str,
        *,
        reason: str,
        payload_path: str,
        pseudo_sop_uid: str | None = None,
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO quarantine
                    (pseudo_study_uid, pseudo_sop_uid, reason, payload_path, flagged_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (pseudo_study_uid, pseudo_sop_uid, reason, payload_path, _utcnow()),
            )
        return int(cursor.lastrowid or 0)

    # ---- upload retry ----

    def schedule_retry(self, pseudo_study_uid: str, next_attempt_at: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO upload_retry (pseudo_study_uid, next_attempt_at, attempt_count)
                VALUES (?, ?, 1)
                ON CONFLICT(pseudo_study_uid) DO UPDATE SET
                    next_attempt_at = excluded.next_attempt_at,
                    attempt_count = upload_retry.attempt_count + 1
                """,
                (pseudo_study_uid, next_attempt_at),
            )

    def clear_retry(self, pseudo_study_uid: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM upload_retry WHERE pseudo_study_uid = ?",
                (pseudo_study_uid,),
            )

    # ---- pixel audit (v0.2) ----

    def add_pixel_audit_event(
        self,
        *,
        pseudo_study_uid: str,
        op: str,
        outcome: str,
        sop_instance_uid: str | None = None,
        library: str | None = None,
        library_version: str | None = None,
        duration_ms: int | None = None,
        box_count: int | None = None,
        avg_confidence: float | None = None,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        removed_voxel_ratio: float | None = None,
        reason: str | None = None,
        audit_seq: int | None = None,
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO pixel_audit_event (
                    pseudo_study_uid, sop_instance_uid, op, outcome,
                    library, library_version, duration_ms,
                    box_count, avg_confidence, min_confidence, max_confidence,
                    removed_voxel_ratio, reason, audit_seq, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pseudo_study_uid,
                    sop_instance_uid,
                    op,
                    outcome,
                    library,
                    library_version,
                    duration_ms,
                    box_count,
                    avg_confidence,
                    min_confidence,
                    max_confidence,
                    removed_voxel_ratio,
                    reason,
                    audit_seq,
                    _utcnow(),
                ),
            )
        return int(cursor.lastrowid or 0)

    def list_pixel_audit_events(
        self,
        *,
        pseudo_study_uid: str | None = None,
        op: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock:
            sql = "SELECT * FROM pixel_audit_event"
            params: list[Any] = []
            clauses: list[str] = []
            if pseudo_study_uid is not None:
                clauses.append("pseudo_study_uid = ?")
                params.append(pseudo_study_uid)
            if op is not None:
                clauses.append("op = ?")
                params.append(op)
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def pixel_counts_by_outcome(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT outcome, COUNT(*) as n FROM pixel_audit_event GROUP BY outcome"
            ).fetchall()
        return {row["outcome"]: int(row["n"]) for row in rows}
