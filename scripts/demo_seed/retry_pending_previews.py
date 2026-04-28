"""Retry stuck preview pipelines for series.preview_status='pending'.

Today's multi-PACS + JPG-preview rollout left a backlog of series rows
in central whose ``preview_status`` is still ``pending`` because the
original ingest hit one of three transient defects:

  - psycopg2 not yet installed when the gateway sync ran
    (PgFrameWriter / PgAuditWriter import failure → preview block dropped)
  - RV_CENTRAL_DATABASE_URL pointing at the wrong DB user
    ("central_app" typo' before the credential fix)
  - HOSP-002 manifest stamping bug (ERR_AUTH_MISMATCH on the second
    hospital's upload — preview ran but the manifest never landed in
    central, so series.preview_status stays at 'pending')

All three faults are now fixed in code (commits 88cbd43 / 3f617fc /
…) and the underlying DICOMs are still in Orthanc. This script walks
every pending series, re-fetches the original DICOM from the right
PACS, runs the preview pipeline directly (bypasses the ingest router
because the study row already exists in central), and updates
``series.preview_status='generated'`` once frames + audit have landed.

Design constraints (Kyle approval — see retry-preview ticket):

  - ``main`` branch off-limits; everything goes in ``claude``.
  - DB UPDATE permitted (preview_status only). DELETE forbidden.
  - ``preview_pipeline.py`` / ``preview_clients.py`` core logic stays
    untouched — this script only *calls* them.
  - Idempotent: a re-run is safe; series already 'generated' are
    skipped without touching Orthanc/MinIO/DB.
  - Per-series isolation: one bad fetch never aborts the batch.

Usage::

    source scripts/demo_seed/inject_all.sh.env  # if you have one
    # or export the same vars inject_all.sh STEP 3 sets:
    export PREVIEW_PIPELINE_ENABLED=true
    export DEFACE_SIDECAR_URL=http://127.0.0.1:8090
    export RV_CENTRAL_DATABASE_URL=postgresql+psycopg://central_app:central_app@127.0.0.1:5432/central
    export RV_MINIO_ENDPOINT=http://127.0.0.1:9000
    export RV_MINIO_ACCESS_KEY=minioadmin
    export RV_MINIO_SECRET_KEY=minioadmin

    python scripts/demo_seed/retry_pending_previews.py --dry-run
    python scripts/demo_seed/retry_pending_previews.py
    python scripts/demo_seed/retry_pending_previews.py \
        --uid 2.25.140737488355328.451164170341 --verbose
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Ensure the in-repo packages are importable when running the script as
# ``python scripts/demo_seed/retry_pending_previews.py`` from the repo
# root with an activated venv that has the project installed editable.
# This mirrors the seed_buyer.py / seed_hospital.py preamble.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Side-effect import: pre-load ``radivault_gateway.deid.engine`` so that
# ``radivault_gateway.config.schema`` (imported transitively below)
# doesn't hit the partial-init circular import path:
#
#   config.__init__ → config.schema → deid.pixel.config → deid.__init__
#     → deid.engine → ``from radivault_gateway.config import RetainOptions``
#
# ``deid.engine`` only needs ``RetainOptions`` and the StateDB; importing
# it directly resolves the symbol cleanly because ``config.schema`` is
# self-contained when entered first. The CLI entrypoint sidesteps this
# by importing through ``radivault_gateway.cli`` which fixes the order.
import radivault_gateway.deid.engine  # noqa: F401 — circular-import bypass

log = logging.getLogger("demo_seed.retry_pending_previews")


# ---------------------------------------------------------------------------
# Constants — env contract + config defaults
# ---------------------------------------------------------------------------

# Required env vars; missing → exit non-zero with a clear hint.
_REQUIRED_ENV: tuple[str, ...] = (
    "RV_CENTRAL_DATABASE_URL",
    "RV_MINIO_ENDPOINT",
    "RV_MINIO_ACCESS_KEY",
    "RV_MINIO_SECRET_KEY",
)

# We don't *require* PREVIEW_PIPELINE_ENABLED at the env layer because
# the pipeline checks it internally and we want to give the operator a
# clearer message if the flag is off (see below).
_PREVIEW_FLAG_VAR = "PREVIEW_PIPELINE_ENABLED"

DEFAULT_GATEWAY_CONFIG = _REPO_ROOT / "configs" / "demo_gateway.yaml"
DEFAULT_STATE_DB = _REPO_ROOT / "demo_data" / "gateway" / "state.sqlite3"


# ---------------------------------------------------------------------------
# Result accounting
# ---------------------------------------------------------------------------


@dataclass
class StudyRetryResult:
    pseudo_study_uid: str
    hospital_id: str
    pacs_id: str | None
    n_pending_series_before: int
    n_series_processed: int = 0
    n_series_skipped: int = 0  # already 'generated' between scan and run
    n_series_quarantined: int = 0
    success: bool = False
    error: str | None = None


@dataclass
class RunSummary:
    studies_total: int = 0
    studies_success: int = 0
    studies_failed: int = 0
    series_generated: int = 0
    series_quarantined: int = 0
    results: list[StudyRetryResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Retry stuck preview pipelines for series.preview_status='pending'."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List pending studies/series without touching Orthanc/MinIO/DB.",
    )
    parser.add_argument(
        "--uid",
        action="append",
        default=[],
        help=(
            "Process only the given pseudo_study_uid(s). May be repeated. "
            "Useful for debugging a single Kyle study."
        ),
    )
    parser.add_argument(
        "--pacs",
        choices=("orthanc-a", "orthanc-b"),
        default=None,
        help=(
            "Restrict to studies whose source PACS endpoint matches. "
            "When uid_map.pacs_id is NULL we resolve by hospital_id "
            "(HOSP-001 → orthanc-a, HOSP-002 → orthanc-b)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N studies (after filtering). Default: all.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_GATEWAY_CONFIG,
        help=f"Gateway config path (default: {DEFAULT_GATEWAY_CONFIG})",
    )
    parser.add_argument(
        "--state-db",
        type=Path,
        default=DEFAULT_STATE_DB,
        help=f"Gateway state DB path (default: {DEFAULT_STATE_DB})",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="DEBUG-level logs."
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Env preflight
# ---------------------------------------------------------------------------


def _preflight_env() -> None:
    """Hard-fail with a helpful message when required env is missing.

    The CEO demo runbook expects ``inject_all.sh`` to have exported
    these; running this retry script without the env wiring is a
    common mistake we want to surface immediately.
    """
    missing = [v for v in _REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        sys.stderr.write(
            "ERROR: required env not set: " + ", ".join(missing) + "\n"
            "Source the same env block inject_all.sh STEP 3 exports, e.g.:\n\n"
            "  export PREVIEW_PIPELINE_ENABLED=true\n"
            "  export DEFACE_SIDECAR_URL=http://127.0.0.1:8090\n"
            "  export RV_CENTRAL_DATABASE_URL="
            "postgresql+psycopg://central_app:central_app@127.0.0.1:5432/central\n"
            "  export RV_MINIO_ENDPOINT=http://127.0.0.1:9000\n"
            "  export RV_MINIO_ACCESS_KEY=minioadmin\n"
            "  export RV_MINIO_SECRET_KEY=minioadmin\n"
        )
        sys.exit(2)
    flag = (os.environ.get(_PREVIEW_FLAG_VAR) or "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        sys.stderr.write(
            f"ERROR: {_PREVIEW_FLAG_VAR} must be 'true' for the preview "
            f"pipeline to run; got {flag!r}.\n"
            f"  export {_PREVIEW_FLAG_VAR}=true\n"
        )
        sys.exit(2)


# ---------------------------------------------------------------------------
# Central DB — pending series scan + UPDATE
# ---------------------------------------------------------------------------


@dataclass
class PendingStudy:
    pseudo_study_uid: str
    hospital_id: str
    pseudo_series_uids: list[str]


def scan_pending_studies(
    central_session_factory,
    *,
    only_uids: Iterable[str] | None = None,
) -> list[PendingStudy]:
    """Group pending series by pseudo_study_uid and resolve hospital_id.

    Returns one entry per study (not per series). Studies are sorted by
    hospital_id then pseudo_study_uid for deterministic output.
    """
    from sqlalchemy import select

    from radivault_central.db.models import Hospital, Series, Study

    only = set(only_uids or ())

    grouped: dict[str, dict] = defaultdict(
        lambda: {"hospital_id": "", "series": []}
    )
    with central_session_factory() as session:
        stmt = (
            select(
                Study.pseudo_study_uid,
                Hospital.hospital_id,
                Series.pseudo_series_uid,
            )
            .join(Series, Series.study_pk == Study.study_pk)
            .join(Hospital, Hospital.hospital_pk == Study.hospital_pk)
            .where(Series.preview_status == "pending")
        )
        if only:
            stmt = stmt.where(Study.pseudo_study_uid.in_(only))
        for row in session.execute(stmt):
            entry = grouped[row.pseudo_study_uid]
            entry["hospital_id"] = row.hospital_id
            entry["series"].append(row.pseudo_series_uid)

    out: list[PendingStudy] = []
    for uid in sorted(grouped):
        entry = grouped[uid]
        out.append(
            PendingStudy(
                pseudo_study_uid=uid,
                hospital_id=entry["hospital_id"],
                pseudo_series_uids=sorted(set(entry["series"])),
            )
        )
    out.sort(key=lambda s: (s.hospital_id, s.pseudo_study_uid))
    return out


def update_series_status_from_batch(
    central_session_factory, *, batch
) -> tuple[int, int]:
    """Reflect a ``PreviewBatchResult`` into ``series.preview_status``.

    The preview pipeline's PgFrameWriter / PgAuditWriter only touch
    ``dicom_preview_frame`` and ``phi_scrub_audit`` — the ``series``
    row's ``preview_status`` is normally flipped by central's ingest
    router via ``_persist_preview_batch``. This script bypasses that
    router (the study row already exists), so we mirror its UPDATE
    semantics here:

      - 'generated' → set status='generated', frame_count, decision,
        method, pipeline_version, generated_at = now.
      - 'skipped' / 'quarantined' → set the same metadata fields but
        leave generated_at NULL so the buyer BFF still 404s the row.

    Returns ``(n_generated, n_quarantined_or_skipped)``.
    """
    from datetime import datetime, timezone

    from sqlalchemy import select

    from radivault_central.db.models import Series

    n_gen = 0
    n_other = 0
    now = datetime.now(tz=timezone.utc)
    with central_session_factory() as session:
        for series_result in batch.series:
            row = session.scalar(
                select(Series).where(
                    Series.pseudo_series_uid == series_result.pseudo_series_uid
                )
            )
            if row is None:
                log.warning(
                    "central_series_missing_for_update",
                    extra={
                        "event": "retry.series.missing",
                        "pseudo_series_uid": series_result.pseudo_series_uid,
                    },
                )
                continue
            row.preview_status = series_result.preview_status
            row.preview_frame_count = int(series_result.frame_count or 0)
            row.preview_deface_decision = series_result.deface_decision
            row.preview_deface_method = series_result.phi_scrub_method
            row.preview_pipeline_version = batch.pipeline_version
            if series_result.preview_status == "generated":
                row.preview_generated_at = now
                n_gen += 1
            else:
                n_other += 1
        session.commit()
    return n_gen, n_other


# ---------------------------------------------------------------------------
# Gateway state DB — pseudo→original UID lookup (multi-kind)
# ---------------------------------------------------------------------------


@dataclass
class StateMapping:
    pseudo_study_uid: str
    original_study_uid: str
    pacs_id: str | None  # may be None for legacy single-PACS rows


def lookup_state_mapping(
    state_db_path: Path, pseudo_study_uid: str
) -> StateMapping | None:
    """Look up the original Study Instance UID from the gateway state DB.

    The gateway records ``uid_map(original_uid → pseudo_uid, kind, pacs_id)``
    rows on every successful pseudonymisation. We find the row by
    pseudo_uid + kind='study'. ``pacs_id`` may be NULL on legacy rows
    written before the FR-MPS-9 migration; the caller decides how to
    resolve those (typically by hospital_id → endpoint mapping).
    """
    import sqlite3

    if not state_db_path.exists():
        log.error(
            "state_db_missing",
            extra={"event": "retry.state.missing", "path": str(state_db_path)},
        )
        return None
    conn = sqlite3.connect(state_db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT original_uid, pacs_id FROM uid_map "
            "WHERE pseudo_uid = ? AND uid_kind = 'study' LIMIT 1",
            (pseudo_study_uid,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return StateMapping(
        pseudo_study_uid=pseudo_study_uid,
        original_study_uid=row["original_uid"],
        pacs_id=row["pacs_id"],
    )


# ---------------------------------------------------------------------------
# PACS endpoint resolution
# ---------------------------------------------------------------------------


@dataclass
class ResolvedEndpoint:
    pacs_id: str
    base_url: str
    auth_username: str
    auth_password: str
    hospital_id: str


def load_endpoints(config_path: Path) -> dict[str, ResolvedEndpoint]:
    """Read enabled PACS endpoints from the gateway YAML config.

    We deliberately use the validated GatewayConfig schema (rather than
    yaml.safe_load + ad-hoc field reads) so any future config-shape
    change automatically flows through this script.
    """
    from radivault_gateway.config.loader import load_config

    cfg = load_config(config_path)
    out: dict[str, ResolvedEndpoint] = {}
    for ep in cfg.enabled_endpoints():
        if ep.auth.type != "basic":
            log.warning(
                "endpoint_unsupported_auth_skipped",
                extra={
                    "event": "retry.endpoint.skip",
                    "pacs_id": ep.id,
                    "auth_type": ep.auth.type,
                },
            )
            continue
        out[ep.id] = ResolvedEndpoint(
            pacs_id=ep.id,
            base_url=ep.base_url,
            auth_username=ep.auth.username or "",
            auth_password=ep.auth.password or "",
            hospital_id=cfg.hospital_id_for(ep),
        )
    return out


def _hospital_to_pacs_fallback(
    hospital_id: str, endpoints: dict[str, ResolvedEndpoint]
) -> ResolvedEndpoint | None:
    """Find the endpoint whose hospital_id matches.

    Used when uid_map.pacs_id is NULL (legacy rows). Picks the first
    enabled endpoint with the matching hospital_id; deterministic
    because ``load_endpoints`` preserves the priority-sorted order
    from ``enabled_endpoints()``.
    """
    for ep in endpoints.values():
        if ep.hospital_id == hospital_id:
            return ep
    return None


def _verify_endpoint_has_study(
    endpoint: ResolvedEndpoint, original_study_uid: str
) -> bool:
    """Probe ``GET /studies?StudyInstanceUID=<uid>`` to confirm presence.

    Cheap (kilobyte-scale QIDO row, ~50 ms on Orthanc). We use this as
    a defensive guard before WADO-RS — saves us from a bigger 404 on
    the multipart endpoint when the study sits on the *other* PACS
    (multi-PACS race / legacy uid_map.pacs_id=NULL ambiguity).
    """
    from radivault_gateway.pacs.client import DicomWebPacsClient, PacsError

    client = DicomWebPacsClient(
        endpoint.base_url,
        auth_type="basic",
        username=endpoint.auth_username,
        password=endpoint.auth_password,
        timeout_seconds=15.0,
        max_retries=1,
    )
    try:
        client.fetch_study_qido_summary(original_study_uid)
        return True
    except PacsError as exc:
        log.debug(
            "endpoint_does_not_have_study",
            extra={
                "event": "retry.endpoint.miss",
                "pacs_id": endpoint.pacs_id,
                "status": exc.status_code,
            },
        )
        return False
    finally:
        client.close()


def resolve_endpoint_for_study(
    *,
    mapping: StateMapping,
    hospital_id: str,
    endpoints: dict[str, ResolvedEndpoint],
    pacs_filter: str | None,
) -> ResolvedEndpoint | None:
    """Pick the right PACS for a given pseudo study.

    Resolution order:

      1. ``mapping.pacs_id`` set (FR-MPS-9 era row) → use that endpoint.
      2. else → pick the endpoint with matching hospital_id.
      3. else → try every enabled endpoint and pick the first that
         answers QIDO with a hit.

    ``pacs_filter`` (--pacs CLI flag) hard-restricts the candidate set.
    """
    candidates = (
        {pid: ep for pid, ep in endpoints.items() if pid == pacs_filter}
        if pacs_filter
        else endpoints
    )
    if not candidates:
        return None

    if mapping.pacs_id and mapping.pacs_id in candidates:
        return candidates[mapping.pacs_id]

    by_hospital = _hospital_to_pacs_fallback(hospital_id, candidates)
    if by_hospital is not None:
        return by_hospital

    # Final fallback — probe each enabled endpoint.
    for ep in candidates.values():
        if _verify_endpoint_has_study(ep, mapping.original_study_uid):
            return ep
    return None


# ---------------------------------------------------------------------------
# DICOM re-fetch + de-id (uses existing modules, no copy/paste)
# ---------------------------------------------------------------------------


def fetch_study_to_dir(
    endpoint: ResolvedEndpoint, original_study_uid: str, out_dir: Path
) -> int:
    """WADO-RS multipart fetch via the existing gateway client.

    Returns the number of instances written to ``out_dir``. Raises
    ``PacsError`` on unrecoverable failure — the caller treats this
    as a per-study failure and moves on to the next.
    """
    from radivault_gateway.pacs.client import DicomWebPacsClient

    client = DicomWebPacsClient(
        endpoint.base_url,
        auth_type="basic",
        username=endpoint.auth_username,
        password=endpoint.auth_password,
        timeout_seconds=300.0,
    )
    try:
        result = client.fetch_study(original_study_uid, out_dir)
        return len(result.instance_paths)
    finally:
        client.close()


def deidentify_study(
    *,
    cfg,
    state_db,
    pacs_id: str,
    fetch_dir: Path,
    out_dir: Path,
):
    """Re-run the DeidEngine against the freshly-fetched payload.

    Reuses the production DeidEngine + RetainOptions wiring so the
    pseudo UIDs are identical to the original ingest (the salt and
    org_root_oid are deterministic). uid_map.upsert_uid_map is
    ON CONFLICT DO NOTHING, so re-running against the same originals
    is a no-op against state DB.
    """
    from radivault_gateway.deid import DeidEngine

    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=state_db,
        retain=cfg.deid.retain_options,
        burnin_quarantine_modalities=cfg.deid.burnin_quarantine_modalities,
        ruleset_version=cfg.deid.ruleset_version,
    )
    deid.set_pacs_context(pacs_id)
    return deid.deidentify_study(fetch_dir, out_dir)


# ---------------------------------------------------------------------------
# Per-study driver
# ---------------------------------------------------------------------------


def reprocess_one_study(
    *,
    pending: PendingStudy,
    endpoint: ResolvedEndpoint,
    mapping: StateMapping,
    cfg,
    state_db,
    preview_clients,
    central_session_factory,
) -> StudyRetryResult:
    """Fetch → de-id → preview pipeline → series UPDATE for one study."""
    from radivault_gateway.preview_pipeline import (
        SeriesInput,
        process_study as run_preview_process_study,
    )

    out = StudyRetryResult(
        pseudo_study_uid=pending.pseudo_study_uid,
        hospital_id=pending.hospital_id,
        pacs_id=endpoint.pacs_id,
        n_pending_series_before=len(pending.pseudo_series_uids),
    )

    # Wrap the whole thing in a tempdir so on any failure path we
    # don't leak megabytes of DICOMs to /tmp. The TemporaryDirectory
    # context manager handles cleanup even on exceptions.
    with tempfile.TemporaryDirectory(prefix="retry_preview_") as base:
        base_path = Path(base)
        fetch_dir = base_path / "fetch"
        deid_dir = base_path / "deid"
        fetch_dir.mkdir(parents=True, exist_ok=True)
        deid_dir.mkdir(parents=True, exist_ok=True)

        log.info(
            "retry_study_start",
            extra={
                "event": "retry.study.start",
                "pseudo_study_uid": pending.pseudo_study_uid,
                "hospital_id": pending.hospital_id,
                "pacs_id": endpoint.pacs_id,
                "n_pending_series": len(pending.pseudo_series_uids),
            },
        )

        try:
            n_instances = fetch_study_to_dir(
                endpoint, mapping.original_study_uid, fetch_dir
            )
        except Exception as exc:  # noqa: BLE001 — bubble as per-study failure
            out.error = f"fetch_failed: {exc}"
            log.error(
                "retry_fetch_failed",
                extra={
                    "event": "retry.fetch.fail",
                    "pseudo_study_uid": pending.pseudo_study_uid,
                    "error": str(exc)[:200],
                },
            )
            return out

        if n_instances == 0:
            out.error = "fetch_returned_zero_instances"
            return out

        try:
            deid_result = deidentify_study(
                cfg=cfg,
                state_db=state_db,
                pacs_id=endpoint.pacs_id,
                fetch_dir=fetch_dir,
                out_dir=deid_dir,
            )
        except Exception as exc:  # noqa: BLE001
            out.error = f"deid_failed: {exc}"
            log.error(
                "retry_deid_failed",
                extra={
                    "event": "retry.deid.fail",
                    "pseudo_study_uid": pending.pseudo_study_uid,
                    "error": str(exc)[:200],
                },
            )
            return out

        # Sanity check: DeidEngine should produce the same pseudo_study_uid
        # as the central row. If it doesn't, the salt has changed since
        # the original ingest — bail rather than silently UPDATE the
        # wrong rows.
        if deid_result.pseudo_study_uid != pending.pseudo_study_uid:
            out.error = (
                f"pseudo_uid_mismatch: deid={deid_result.pseudo_study_uid} "
                f"central={pending.pseudo_study_uid}"
            )
            log.error(
                "retry_pseudo_uid_mismatch",
                extra={
                    "event": "retry.deid.uid_mismatch",
                    "deid_uid": deid_result.pseudo_study_uid,
                    "central_uid": pending.pseudo_study_uid,
                },
            )
            return out

        # Build SeriesInput list — one per series subdir under deid_dir.
        # We extract modality / body_part from the first instance of
        # each series so the deface decision matches the original
        # ingest logic.
        try:
            import pydicom  # type: ignore[import-not-found]
        except ImportError as exc:
            out.error = f"pydicom_missing: {exc}"
            return out

        series_inputs: list[SeriesInput] = []
        study_description: str | None = None
        for series_idx, series_dir in enumerate(
            sorted(deid_dir.iterdir()), start=1
        ):
            if not series_dir.is_dir():
                continue
            pseudo_series_uid = series_dir.name
            modality: str | None = None
            body_part: str | None = None
            series_description: str | None = None
            protocol_name: str | None = None
            for inst in sorted(series_dir.glob("*.dcm")):
                try:
                    ds = pydicom.dcmread(inst, stop_before_pixels=True)
                except Exception:
                    continue
                modality = (
                    str(getattr(ds, "Modality", "") or "").strip() or None
                )
                body_part = (
                    str(getattr(ds, "BodyPartExamined", "") or "").strip()
                    or None
                )
                series_description = (
                    str(getattr(ds, "SeriesDescription", "") or "").strip()
                    or None
                )
                protocol_name = (
                    str(getattr(ds, "ProtocolName", "") or "").strip()
                    or None
                )
                if study_description is None:
                    study_description = (
                        str(getattr(ds, "StudyDescription", "") or "").strip()
                        or None
                    )
                break
            series_inputs.append(
                SeriesInput(
                    pseudo_series_uid=pseudo_series_uid,
                    series_num=series_idx,
                    series_dir=series_dir,
                    modality=modality,
                    body_part=body_part,
                    series_description=series_description,
                    protocol_name=protocol_name,
                )
            )

        if not series_inputs:
            out.error = "no_series_in_deid_output"
            return out

        # Run the preview pipeline. PreviewClients context is owned by
        # the caller (PreviewClients.from_env()) so we can amortize the
        # DB engine + boto3 session across many studies in one run.
        try:
            batch = run_preview_process_study(
                pseudo_study_uid=pending.pseudo_study_uid,
                series_inputs=series_inputs,
                study_description=study_description,
                minio_client=preview_clients.minio,
                audit_writer=preview_clients.audit,
                frame_writer=preview_clients.frames,
            )
        except Exception as exc:  # noqa: BLE001
            out.error = f"preview_pipeline_failed: {exc}"
            log.error(
                "retry_preview_failed",
                extra={
                    "event": "retry.preview.fail",
                    "pseudo_study_uid": pending.pseudo_study_uid,
                    "error": str(exc)[:200],
                },
            )
            return out

        # Reflect into series.preview_status — mirrors central's
        # _persist_preview_batch but only the series-row fields, since
        # frames + audit already landed via the writers above.
        try:
            n_gen, n_other = update_series_status_from_batch(
                central_session_factory, batch=batch
            )
        except Exception as exc:  # noqa: BLE001
            out.error = f"series_update_failed: {exc}"
            log.error(
                "retry_series_update_failed",
                extra={
                    "event": "retry.series.update.fail",
                    "pseudo_study_uid": pending.pseudo_study_uid,
                    "error": str(exc)[:200],
                },
            )
            return out

        out.n_series_processed = n_gen
        out.n_series_quarantined = n_other
        # Re-scan the central DB to determine if this study still has
        # any 'pending' series. A SeriesInput may have been skipped if
        # the central row was already 'generated' on a previous run
        # (race) — we should not count those as failures.
        out.success = True
        log.info(
            "retry_study_done",
            extra={
                "event": "retry.study.done",
                "pseudo_study_uid": pending.pseudo_study_uid,
                "n_generated": n_gen,
                "n_other": n_other,
            },
        )
        return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _setup_logging(args.verbose)
    _preflight_env()

    # ---- load gateway config + state DB + endpoints ---------------------
    from radivault_gateway.config.loader import load_config
    from radivault_gateway.state import StateDB

    if not args.config.exists():
        sys.stderr.write(f"ERROR: config not found: {args.config}\n")
        return 2
    cfg = load_config(args.config)
    endpoints = load_endpoints(args.config)
    if not endpoints:
        sys.stderr.write("ERROR: no enabled PACS endpoints in config\n")
        return 2
    log.info(
        "endpoints_loaded",
        extra={
            "event": "retry.endpoints.loaded",
            "count": len(endpoints),
            "ids": sorted(endpoints),
        },
    )

    if not args.state_db.exists():
        sys.stderr.write(f"ERROR: state DB not found: {args.state_db}\n")
        return 2

    # ---- central DB session factory ------------------------------------
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    dsn = os.environ["RV_CENTRAL_DATABASE_URL"]
    central_engine = create_engine(dsn, pool_pre_ping=True, future=True)
    central_session_factory = sessionmaker(
        bind=central_engine, autoflush=False, expire_on_commit=False
    )

    # ---- scan pending series -------------------------------------------
    only_uids = args.uid or None
    pending_studies = scan_pending_studies(
        central_session_factory, only_uids=only_uids
    )

    # ``--pacs`` narrows the candidate set by hospital affinity. We map
    # each enabled endpoint id → hospital_id and drop pending studies
    # whose hospital_id doesn't belong to the chosen endpoint. This is
    # cheap (no Orthanc round-trip) and correct for the v0.1 demo
    # where hospital_id ↔ endpoint is one-to-one. If the production
    # multi-PACS-per-hospital case ever materialises this filter will
    # need a per-study probe.
    if args.pacs:
        target_hospital = endpoints[args.pacs].hospital_id
        before = len(pending_studies)
        pending_studies = [
            ps for ps in pending_studies if ps.hospital_id == target_hospital
        ]
        log.info(
            "pacs_filter_applied",
            extra={
                "event": "retry.pacs.filter",
                "pacs_id": args.pacs,
                "hospital_id": target_hospital,
                "kept": len(pending_studies),
                "dropped": before - len(pending_studies),
            },
        )

    n_total_pending_series = sum(
        len(s.pseudo_series_uids) for s in pending_studies
    )
    print(
        f"\nFound {len(pending_studies)} studies with "
        f"{n_total_pending_series} pending series.\n"
    )

    if not pending_studies:
        print("Nothing to do. ✔")
        central_engine.dispose()
        return 0

    if args.dry_run:
        print("--- dry-run: pending studies ---")
        shown = 0
        for ps in pending_studies:
            if args.limit is not None and shown >= args.limit:
                print(
                    f"  ...{len(pending_studies) - shown} more "
                    f"(--limit {args.limit} truncating)\n"
                )
                break
            shown += 1
            print(
                f"  [{shown:>3}] {ps.pseudo_study_uid}  "
                f"({ps.hospital_id})  "
                f"{len(ps.pseudo_series_uids)} pending series"
            )
        print()
        central_engine.dispose()
        return 0

    # ---- live run ------------------------------------------------------
    from radivault_gateway.preview_clients import PreviewClients

    state_db = StateDB(args.state_db)
    summary = RunSummary()

    processed = 0
    try:
        with PreviewClients.from_env() as preview_clients:
            for pending in pending_studies:
                if args.limit is not None and processed >= args.limit:
                    break
                summary.studies_total += 1
                mapping = lookup_state_mapping(
                    args.state_db, pending.pseudo_study_uid
                )
                if mapping is None:
                    res = StudyRetryResult(
                        pseudo_study_uid=pending.pseudo_study_uid,
                        hospital_id=pending.hospital_id,
                        pacs_id=None,
                        n_pending_series_before=len(
                            pending.pseudo_series_uids
                        ),
                        error="state_db_no_uid_map_row",
                    )
                    summary.results.append(res)
                    summary.studies_failed += 1
                    log.warning(
                        "retry_study_no_state_mapping",
                        extra={
                            "event": "retry.study.no_state",
                            "pseudo_study_uid": pending.pseudo_study_uid,
                        },
                    )
                    processed += 1
                    continue

                endpoint = resolve_endpoint_for_study(
                    mapping=mapping,
                    hospital_id=pending.hospital_id,
                    endpoints=endpoints,
                    pacs_filter=args.pacs,
                )
                if endpoint is None:
                    res = StudyRetryResult(
                        pseudo_study_uid=pending.pseudo_study_uid,
                        hospital_id=pending.hospital_id,
                        pacs_id=mapping.pacs_id,
                        n_pending_series_before=len(
                            pending.pseudo_series_uids
                        ),
                        error="no_pacs_endpoint_resolved",
                    )
                    summary.results.append(res)
                    summary.studies_failed += 1
                    log.warning(
                        "retry_study_no_endpoint",
                        extra={
                            "event": "retry.study.no_endpoint",
                            "pseudo_study_uid": pending.pseudo_study_uid,
                            "hospital_id": pending.hospital_id,
                            "pacs_filter": args.pacs,
                        },
                    )
                    processed += 1
                    continue

                # Apply --pacs filter post-resolution (handles mapping
                # resolved by hospital_id fallback that doesn't match the
                # caller's narrowing). resolve_endpoint_for_study already
                # honours pacs_filter, so endpoint.pacs_id == args.pacs
                # is guaranteed here when the filter was set.

                res = reprocess_one_study(
                    pending=pending,
                    endpoint=endpoint,
                    mapping=mapping,
                    cfg=cfg,
                    state_db=state_db,
                    preview_clients=preview_clients,
                    central_session_factory=central_session_factory,
                )
                summary.results.append(res)
                if res.success:
                    summary.studies_success += 1
                    summary.series_generated += res.n_series_processed
                    summary.series_quarantined += res.n_series_quarantined
                else:
                    summary.studies_failed += 1
                processed += 1
    finally:
        try:
            state_db.close()
        except Exception:  # pragma: no cover
            pass

    # ---- final report --------------------------------------------------
    print()
    print("Retry preview pipelines — summary")
    print("=================================")
    print(f"studies (attempted): {summary.studies_total}")
    print(f"  success:           {summary.studies_success}")
    print(f"  failed:            {summary.studies_failed}")
    print(f"series:")
    print(f"  generated:         {summary.series_generated}")
    print(f"  skipped/quarant.:  {summary.series_quarantined}")
    print()

    failures = [r for r in summary.results if not r.success]
    if failures:
        print("Failures:")
        for r in failures:
            print(
                f"  - {r.pseudo_study_uid}  ({r.hospital_id}, "
                f"pacs={r.pacs_id})  {r.error}"
            )
        print()

    # Re-scan central to show the after-state.
    final_pending = scan_pending_studies(central_session_factory)
    final_total_series = sum(len(s.pseudo_series_uids) for s in final_pending)
    print(
        f"Final state in central DB: {len(final_pending)} studies "
        f"with {final_total_series} pending series."
    )
    central_engine.dispose()
    return 0 if summary.studies_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
