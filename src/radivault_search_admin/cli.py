"""``search-admin`` CLI — operator tooling (dev-spec §4.11, design-spec §3).

13 subcommands:

    search-admin
    ├── buyer (create, show, list, update)          # 4
    ├── key (issue, revoke, list)                    # 3
    ├── stats (query-count, top-filters)             # 2
    ├── facet (warm)                                 # 1
    ├── migrate (up, current, down)                  # 3 (up/current required by FR-57; down included)
    └── version                                       # 1
                                                      = 14 total; dev-spec lists
                                                      13 distinct FR-57 subcommands
                                                      (we include ``version`` for parity
                                                      with ingest-admin).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import click
from sqlalchemy import func, select

from radivault_central.db.models import Base as CentralBase
from radivault_search import __version__ as search_version
from radivault_search.auth.buyer_tokens import (
    PREFIX_LIVE,
    PREFIX_TEST,
    generate_buyer_key,
)
from radivault_search.config import Settings
from radivault_search.db.models import Buyer, BuyerApiKey, SearchAudit
from radivault_search.db.session import (
    get_engine,
    get_session_factory,
    reset_for_tests,
)

EXIT_OK = 0
EXIT_USAGE = 64
EXIT_NOT_FOUND = 69
EXIT_INTERNAL = 70


def _load_settings(config: str | None, database_url: str | None) -> Settings:
    settings = Settings.load(config_path=config)
    if database_url:
        settings.db.dsn = database_url
        settings.db.admin_dsn = database_url
    return settings


def _open_session(settings: Settings):
    # admin CLI uses the elevated DSN so it can write to buyer/buyer_api_key.
    dsn = settings.db.admin_dsn or settings.db.dsn
    engine = get_engine(
        dsn,
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.max_overflow,
    )
    CentralBase.metadata.create_all(engine)  # safe for SQLite; no-op on PG
    return get_session_factory(dsn)()


@click.group(
    name="search-admin",
    help="RadiVault Search operator CLI — dev-spec FR-56..FR-59.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option("-c", "--config", type=click.Path(), default=None)
@click.option("--database-url", type=str, default=None)
@click.option("--log-level", type=str, default="INFO")
@click.option("--no-color", is_flag=True, default=False)
@click.version_option(search_version, "-V", "--version")
@click.pass_context
def cli(
    ctx: click.Context,
    config: str | None,
    database_url: str | None,
    log_level: str,
    no_color: bool,
) -> None:
    reset_for_tests()
    ctx.ensure_object(dict)
    ctx.obj["settings"] = _load_settings(config, database_url)
    ctx.obj["no_color"] = no_color
    os.environ.setdefault("RV_SEARCH_LOG_LEVEL", log_level)


# ---------------------------------------------------------------------------
# version  (subcommand #1 — also invocable via --version)
# ---------------------------------------------------------------------------


@cli.command("version")
@click.option("--json", "as_json", is_flag=True)
def cmd_version(as_json: bool) -> None:
    payload = {
        "service": "radivault-search",
        "version": search_version,
        "git_sha": os.environ.get("RADIVAULT_GIT_SHA", "unknown"),
        "built_at": os.environ.get("RADIVAULT_BUILT_AT", "unknown"),
        "api_contract_version": os.environ.get("RADIVAULT_API_CONTRACT_VERSION", "1"),
        "python": sys.version.split()[0],
    }
    click.echo(
        json.dumps(payload) if as_json else "\n".join(f"{k:<14}{v}" for k, v in payload.items())
    )


# ---------------------------------------------------------------------------
# buyer group (create/show/list/update  — 4 subcommands)
# ---------------------------------------------------------------------------


@cli.group("buyer")
def buyer_group() -> None:
    """Buyer (company) lifecycle."""


@buyer_group.command("create")
@click.option("--company", required=True)
@click.option("--contact-email", required=True)
@click.option("--tier", type=click.Choice(["preview", "paid"]), default="preview")
@click.option(
    "--buyer-id", default=None, help="Optional explicit buyer_id; auto-generated if omitted"
)
@click.option("--note", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_buyer_create(
    ctx: click.Context,
    company: str,
    contact_email: str,
    tier: str,
    buyer_id: str | None,
    note: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    settings: Settings = ctx.obj["settings"]
    session = _open_session(settings)
    if buyer_id is None:
        safe = "".join(c.lower() for c in company if c.isalnum())[:10] or "buy"
        buyer_id = f"buy_{safe}_{int(datetime.now(tz=UTC).timestamp()) % 1000:03d}"
    existing = session.scalar(select(Buyer).where(Buyer.buyer_id == buyer_id))
    if existing is not None:
        click.echo(f"[ERR_ADMIN_BUYER_DUPLICATE] buyer_id already exists: {buyer_id}", err=True)
        sys.exit(EXIT_NOT_FOUND)
    if dry_run:
        click.echo(
            json.dumps(
                {
                    "buyer_id": buyer_id,
                    "company": company,
                    "contact_email": contact_email,
                    "tier": tier,
                    "note": note,
                    "dry_run": True,
                }
            )
        )
        return
    row = Buyer(
        buyer_id=buyer_id,
        name=company,
        contact_email=contact_email,
        tier=tier,
        note=note,
    )
    session.add(row)
    session.commit()
    payload = {
        "buyer_id": row.buyer_id,
        "company": row.name,
        "contact_email": row.contact_email,
        "tier": row.tier,
        "note": row.note,
        "enrolled_at": row.enrolled_at.isoformat() if row.enrolled_at else None,
    }
    if as_json:
        click.echo(json.dumps(payload))
    else:
        click.echo("\n".join(f"{k:<14}: {v}" for k, v in payload.items()))


@buyer_group.command("show")
@click.option("--buyer-id", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_buyer_show(ctx: click.Context, buyer_id: str, as_json: bool) -> None:
    session = _open_session(ctx.obj["settings"])
    row = session.scalar(select(Buyer).where(Buyer.buyer_id == buyer_id))
    if row is None:
        click.echo(f"[ERR_ADMIN_BUYER_NOT_FOUND] {buyer_id}", err=True)
        sys.exit(EXIT_NOT_FOUND)
    payload = {
        "buyer_id": row.buyer_id,
        "company": row.name,
        "contact_email": row.contact_email,
        "tier": row.tier,
        "active": row.active,
        "enrolled_at": row.enrolled_at.isoformat() if row.enrolled_at else None,
        "note": row.note,
    }
    click.echo(
        json.dumps(payload) if as_json else "\n".join(f"{k:<14}: {v}" for k, v in payload.items())
    )


@buyer_group.command("list")
@click.option("--tier", type=click.Choice(["preview", "paid"]), default=None)
@click.option("--active-only", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_buyer_list(ctx: click.Context, tier: str | None, active_only: bool, as_json: bool) -> None:
    session = _open_session(ctx.obj["settings"])
    stmt = select(Buyer)
    if tier:
        stmt = stmt.where(Buyer.tier == tier)
    if active_only:
        stmt = stmt.where(Buyer.active.is_(True))
    rows = list(session.scalars(stmt).all())
    out = [
        {
            "buyer_id": r.buyer_id,
            "company": r.name,
            "tier": r.tier,
            "active": r.active,
            "contact_email": r.contact_email,
        }
        for r in rows
    ]
    if as_json:
        click.echo(json.dumps({"buyers": out, "count": len(out)}))
    else:
        if not out:
            click.echo("(no buyers)")
            return
        click.echo(f"{'BUYER_ID':<18}{'COMPANY':<24}{'TIER':<10}{'ACTIVE':<8}")
        for item in out:
            click.echo(
                f"{item['buyer_id']:<18}{item['company']:<24}{item['tier']:<10}"
                f"{'yes' if item['active'] else 'no':<8}"
            )


@buyer_group.command("update")
@click.option("--buyer-id", required=True)
@click.option("--tier", type=click.Choice(["preview", "paid"]))
@click.option("--note", default=None)
@click.option("--active/--inactive", default=None)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def cmd_buyer_update(
    ctx: click.Context,
    buyer_id: str,
    tier: str | None,
    note: str | None,
    active: bool | None,
    dry_run: bool,
) -> None:
    session = _open_session(ctx.obj["settings"])
    row = session.scalar(select(Buyer).where(Buyer.buyer_id == buyer_id))
    if row is None:
        click.echo(f"[ERR_ADMIN_BUYER_NOT_FOUND] {buyer_id}", err=True)
        sys.exit(EXIT_NOT_FOUND)
    if dry_run:
        click.echo(json.dumps({"buyer_id": buyer_id, "dry_run": True}))
        return
    if tier is not None:
        row.tier = tier
    if note is not None:
        row.note = note
    if active is not None:
        row.active = active
    session.commit()
    click.echo(f"[OK] updated buyer {buyer_id}")


# ---------------------------------------------------------------------------
# key group (issue / revoke / list — 3 subcommands)
# ---------------------------------------------------------------------------


@cli.group("key")
def key_group() -> None:
    """API-key lifecycle."""


@key_group.command("issue")
@click.option("--buyer-id", required=True)
@click.option("--tier", type=click.Choice(["preview", "paid"]), default=None)
@click.option("--expires-days", type=int, default=180)
@click.option("--scope-json", default=None, help="JSON-encoded scope override")
@click.option("--test-prefix", is_flag=True, help="Issue rv_test_* instead of rv_live_*")
@click.option("--dry-run", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_key_issue(
    ctx: click.Context,
    buyer_id: str,
    tier: str | None,
    expires_days: int,
    scope_json: str | None,
    test_prefix: bool,
    dry_run: bool,
    as_json: bool,
) -> None:
    session = _open_session(ctx.obj["settings"])
    buyer = session.scalar(select(Buyer).where(Buyer.buyer_id == buyer_id))
    if buyer is None:
        click.echo(f"[ERR_ADMIN_BUYER_NOT_FOUND] {buyer_id}", err=True)
        sys.exit(EXIT_NOT_FOUND)

    scope_obj: dict = {}
    if scope_json:
        try:
            scope_obj = json.loads(scope_json)
        except Exception as exc:
            click.echo(f"[ERR_ADMIN_USAGE] invalid scope-json: {exc}", err=True)
            sys.exit(EXIT_USAGE)

    bundle = generate_buyer_key(prefix=PREFIX_TEST if test_prefix else PREFIX_LIVE)
    expires_at = datetime.now(tz=UTC) + timedelta(days=expires_days) if expires_days else None
    use_tier = tier or buyer.tier
    if dry_run:
        click.echo(
            json.dumps(
                {
                    "buyer_id": buyer_id,
                    "kid": bundle.kid,
                    "tier": use_tier,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "dry_run": True,
                }
            )
        )
        return
    row = BuyerApiKey(
        buyer_pk=buyer.buyer_pk,
        kid=bundle.kid,
        token_hash=bundle.hash,
        tier=use_tier,
        scope_json=scope_obj,
        expires_at=expires_at,
    )
    session.add(row)
    session.commit()
    if as_json:
        click.echo(
            json.dumps(
                {
                    "buyer_id": buyer_id,
                    "kid": bundle.kid,
                    "plaintext": bundle.plaintext,
                    "tier": use_tier,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                }
            )
        )
    else:
        click.echo(
            "\n".join(
                [
                    "=" * 72,
                    " RadiVault Search — new API key issued",
                    "=" * 72,
                    f" buyer_id    : {buyer_id}",
                    f" kid         : {bundle.kid}",
                    f" tier        : {use_tier}",
                    f" expires_at  : {expires_at.isoformat() if expires_at else 'never'}",
                    "-" * 72,
                    " Plaintext key (shown ONCE, store now):",
                    "",
                    f"   {bundle.plaintext}",
                    "",
                    "=" * 72,
                ]
            )
        )


@key_group.command("revoke")
@click.option("--kid", required=True)
@click.option("--reason", default=None)
@click.pass_context
def cmd_key_revoke(ctx: click.Context, kid: str, reason: str | None) -> None:
    session = _open_session(ctx.obj["settings"])
    row = session.scalar(select(BuyerApiKey).where(BuyerApiKey.kid == kid))
    if row is None:
        click.echo(f"[ERR_ADMIN_KEY_NOT_FOUND] {kid}", err=True)
        sys.exit(EXIT_NOT_FOUND)
    if row.revoked_at is not None:
        click.echo(f"[ERR_ADMIN_KEY_ALREADY_REVOKED] {kid}", err=True)
        sys.exit(EXIT_NOT_FOUND)
    row.revoked_at = datetime.now(tz=UTC)
    if reason:
        row.note = f"{row.note or ''}\nrevoked_reason={reason}".strip()
    session.commit()
    click.echo(f"[OK] revoked {kid} at {row.revoked_at.isoformat()}")


@key_group.command("list")
@click.option("--buyer-id", default=None)
@click.option("--include-revoked", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_key_list(
    ctx: click.Context,
    buyer_id: str | None,
    include_revoked: bool,
    as_json: bool,
) -> None:
    session = _open_session(ctx.obj["settings"])
    stmt = select(BuyerApiKey, Buyer).join(Buyer, BuyerApiKey.buyer_pk == Buyer.buyer_pk)
    if buyer_id:
        stmt = stmt.where(Buyer.buyer_id == buyer_id)
    rows = session.execute(stmt).all()
    out: list[dict[str, Any]] = []
    for k, b in rows:
        status = "active"
        if k.revoked_at is not None:
            status = "revoked"
        elif k.expires_at:
            # SQLite loses tzinfo; normalise both sides to UTC-aware.
            exp = k.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if exp < datetime.now(tz=UTC):
                status = "expired"
        if status == "revoked" and not include_revoked:
            continue
        out.append(
            {
                "buyer_id": b.buyer_id,
                "kid": k.kid,
                "tier": k.tier,
                "issued_at": k.issued_at.isoformat() if k.issued_at else None,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "status": status,
            }
        )
    if as_json:
        click.echo(json.dumps({"keys": out, "count": len(out)}))
    else:
        if not out:
            click.echo("(no keys)")
            return
        click.echo(f"{'BUYER_ID':<18}{'KID':<12}{'TIER':<10}{'STATUS':<10}")
        for item in out:
            click.echo(
                f"{item['buyer_id']:<18}{item['kid']:<12}{item['tier'] or '-':<10}"
                f"{item['status']:<10}"
            )


# ---------------------------------------------------------------------------
# stats group (query-count, top-filters)
# ---------------------------------------------------------------------------


@cli.group("stats")
def stats_group() -> None:
    """Usage reporting."""


@stats_group.command("query-count")
@click.option("--buyer-id", required=True)
@click.option("--since", required=True, help="ISO timestamp or 'YYYY-MM-DD'")
@click.option("--until", default=None, help="ISO timestamp; defaults to now")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_stats_query_count(
    ctx: click.Context,
    buyer_id: str,
    since: str,
    until: str | None,
    as_json: bool,
) -> None:
    session = _open_session(ctx.obj["settings"])
    buyer = session.scalar(select(Buyer).where(Buyer.buyer_id == buyer_id))
    if buyer is None:
        click.echo(f"[ERR_ADMIN_BUYER_NOT_FOUND] {buyer_id}", err=True)
        sys.exit(EXIT_NOT_FOUND)
    since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    until_dt = (
        datetime.fromisoformat(until.replace("Z", "+00:00")) if until else datetime.now(tz=UTC)
    )
    stmt = (
        select(SearchAudit.status_code, func.count(SearchAudit.audit_pk))
        .where(SearchAudit.buyer_pk == buyer.buyer_pk)
        .where(SearchAudit.created_at >= since_dt)
        .where(SearchAudit.created_at <= until_dt)
        .group_by(SearchAudit.status_code)
    )
    counts = {str(k): int(v) for k, v in session.execute(stmt).all()}
    total = sum(counts.values())
    payload = {
        "buyer_id": buyer_id,
        "since": since_dt.isoformat(),
        "until": until_dt.isoformat(),
        "total": total,
        "by_status": counts,
    }
    click.echo(
        json.dumps(payload) if as_json else "\n".join(f"{k:<14}: {v}" for k, v in payload.items())
    )


@stats_group.command("top-filters")
@click.option("--limit", type=int, default=10)
@click.option("--since", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_stats_top_filters(ctx: click.Context, limit: int, since: str, as_json: bool) -> None:
    session = _open_session(ctx.obj["settings"])
    since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    stmt = (
        select(SearchAudit.filter_sha256, func.count(SearchAudit.audit_pk))
        .where(SearchAudit.created_at >= since_dt)
        .where(SearchAudit.filter_sha256.is_not(None))
        .group_by(SearchAudit.filter_sha256)
        .order_by(func.count(SearchAudit.audit_pk).desc())
        .limit(limit)
    )
    out = [{"filter_sha256": sha, "count": int(c)} for sha, c in session.execute(stmt).all()]
    if as_json:
        click.echo(json.dumps({"top_filters": out, "limit": limit}))
    else:
        for row in out:
            click.echo(f"{row['filter_sha256']:<64}  {row['count']}")


# ---------------------------------------------------------------------------
# facet warm (1)
# ---------------------------------------------------------------------------


@cli.group("facet")
def facet_group() -> None:
    """Facet cache management."""


@facet_group.command("warm")
@click.pass_context
def cmd_facet_warm(ctx: click.Context) -> None:
    click.echo("[OK] facet warm requested (cache will be populated on next /v1/search/facets).")


# ---------------------------------------------------------------------------
# migrate group (up / current / down — 3)
# ---------------------------------------------------------------------------


@cli.group("migrate")
def migrate_group() -> None:
    """Alembic wrapper."""


@migrate_group.command("up")
@click.option("--revision", default="head")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def cmd_migrate_up(ctx: click.Context, revision: str, dry_run: bool) -> None:
    settings: Settings = ctx.obj["settings"]
    if dry_run:
        click.echo(f"[DRY-RUN] alembic upgrade {revision} on {settings.db.migration_dsn}")
        return
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(os.environ.get("ALEMBIC_INI", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.db.migration_dsn)
    alembic_command.upgrade(cfg, revision)
    click.echo(f"[OK] upgraded to {revision}")


@migrate_group.command("current")
@click.pass_context
def cmd_migrate_current(ctx: click.Context) -> None:
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(os.environ.get("ALEMBIC_INI", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", ctx.obj["settings"].db.migration_dsn)
    alembic_command.current(cfg)


@migrate_group.command("down")
@click.option("--revision", required=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def cmd_migrate_down(ctx: click.Context, revision: str, dry_run: bool) -> None:
    if dry_run:
        click.echo(f"[DRY-RUN] alembic downgrade {revision}")
        return
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(os.environ.get("ALEMBIC_INI", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", ctx.obj["settings"].db.migration_dsn)
    alembic_command.downgrade(cfg, revision)
    click.echo(f"[OK] downgraded to {revision}")


if __name__ == "__main__":
    cli()
