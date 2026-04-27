"""Unit tests for ``radivault_gateway.preview_clients.PreviewClients``.

jpg-preview-defacing CAVEAT-1 closeout — the production adapters are
constructed from environment variables. The CLI must not silently run
a half-wired pipeline, so ``from_env`` raises if a required var is
missing. These tests pin that behaviour without hitting MinIO or
Postgres (we use sqlite for the audit writer DSN and never call any
client method that would touch the network).
"""

from __future__ import annotations

import os

import pytest

from radivault_gateway.preview_clients import (
    MinioJpegClient,
    PgAuditWriter,
    PgFrameWriter,
    PreviewClients,
    maybe_preview_clients,
)


def _env(**overrides: str) -> dict[str, str]:
    """Build an env dict with sensible defaults — tests pass overrides
    to flip individual values."""
    base = {
        "RV_MINIO_ENDPOINT": "http://minio:9000",
        "RV_MINIO_ACCESS_KEY": "minioadmin",
        "RV_MINIO_SECRET_KEY": "minioadmin",
        "RV_MINIO_USE_TLS": "false",
        "RV_PREVIEWS_S3_BUCKET": "radivault-previews",
        # sqlite in-memory so we exercise the SQLAlchemy plumbing without
        # needing a live Postgres in unit tests.
        "RV_CENTRAL_DATABASE_URL": "sqlite:///:memory:",
    }
    base.update(overrides)
    return base


def test_from_env_constructs_concrete_adapters():
    """Smoke: each of the 3 adapters is the concrete production class."""
    clients = PreviewClients.from_env(env=_env())
    try:
        assert isinstance(clients.minio, MinioJpegClient)
        assert isinstance(clients.audit, PgAuditWriter)
        assert isinstance(clients.frames, PgFrameWriter)
        assert clients.bucket == "radivault-previews"
    finally:
        clients.__exit__(None, None, None)


def test_from_env_bucket_override_honoured():
    clients = PreviewClients.from_env(
        env=_env(RV_PREVIEWS_S3_BUCKET="my-custom-bucket")
    )
    try:
        assert clients.bucket == "my-custom-bucket"
    finally:
        clients.__exit__(None, None, None)


def test_from_env_default_bucket_when_unset():
    """Bucket defaults to ``radivault-previews`` per FR-PREVIEW-9 +
    ``preview_pipeline.PREVIEW_BUCKET`` so the search-side reader stays
    in sync without a separate env var."""
    env = _env()
    env.pop("RV_PREVIEWS_S3_BUCKET", None)
    clients = PreviewClients.from_env(env=env)
    try:
        assert clients.bucket == "radivault-previews"
    finally:
        clients.__exit__(None, None, None)


def test_from_env_use_tls_synthesises_https_scheme():
    """When the endpoint is bare hostname + ``RV_MINIO_USE_TLS=true``,
    the constructor prefixes ``https://``."""
    # We can't introspect the boto3 endpoint after construction without
    # poking private state. Instead we verify the env-driven scheme
    # selection by constructing two clients with different USE_TLS
    # values and confirming neither raises (the underlying scheme
    # validation in MinioJpegClient.__init__ rejects unknown schemes).
    clients_https = PreviewClients.from_env(
        env=_env(RV_MINIO_ENDPOINT="minio.example.com", RV_MINIO_USE_TLS="true")
    )
    clients_https.__exit__(None, None, None)

    clients_http = PreviewClients.from_env(
        env=_env(RV_MINIO_ENDPOINT="minio.example.com", RV_MINIO_USE_TLS="false")
    )
    clients_http.__exit__(None, None, None)


def test_from_env_existing_scheme_preserved():
    """If the endpoint already has http:// or https://, USE_TLS is ignored."""
    clients = PreviewClients.from_env(
        env=_env(
            RV_MINIO_ENDPOINT="http://minio:9000",
            RV_MINIO_USE_TLS="true",  # ignored — explicit http wins
        )
    )
    clients.__exit__(None, None, None)


def test_from_env_missing_dsn_raises():
    env = _env()
    env.pop("RV_CENTRAL_DATABASE_URL")
    with pytest.raises(RuntimeError, match="RV_CENTRAL_DATABASE_URL"):
        PreviewClients.from_env(env=env)


