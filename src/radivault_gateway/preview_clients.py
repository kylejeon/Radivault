"""Concrete production implementations of the preview-pipeline adapter
Protocols (jpg-preview-defacing FR-PREVIEW-2).

Round-2 CAVEAT-1 closeout — round 1 left these adapters as Protocols
only and tested via fakes; the CLI wiring of ``with_preview_pipeline``
needs *real* clients backed by MinIO (boto3 / S3 protocol) and Postgres
(SQLAlchemy). The three classes here implement:

  * :class:`MinioJpegClient`   — ``preview_pipeline.MinioClient``
  * :class:`PgAuditWriter`     — ``preview_pipeline.AuditWriter``
  * :class:`PgFrameWriter`     — ``preview_pipeline.FrameWriter``

A small bundle :class:`PreviewClients` ties all three together with a
shared SQLAlchemy session factory so the CLI can ``with PreviewClients
.from_env() as clients:`` and pass the three adapters to
``with_preview_pipeline``.

Environment variables read (FR-PREVIEW-9 / FR-PREVIEW-11 / FR-AUDIT-1):

  RV_MINIO_ENDPOINT       e.g. http://minio:9000  (or s3 hostname)
  RV_MINIO_ACCESS_KEY     access key id
  RV_MINIO_SECRET_KEY     secret key
  RV_MINIO_USE_TLS        "true"|"1" → use https schema if endpoint
                          is bare hostname; default false (dev compose)
  RV_MINIO_REGION         optional, default us-east-1
  RV_PREVIEWS_S3_BUCKET   override the bucket name (default
                          ``radivault-previews`` to match
                          ``preview_pipeline.PREVIEW_BUCKET``)
  RV_CENTRAL_DATABASE_URL SQLAlchemy DSN for the central DB; the
                          gateway writes ``phi_scrub_audit`` and
                          ``dicom_preview_frame`` rows directly into
                          the same logical schema central uses.

Why direct DB writes vs RPC to central?
---------------------------------------
The ``manifest.preview`` block already travels through the existing
``complete`` RPC and is persisted by central's ingest router (B-5
closeout). The local audit writes here are an additional belt-and-
braces path: per FR-AUDIT-2 every series gets exactly one
``phi_scrub_audit`` row, and that row needs to land *before* the
sidecar response so the audit trail is durable even if the gateway
crashes mid-batch. v0.2 will collapse this to a single source of
truth; v0.1 demo posture is "write twice, idempotent on conflict".

Ruff ignores: this module imports boto3 / sqlalchemy lazily so that
the unit-test environment (which has neither boto3 nor a live
Postgres) can still import it for the CLI factory test.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator
from urllib.parse import urlsplit

from radivault_gateway.preview_pipeline import (
    PREVIEW_BUCKET,
    AuditWriter,
    FrameRecord,
    FrameWriter,
    MinioClient,
)

log = logging.getLogger("radivault_gateway.preview_clients")


# ---------------------------------------------------------------------------
# MinIO / S3 adapter
# ---------------------------------------------------------------------------


class MinioJpegClient:
    """boto3-backed implementation of ``preview_pipeline.MinioClient``.

    The preview pipeline writes one JPG per frame to
    ``radivault-previews/previews/{study}/{series}/{idx:04d}.jpg``
    (FR-PREVIEW-9 + FR-PREVIEW-10). This client uses S3v4 signing via
    boto3 — MinIO is fully S3-compatible so the same code works in
    pilot (MinIO) and production (S3 / Wasabi / etc.).
    """

    def __init__(
        self,
        *,
        endpoint_url: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
        region: str = "us-east-1",
        allow_insecure: bool = True,
    ) -> None:
        # Defer boto3 import — unit tests should be able to construct
        # ``MinioJpegClient`` for type-resolving purposes without boto3.
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover — runtime-only
            raise RuntimeError(
                "boto3 is required for MinioJpegClient. "
                "Install with `pip install '.[search]'` or '.[central]'."
            ) from exc

        if endpoint_url:
            scheme = urlsplit(endpoint_url).scheme.lower()
            if scheme not in ("http", "https"):
                raise RuntimeError(
                    f"RV_MINIO_ENDPOINT scheme must be http|https, got {scheme!r}"
                )
            if scheme == "http" and not allow_insecure:
                raise RuntimeError(
                    "Refusing http:// MinIO endpoint with allow_insecure=False"
                )

        cfg = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=cfg,
        )

    def ensure_bucket(self, *, bucket: str) -> None:
        """Idempotent CreateBucket — swallows BucketAlreadyOwnedByYou."""
        try:
            self._client.head_bucket(Bucket=bucket)
            return
        except Exception as exc:  # noqa: BLE001
            code = (
                getattr(exc, "response", {}) or {}
            ).get("Error", {}).get("Code")
            if code not in ("404", "NoSuchBucket", "NotFound"):
                # Could be 403 (no head perm) — try create anyway, the
                # subsequent PutObject will surface the real error.
                log.debug(
                    "minio_head_bucket_unexpected",
                    extra={"event": "minio.head.error", "code": code},
                )
        try:
            self._client.create_bucket(Bucket=bucket)
            log.info(
                "minio_bucket_created",
                extra={"event": "minio.bucket.create", "bucket": bucket},
            )
        except Exception as exc:  # noqa: BLE001
            code = (
                getattr(exc, "response", {}) or {}
            ).get("Error", {}).get("Code")
            if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                return
            # Permission errors etc. — re-raise so the operator sees them.
            raise

    def put_jpeg(self, *, bucket: str, key: str, body: bytes) -> None:
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="image/jpeg",
            CacheControl="private, max-age=3600",
        )


# ---------------------------------------------------------------------------
# Audit + frame DB writers
# ---------------------------------------------------------------------------


class PgAuditWriter:
    """SQLAlchemy-backed ``AuditWriter`` (FR-AUDIT-1, FR-AUDIT-3).

    Inserts one ``phi_scrub_audit`` row per series. The model is reused
    from ``radivault_central.db.models`` so gateway-side writes share a
    schema definition with central-side reads — there's exactly one
    source of truth for column types + constraints.

    AC-19 invariant: the caller (``preview_pipeline._record_series``)
    is responsible for keeping ``error_detail`` PHI-free. This writer
    does not re-scrub — that would mask PII coming in from a future
    pipeline regression. It is a pure persistence layer.
    """

    def __init__(self, *, session_factory: Any) -> None:
        self._sf = session_factory

    def write_audit(
        self,
        *,
        pseudo_study_uid: str,
        pseudo_series_uid: str,
        modality: str,
        body_part: str | None,
        deface_decision: str,
        deface_decision_reason: str,
        phi_scrub_method: str,
        sidecar_image_tag: str | None,
        afni_version: str | None,
        duration_ms: int | None,
        outcome: str,
        error_code: str | None,
        error_detail: str | None,
        pipeline_version: str,
    ) -> None:
        from radivault_central.db.models import PhiScrubAudit

        with self._sf() as session:
            row = PhiScrubAudit(
                pseudo_study_uid=pseudo_study_uid,
                pseudo_series_uid=pseudo_series_uid,
                modality=modality[:8],
                body_part=(body_part or None),
                deface_decision=deface_decision,
                deface_decision_reason=deface_decision_reason[:255],
                phi_scrub_method=phi_scrub_method,
                # Match central's bound enforcement
                # (radivault_central.routers.ingest line 303 truncates to [:32]).
                # Without this the AFNI binary description string
                # (~64 chars: "Precompiled binary linux_ubuntu_16_64...") trips
                # phi_scrub_audit.afni_version VARCHAR(32) and fails the
                # series-level audit write, leaving series.preview_status='pending'.
                sidecar_image_tag=(sidecar_image_tag[:64] if sidecar_image_tag else None),
                afni_version=(afni_version[:32] if afni_version else None),
                duration_ms=duration_ms,
                outcome=outcome,
                error_code=error_code,
                error_detail=(error_detail or None),
                pipeline_version=pipeline_version,
            )
            session.add(row)
            session.commit()


class PgFrameWriter:
    """SQLAlchemy-backed ``FrameWriter``. One row per generated JPG
    (FR-PREVIEW-13). UPSERT-light semantics: re-runs of the same series
    fail on the unique ``(pseudo_series_uid, frame_idx)`` constraint —
    that's intentional, the pipeline is meant to be invoked once per
    series.
    """

    def __init__(self, *, session_factory: Any) -> None:
        self._sf = session_factory

    def write_frame_rows(
        self,
        *,
        pseudo_study_uid: str,
        pseudo_series_uid: str,
        frames: list[FrameRecord],
    ) -> None:
        if not frames:
            return
        from radivault_central.db.models import DicomPreviewFrame

        with self._sf() as session:
            for f in frames:
                session.add(
                    DicomPreviewFrame(
                        pseudo_study_uid=pseudo_study_uid,
                        pseudo_series_uid=pseudo_series_uid,
                        frame_idx=f.frame_idx,
                        minio_key=f.minio_key,
                        width=f.width,
                        height=f.height,
                        byte_size=f.byte_size,
                        sha256=f.sha256,
                        phi_scrub_method=f.phi_scrub_method,
                        source_instance_uid_pseudo=f.source_instance_uid_pseudo,
                    )
                )
            session.commit()


# ---------------------------------------------------------------------------
# Bundle / CLI factory
# ---------------------------------------------------------------------------


@dataclass
class PreviewClients:
    """Bundle of the three adapters + their owned resources.

    Use as a context manager so the SQLAlchemy engine is disposed and
    the boto3 client (which has no formal close API but holds a session)
    is released cleanly when the CLI exits.
    """

    minio: MinioJpegClient
    audit: PgAuditWriter
    frames: PgFrameWriter
    bucket: str
    _engine: Any  # sqlalchemy.Engine — kept private so .dispose() runs

    def __enter__(self) -> "PreviewClients":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self._engine.dispose()
        except Exception:  # pragma: no cover - best-effort cleanup
            log.debug("preview_clients_dispose_swallowed", exc_info=True)

    @classmethod
    def from_env(cls, *, env: dict[str, str] | None = None) -> "PreviewClients":
        """Build a :class:`PreviewClients` from environment variables.

        Raises ``RuntimeError`` if a required variable is missing —
        the CLI surfaces this as a non-zero exit so operators don't
        silently run a half-wired pipeline.
        """
        e = env if env is not None else os.environ
        endpoint = (e.get("RV_MINIO_ENDPOINT") or "").strip() or None
        access_key = (e.get("RV_MINIO_ACCESS_KEY") or "").strip() or None
        secret_key = (e.get("RV_MINIO_SECRET_KEY") or "").strip() or None
        region = (e.get("RV_MINIO_REGION") or "us-east-1").strip()
        bucket = (
            e.get("RV_PREVIEWS_S3_BUCKET") or PREVIEW_BUCKET
        ).strip()
        # use_tls: only meaningful if endpoint lacks a scheme. If the
        # endpoint already contains "http://" / "https://" we honour
        # that verbatim. This preserves the semantics of search-side
        # ``RV_PREVIEW_S3_ENDPOINT``.
        use_tls = _truthy(e.get("RV_MINIO_USE_TLS"))
        if endpoint and "://" not in endpoint:
            scheme = "https" if use_tls else "http"
            endpoint = f"{scheme}://{endpoint}"

        # Postgres DSN — required for audit/frame writes.
        dsn = (e.get("RV_CENTRAL_DATABASE_URL") or "").strip()
        if not dsn:
            raise RuntimeError(
                "PREVIEW_PIPELINE_ENABLED=true but RV_CENTRAL_DATABASE_URL is "
                "not set. Set the central Postgres DSN so phi_scrub_audit + "
                "dicom_preview_frame writes can land."
            )

        # Lazy import — don't make the module-level import fragile.
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "sqlalchemy is required for PreviewClients. "
                "Install with `pip install '.[central]'`."
            ) from exc

        kwargs: dict[str, Any] = {"pool_pre_ping": True, "future": True}
        if dsn.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        engine = create_engine(dsn, **kwargs)
        session_factory = sessionmaker(
            bind=engine, autoflush=False, expire_on_commit=False
        )

        minio = MinioJpegClient(
            endpoint_url=endpoint,
            access_key_id=access_key,
            secret_access_key=secret_key,
            region=region,
            allow_insecure=True,
        )
        audit = PgAuditWriter(session_factory=session_factory)
        frames = PgFrameWriter(session_factory=session_factory)
        log.info(
            "preview_clients_initialised",
            extra={
                "event": "preview.clients.init",
                "bucket": bucket,
                "endpoint_present": bool(endpoint),
                "dsn_kind": dsn.split(":", 1)[0],
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )
        return cls(
            minio=minio,
            audit=audit,
            frames=frames,
            bucket=bucket,
            _engine=engine,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truthy(raw: str | None) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@contextmanager
def maybe_preview_clients(
    enabled: bool, *, env: dict[str, str] | None = None
) -> Iterator[PreviewClients | None]:
    """Yield a :class:`PreviewClients` if ``enabled`` is True; else None.

    Used by the CLI so a single ``with`` block conditionally constructs
    the production adapters or yields ``None`` when the feature flag is
    off (in which case ``with_preview_pipeline`` shouldn't run anyway —
    but the CLI still wires it for symmetry, and the wrapper short-
    circuits on its own ``flag_check``).
    """
    if not enabled:
        yield None
        return
    clients = PreviewClients.from_env(env=env)
    try:
        yield clients
    finally:
        try:
            clients.__exit__(None, None, None)
        except Exception:  # pragma: no cover
            log.debug("preview_clients_cleanup_swallowed", exc_info=True)


__all__ = [
    "AuditWriter",
    "FrameWriter",
    "MinioClient",
    "MinioJpegClient",
    "PgAuditWriter",
    "PgFrameWriter",
    "PreviewClients",
    "maybe_preview_clients",
]
