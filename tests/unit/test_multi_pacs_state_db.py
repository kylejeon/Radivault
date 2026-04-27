"""Multi-PACS sync — state DB migration tests (FR-MPS-9).

Covers the ``uid_map.pacs_id`` column added by ``StateDB._migrate``:

- Fresh DB has the column + index.
- Legacy DB (pre-MPS) gains the column on next open without losing data.
- ``upsert_uid_map(..., pacs_id=...)`` records the source endpoint id.
- Re-running the migration on an already-migrated DB is a no-op
  (idempotent — guards against double-ALTER on container restart).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from radivault_gateway.state import StateDB


def test_fresh_db_has_pacs_id_column_and_index(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    cols = {
        row["name"]
        for row in db._conn.execute("PRAGMA table_info('uid_map')").fetchall()
    }
    assert "pacs_id" in cols
    indexes = {
        row["name"]
        for row in db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='uid_map'"
        ).fetchall()
    }
    assert "idx_uid_map_pacs" in indexes
    db.close()


def test_legacy_db_gains_pacs_id_on_open(tmp_path: Path) -> None:
    """Simulate a pre-MPS uid_map (no pacs_id column) and verify the
    migration adds the column without losing existing rows."""
    path = tmp_path / "legacy.sqlite3"
    legacy_conn = sqlite3.connect(path)
    legacy_conn.executescript(
        """
        CREATE TABLE uid_map (
            original_uid TEXT PRIMARY KEY,
            pseudo_uid TEXT NOT NULL UNIQUE,
            uid_kind TEXT NOT NULL,
            salt_version INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO uid_map VALUES
            ('1.2.840.original.legacy', '2.25.pseudo', 'study', 1, '2026-04-26T00:00:00Z');
        """
    )
    legacy_conn.commit()
    legacy_conn.close()

    # Open with the new StateDB → migration runs.
    db = StateDB(path)
    cols = {
        row["name"]
        for row in db._conn.execute("PRAGMA table_info('uid_map')").fetchall()
    }
    assert "pacs_id" in cols
    # Legacy row preserved with NULL pacs_id (no fake backfill).
    rows = db._conn.execute(
        "SELECT original_uid, pseudo_uid, pacs_id FROM uid_map"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["pacs_id"] is None
    assert rows[0]["original_uid"] == "1.2.840.original.legacy"
    db.close()


def test_upsert_uid_map_records_pacs_id(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.sqlite3")
    db.upsert_uid_map(
        "1.2.840.orig.a",
        "2.25.pseudo.a",
        kind="study",
        salt_version=1,
        pacs_id="orthanc-a",
    )
    db.upsert_uid_map(
        "1.2.840.orig.b",
        "2.25.pseudo.b",
        kind="study",
        salt_version=1,
        pacs_id="orthanc-b",
    )
    rows = {
        row["original_uid"]: row["pacs_id"]
        for row in db._conn.execute(
            "SELECT original_uid, pacs_id FROM uid_map ORDER BY original_uid"
        ).fetchall()
    }
    assert rows == {
        "1.2.840.orig.a": "orthanc-a",
        "1.2.840.orig.b": "orthanc-b",
    }
    db.close()


def test_upsert_uid_map_legacy_call_omits_pacs_id(tmp_path: Path) -> None:
    """Callers that don't pass pacs_id (legacy DeidEngine without the
    multi-PACS context) must produce NULL — preserving the migration
    invariant that NULL means "pre-MPS or unattributed"."""
    db = StateDB(tmp_path / "state.sqlite3")
    db.upsert_uid_map(
        "1.2.840.orig", "2.25.pseudo", kind="study", salt_version=1
    )
    row = db._conn.execute(
        "SELECT pacs_id FROM uid_map WHERE original_uid=?",
        ("1.2.840.orig",),
    ).fetchone()
    assert row["pacs_id"] is None
    db.close()


def test_upsert_uid_map_first_write_wins(tmp_path: Path) -> None:
    """Same original_uid from two PACS endpoints (cross-PACS overlap, K-MPS-2):
    the first write keeps its pacs_id; subsequent writes are no-ops."""
    db = StateDB(tmp_path / "state.sqlite3")
    db.upsert_uid_map(
        "1.2.840.shared",
        "2.25.pseudo.shared",
        kind="study",
        salt_version=1,
        pacs_id="orthanc-a",
    )
    # Second call with a different pacs_id — ON CONFLICT DO NOTHING.
    db.upsert_uid_map(
        "1.2.840.shared",
        "2.25.pseudo.shared",
        kind="study",
        salt_version=1,
        pacs_id="orthanc-b",
    )
    row = db._conn.execute(
        "SELECT pacs_id FROM uid_map WHERE original_uid=?",
        ("1.2.840.shared",),
    ).fetchone()
    assert row["pacs_id"] == "orthanc-a"
    db.close()


def test_migration_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    db1 = StateDB(path)
    db1.upsert_uid_map(
        "1.2.840.orig", "2.25.pseudo", kind="study", salt_version=1, pacs_id="p1"
    )
    db1.close()

    # Re-open should NOT error or duplicate columns / indexes.
    db2 = StateDB(path)
    cols = [
        row["name"]
        for row in db2._conn.execute("PRAGMA table_info('uid_map')").fetchall()
    ]
    # No duplicate pacs_id column.
    assert cols.count("pacs_id") == 1
    db2.close()