def test_maybe_preview_clients_yields_none_when_disabled():
    """The CLI passes ``enabled=False`` when the flag is off — the
    context manager must yield ``None`` and not touch any env var
    (so a misconfigured but flag-off deployment doesn't blow up)."""
    with maybe_preview_clients(False, env={}) as clients:
        assert clients is None


def test_maybe_preview_clients_yields_clients_when_enabled():
    """Mirror smoke: enabled=True + a valid env yields concrete clients."""
    with maybe_preview_clients(True, env=_env()) as clients:
        assert clients is not None
        assert isinstance(clients.minio, MinioJpegClient)
        assert isinstance(clients.audit, PgAuditWriter)
        assert isinstance(clients.frames, PgFrameWriter)


def test_maybe_preview_clients_propagates_construction_failure():
    """If from_env raises, the context manager surfaces it instead of
    silently swallowing — the CLI exit code should reflect the misconfig."""
    bad_env = _env()
    bad_env.pop("RV_CENTRAL_DATABASE_URL")
    with pytest.raises(RuntimeError):
        with maybe_preview_clients(True, env=bad_env):
            pass  # pragma: no cover — never enters block


def test_pg_audit_writer_writes_row_to_sqlite():
    """End-to-end that the audit writer actually inserts via SQLAlchemy.

    We stand up the central ORM tables on an in-memory sqlite, write
    one row, then SELECT it back. This proves the cross-module import
    of ``radivault_central.db.models.PhiScrubAudit`` is wired
    correctly from gateway code.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from radivault_central.db.models import Base, PhiScrubAudit

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    writer = PgAuditWriter(session_factory=sf)
    writer.write_audit(
        pseudo_study_uid="RV-STD-test",
        pseudo_series_uid="RV-SER-test",
        modality="MR",
        body_part="BRAIN",
        deface_decision="required",
        deface_decision_reason="BodyPartExamined=BRAIN",
        phi_scrub_method="afni_refacer_v0_7",
        sidecar_image_tag="radivault/deface-sidecar:0.1.0",
        afni_version="AFNI_25.0.00",
        duration_ms=12345,
        outcome="success",
        error_code=None,
        error_detail=None,
        pipeline_version="0.1.0",
    )

    with sf() as session:
        rows = session.execute(select(PhiScrubAudit)).scalars().all()
        assert len(rows) == 1
        r = rows[0]
        assert r.pseudo_study_uid == "RV-STD-test"
        assert r.outcome == "success"
        assert r.deface_decision_reason == "BodyPartExamined=BRAIN"


def test_pg_frame_writer_writes_rows_to_sqlite():
    """Mirror smoke for the frame writer."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from radivault_central.db.models import Base, DicomPreviewFrame
    from radivault_gateway.preview_pipeline import FrameRecord

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    writer = PgFrameWriter(session_factory=sf)
    frames = [
        FrameRecord(
            frame_idx=i,
            minio_key=f"previews/RV-STD-x/RV-SER-y/{i:04d}.jpg",
            width=512,
            height=512,
            byte_size=12345,
            sha256="a" * 64,
            phi_scrub_method="afni_refacer_v0_7",
            source_instance_uid_pseudo=None,
        )
        for i in range(3)
    ]
    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-x",
        pseudo_series_uid="RV-SER-y",
        frames=frames,
    )

    with sf() as session:
        rows = session.execute(select(DicomPreviewFrame)).scalars().all()
        assert len(rows) == 3
        assert {r.frame_idx for r in rows} == {0, 1, 2}


def test_pg_frame_writer_empty_list_is_noop():
    """Per the dev-spec, quarantined series have ``frame_count=0`` and the
    writer is invoked with ``frames=[]``. That must not error and must
    not insert anything."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from radivault_central.db.models import Base, DicomPreviewFrame

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    writer = PgFrameWriter(session_factory=sf)
    writer.write_frame_rows(
        pseudo_study_uid="RV-STD-z",
        pseudo_series_uid="RV-SER-z",
        frames=[],
    )

    with sf() as session:
        rows = session.execute(select(DicomPreviewFrame)).scalars().all()
        assert rows == []
