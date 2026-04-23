"""``ingest-admin`` CLI — operator tooling (design-spec §3).

Nine subcommands covering token lifecycle, anchor chain verification, study
inspection, withdraw stub, migrations, and version. All commands honour
``--config`` (or ``RADIVAULT_CENTRAL_CONFIG``) and ``--database-url``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import click
from sqlalchemy import select

from radivault_central import __version__ as central_version
from radivault_central.audit.anchor import verify_chain
from radivault_central.auth.tokens import generate_token
from radivault_central.config import Settings
from radivault_central.db.models import (
    AuditIngestEvent,
    AuthToken,
    Base,
    Hospital,
    Instance,
    Series,
    Study,
)
from radivault_central.db.session import get_engine, get_session_factory, reset_for_tests


def _load_settings(config: str | None, database_url: str | None) -> Settings:
    settings = Settings.load(config_path=config)
    if database_url:
        settings.db.dsn = database_url
    return settings


def _open_session(settings: Settings):
    engine = get_engine(
        settings.db.dsn, pool_size=settings.db.pool_size, max_overflow=settings.db.max_overflow
    )
    Base.metadata.create_all(engine)  # safe for SQLite dev; no-op for existing PG tables.
    return get_session_factory(settings.db.dsn)()


@click.group(
    name="ingest-admin",
    help="RadiVault Central Ingest operator CLI — dev-spec FR-75 / design-spec §3.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option("-c", "--config", type=click.Path(), default=None, help="Config YAML path")
@click.option("--database-url", type=str, default=None, help="Override DB DSN")
@click.option("--log-level", type=str, default="INFO")
@click.option("--no-color", is_flag=True, default=False)
@click.version_option(central_version, "-V", "--version")
@click.pass_context
def cli(
    ctx: click.Context,
    config: str | None,
    database_url: str | None,
    log_level: str,
    no_color: bool,
) -> None:
    """Root group — populates :attr:`ctx.obj` with a loaded :class:`Settings`."""
    reset_for_tests()
    ctx.ensure_object(dict)
    ctx.obj["settings"] = _load_settings(config, database_url)
    ctx.obj["no_color"] = no_color
    # Namespaced under ``RV_`` (not ``RADIVAULT_``) because the Gateway Agent
    # config loader treats every ``RADIVAULT_*`` env var as a top-level schema
    # override and would reject ours as ``extra`` inputs.
    os.environ.setdefault("RV_CENTRAL_LOG_LEVEL", log_level)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@cli.command("version")
@click.option("--json", "as_json", is_flag=True)
def cmd_version(as_json: bool) -> None:
    payload = {
        "service": "radivault-central",
        "version": central_version,
        "git_sha": os.environ.get("RADIVAULT_GIT_SHA", "unknown"),
        "built_at": os.environ.get("RADIVAULT_BUILT_AT", "unknown"),
        "api_contract_version": os.environ.get("RADIVAULT_API_CONTRACT_VERSION", "1"),
        "python": sys.version.split()[0],
    }
    click.echo(
        json.dumps(payload) if as_json else "\n".join(f"{k:<14}{v}" for k, v in payload.items())
    )


# ---------------------------------------------------------------------------
# token …
# ---------------------------------------------------------------------------


@cli.group("token", help="Bearer token lifecycle commands")
def token_group() -> None:
    pass


@token_group.command("issue")
@click.option("--hospital-id", required=True)
@click.option("--expires-days", type=int, default=None)
@click.option("--note", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_token_issue(
    ctx: click.Context,
    hospital_id: str,
    expires_days: int | None,
    note: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    settings: Settings = ctx.obj["settings"]
    session = _open_session(settings)
    hospital = session.scalar(select(Hospital).where(Hospital.hospital_id == hospital_id))
    if hospital is None:
        click.echo(f"[ERR_ADMIN_HOSPITAL_NOT_FOUND] hospital not enrolled: {hospital_id}", err=True)
        sys.exit(1)
    bundle = generate_token()
    expires_at = datetime.now(tz=UTC) + timedelta(days=expires_days) if expires_days else None
    if dry_run:
        click.echo(
            json.dumps(
                {"hospital_id": hospital_id, "kid": bundle.kid, "dry_run": True, "note": note}
            )
        )
        return
    row = AuthToken(
        hospital_pk=hospital.hospital_pk,
        token_kid=bundle.kid,
        token_hash=bundle.hash,
        expires_at=expires_at,
        note=note,
    )
    session.add(row)
    session.commit()
    if as_json:
        click.echo(
            json.dumps(
                {
                    "hospital_id": hospital_id,
                    "kid": bundle.kid,
                    "plaintext": bundle.plaintext,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "note": note,
                }
            )
        )
    else:
        click.echo(
            "\n".join(
                [
                    "=" * 72,
                    " RadiVault Central — new Bearer token issued",
                    "=" * 72,
                    f" hospital_id : {hospital_id}",
                    f" token_kid   : {bundle.kid}",
                    f" expires_at  : {expires_at.isoformat() if expires_at else 'never'}",
                    f" issued_at   : {datetime.now(tz=UTC).isoformat()}",
                    f" note        : {note or '-'}",
                    "-" * 72,
                    " Plaintext token (shown ONCE, store now):",
                    "",
                    f"   {bundle.plaintext}",
                    "",
                    "=" * 72,
                ]
            )
        )


@token_group.command("revoke")
@click.option("--kid", required=True)
@click.option("--reason", default=None)
@click.pass_context
def cmd_token_revoke(ctx: click.Context, kid: str, reason: str | None) -> None:
    session = _open_session(ctx.obj["settings"])
    row = session.scalar(select(AuthToken).where(AuthToken.token_kid == kid))
    if row is None:
        click.echo(f"[ERR_ADMIN_TOKEN_NOT_FOUND] kid not found: {kid}", err=True)
        sys.exit(1)
    if row.revoked_at is not None:
        click.echo(f"[ERR_ADMIN_TOKEN_ALREADY_REVOKED] kid already revoked: {kid}", err=True)
        sys.exit(1)
    row.revoked_at = datetime.now(tz=UTC)
    if reason:
        row.note = f"{row.note or ''}\nrevoked_reason={reason}".strip()
    session.commit()
    click.echo(f"[OK] revoked {kid} at {row.revoked_at.isoformat()}")


@token_group.command("list")
@click.option("--hospital-id", required=False)
@click.option("--include-revoked", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_token_list(
    ctx: click.Context, hospital_id: str | None, include_revoked: bool, as_json: bool
) -> None:
    session = _open_session(ctx.obj["settings"])
    stmt = select(AuthToken, Hospital).join(Hospital, AuthToken.hospital_pk == Hospital.hospital_pk)
    if hospital_id:
        stmt = stmt.where(Hospital.hospital_id == hospital_id)
    rows = session.execute(stmt).all()
    out: list[dict[str, Any]] = []
    for tok, hos in rows:
        status = "active"
        if tok.revoked_at is not None:
            status = "revoked"
        elif tok.expires_at and tok.expires_at < datetime.now(tz=UTC):
            status = "expired"
        if status == "revoked" and not include_revoked:
            continue
        out.append(
            {
                "hospital_id": hos.hospital_id,
                "kid": tok.token_kid,
                "issued_at": tok.issued_at.isoformat() if tok.issued_at else None,
                "expires_at": tok.expires_at.isoformat() if tok.expires_at else None,
                "last_used_at": tok.last_used_at.isoformat() if tok.last_used_at else None,
                "status": status,
                "note": tok.note,
            }
        )
    if as_json:
        click.echo(json.dumps({"tokens": out, "count": len(out)}))
    else:
        if not out:
            click.echo("(no tokens)")
            return
        click.echo(f"{'HOSPITAL_ID':<16}{'KID':<20}{'STATUS':<10}{'NOTE'}")
        for item in out:
            click.echo(
                f"{item['hospital_id']:<16}{item['kid']:<20}{item['status']:<10}{item.get('note') or '-'}"
            )


# ---------------------------------------------------------------------------
# anchor verify
# ---------------------------------------------------------------------------


@cli.group("anchor")
def anchor_group() -> None:
    pass


@anchor_group.command("verify")
@click.option("--hospital-id", required=True)
@click.option("--from", "seq_from", type=int, default=None)
@click.option("--to", "seq_to", type=int, default=None)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_anchor_verify(
    ctx: click.Context,
    hospital_id: str,
    seq_from: int | None,
    seq_to: int | None,
    as_json: bool,
) -> None:
    session = _open_session(ctx.obj["settings"])
    hospital = session.scalar(select(Hospital).where(Hospital.hospital_id == hospital_id))
    if hospital is None:
        click.echo(f"[ERR_ADMIN_HOSPITAL_NOT_FOUND] hospital not enrolled: {hospital_id}", err=True)
        sys.exit(1)
    report = verify_chain(
        session, hospital_pk=hospital.hospital_pk, seq_from=seq_from, seq_to=seq_to
    )
    if as_json:
        click.echo(
            json.dumps(
                {
                    "hospital_id": hospital_id,
                    "anchors": report.anchors,
                    "seq_lo": report.seq_lo,
                    "seq_hi": report.seq_hi,
                    "continuity": "pass" if report.continuity_ok else "fail",
                    "monotonic": "pass" if report.monotonic_ok else "fail",
                    "first_break_at": report.first_break_at,
                    "last_anchored_at": (
                        report.last_anchored_at.isoformat() if report.last_anchored_at else None
                    ),
                }
            )
        )
    else:
        click.echo(f"hospital_id : {hospital_id}")
        click.echo(f"anchors     : {report.anchors}")
        click.echo(f"range       : [{report.seq_lo}..{report.seq_hi}]")
        click.echo(f"continuity  : {'PASS' if report.continuity_ok else 'FAIL'}")
        click.echo(f"monotonic   : {'PASS' if report.monotonic_ok else 'FAIL'}")
        if not report.continuity_ok:
            click.echo(f"[FAIL] chain break at seq={report.first_break_at}")
    if not report.continuity_ok or not report.monotonic_ok:
        sys.exit(1)


# ---------------------------------------------------------------------------
# study show
# ---------------------------------------------------------------------------


@cli.group("study")
def study_group() -> None:
    pass


@study_group.command("show")
@click.option("--pseudo-study-uid", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_study_show(ctx: click.Context, pseudo_study_uid: str, as_json: bool) -> None:
    session = _open_session(ctx.obj["settings"])
    study = session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo_study_uid))
    if study is None:
        click.echo(f"[NOT_FOUND] study not found: {pseudo_study_uid}", err=True)
        sys.exit(1)
    series_rows = list(
        session.scalars(select(Series).where(Series.study_pk == study.study_pk)).all()
    )
    instance_rows = (
        list(
            session.scalars(
                select(Instance).where(Instance.series_pk.in_([s.series_pk for s in series_rows]))
            ).all()
        )
        if series_rows
        else []
    )
    payload = {
        "pseudo_study_uid": study.pseudo_study_uid,
        "hospital_pk": study.hospital_pk,
        "gateway_id": study.gateway_id,
        "central_job_id": study.central_job_id,
        "ingested_at": study.ingested_at.isoformat() if study.ingested_at else None,
        "modality": study.modality,
        "n_series": study.n_series,
        "n_instances": study.n_instances,
        "total_bytes": study.total_bytes,
        "object_keys_sample": [i.object_key for i in instance_rows[:3]],
    }
    if as_json:
        click.echo(json.dumps(payload))
    else:
        for k, v in payload.items():
            click.echo(f"{k:<20} : {v}")


# ---------------------------------------------------------------------------
# withdraw request
# ---------------------------------------------------------------------------


@cli.group("withdraw")
def withdraw_group() -> None:
    pass


@withdraw_group.command("request")
@click.option("--pseudo-study-uid", required=True)
@click.option("--reason", required=True)
@click.pass_context
def cmd_withdraw_request(ctx: click.Context, pseudo_study_uid: str, reason: str) -> None:
    session = _open_session(ctx.obj["settings"])
    study = session.scalar(select(Study).where(Study.pseudo_study_uid == pseudo_study_uid))
    hospital_pk = study.hospital_pk if study else 0
    event = AuditIngestEvent(
        hospital_pk=hospital_pk or 1,
        gateway_id="cli",
        central_job_id=None,
        event="withdraw.stub.invoked",
        pseudo_study_uid=pseudo_study_uid,
        status_code=501,
        error_code=None,
        request_id=f"cli_{datetime.now(tz=UTC).timestamp():.0f}",
        bytes_received=None,
        duration_ms=None,
    )
    session.add(event)
    session.commit()
    click.echo(f"[STUB] withdraw flow not implemented (dev-spec FR-73). reason={reason!r}")


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------


@cli.group("migrate")
def migrate_group() -> None:
    pass


@migrate_group.command("up")
@click.option("--revision", default="head")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def cmd_migrate_up(ctx: click.Context, revision: str, dry_run: bool) -> None:
    settings: Settings = ctx.obj["settings"]
    if dry_run:
        click.echo(f"[DRY-RUN] would run alembic upgrade {revision} on {settings.db.migration_dsn}")
        return
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig
    except ImportError as exc:
        click.echo(f"[ERR] alembic not installed: {exc}", err=True)
        sys.exit(2)
    cfg = AlembicConfig(os.environ.get("ALEMBIC_INI", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.db.migration_dsn)
    alembic_command.upgrade(cfg, revision)
    click.echo(f"[OK] upgraded to {revision}")


@migrate_group.command("current")
@click.pass_context
def cmd_migrate_current(ctx: click.Context) -> None:
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig
    except ImportError as exc:
        click.echo(f"[ERR] alembic not installed: {exc}", err=True)
        sys.exit(2)
    cfg = AlembicConfig(os.environ.get("ALEMBIC_INI", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", ctx.obj["settings"].db.migration_dsn)
    alembic_command.current(cfg)


@migrate_group.command("down")
@click.option("--revision", required=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def cmd_migrate_down(ctx: click.Context, revision: str, dry_run: bool) -> None:
    if dry_run:
        click.echo(f"[DRY-RUN] would downgrade to {revision}")
        return
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(os.environ.get("ALEMBIC_INI", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", ctx.obj["settings"].db.migration_dsn)
    alembic_command.downgrade(cfg, revision)
    click.echo(f"[OK] downgraded to {revision}")


# ---------------------------------------------------------------------------
# init-hospital (dev-spec FR-75)
# ---------------------------------------------------------------------------


@cli.command("init-hospital")
@click.option("--hospital-id", required=True)
@click.option("--name", required=True)
@click.option("--allowed-ruleset-versions", default="v0.1.0")
@click.option("--salt-version", type=int, default=1)
@click.pass_context
def cmd_init_hospital(
    ctx: click.Context,
    hospital_id: str,
    name: str,
    allowed_ruleset_versions: str,
    salt_version: int,
) -> None:
    session = _open_session(ctx.obj["settings"])
    existing = session.scalar(select(Hospital).where(Hospital.hospital_id == hospital_id))
    if existing is not None:
        click.echo(f"[EXISTS] {hospital_id}")
        return
    row = Hospital(
        hospital_id=hospital_id,
        name=name,
        salt_version_current=salt_version,
        allowed_ruleset_versions=[v.strip() for v in allowed_ruleset_versions.split(",")],
    )
    session.add(row)
    session.commit()
    click.echo(f"[OK] enrolled {hospital_id}")


if __name__ == "__main__":
    cli()
