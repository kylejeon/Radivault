"""Click-based fulfillment-admin CLI (dev-spec §4.17 FR-85, design-spec §4).

Exit codes follow BSD sysexits:
- 0   OK
- 64  EX_USAGE        — bad command invocation
- 65  EX_DATAERR      — invalid input / row not found
- 70  EX_SOFTWARE     — unexpected internal failure
- 73  EX_CANTCREAT    — DB mutation failed (e.g., force-advance rejected)
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any

import click

from radivault_fulfillment import __version__
from radivault_fulfillment.config import Settings
from radivault_fulfillment.db.models import (
    DownloadEvent,
    Order,
    OrderItem,
    OrderStateHistory,
    TransferJob,
    TransferJobDeadLetter,
    UnlinkedStudy,
)
from radivault_fulfillment.db.session import get_engine
from radivault_fulfillment.expiration.reaper import reap_expired_orders
from radivault_fulfillment.jobs.dlq import requeue_from_dlq
from radivault_fulfillment.orders.state_machine import (
    is_allowed,
    transition,
)


def _session_factory_from_ctx(ctx: click.Context):
    settings: Settings = ctx.obj["settings"]
    from sqlalchemy.orm import sessionmaker

    engine = get_engine(
        settings.db.admin_dsn,
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.max_overflow,
    )
    return sessionmaker(bind=engine, expire_on_commit=False)


def _emit(obj: Any, *, as_json: bool, no_color: bool = False) -> None:
    if as_json:
        click.echo(json.dumps(obj, default=_json_default, indent=2))
    else:
        click.echo(_human(obj))


def _json_default(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "__dict__"):
        return {k: _json_default(val) for k, val in vars(v).items() if not k.startswith("_")}
    return str(v)


def _human(obj: Any) -> str:
    if isinstance(obj, dict):
        return "\n".join(f"{k}: {v}" for k, v in obj.items())
    if isinstance(obj, list):
        return "\n".join(str(x) for x in obj)
    return str(obj)


@click.group(
    help="RadiVault Order Fulfillment — operator CLI (주문 관리/조사/복구 운영 도구)",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "-c",
    "--config",
    "config_path",
    default=None,
    help="Path to YAML config (overrides RV_FULFILLMENT_CONFIG env)",
)
@click.option("--no-color", is_flag=True, help="Disable ANSI colour")
@click.version_option(version=__version__, prog_name="fulfillment-admin")
@click.pass_context
def cli(ctx: click.Context, config_path: str | None, no_color: bool) -> None:
    ctx.ensure_object(dict)
    settings = Settings.load(config_path)
    ctx.obj["settings"] = settings
    ctx.obj["no_color"] = no_color


# ---------------------------------------------------------------- version
@cli.command("version", help="Print version metadata")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def version_cmd(ctx: click.Context, as_json: bool) -> None:
    import platform

    payload = {
        "service": "radivault-fulfillment",
        "version": __version__,
        "python": platform.python_version(),
    }
    _emit(payload, as_json=as_json)


# ---------------------------------------------------------------- order
@cli.group("order", help="Order inspection/recovery")
def order_group() -> None:
    pass


@order_group.command("inspect", help="Show full order record (order + items + jobs)")
@click.option("--order-id", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def order_inspect(ctx: click.Context, order_id: str, as_json: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        order = s.query(Order).filter_by(order_id=order_id).one_or_none()
        if order is None:
            click.echo(f"order {order_id} not found", err=True)
            sys.exit(65)
        items = s.query(OrderItem).filter_by(order_pk=order.order_pk).all()
        jobs = s.query(TransferJob).filter_by(order_pk=order.order_pk).all()
        history = s.query(OrderStateHistory).filter_by(order_pk=order.order_pk).all()
    payload = {
        "order_id": order.order_id,
        "status": order.status,
        "tier": order.tier,
        "path_type": order.path_type,
        "n_studies": order.n_studies,
        "total_bytes": order.total_bytes,
        "total_estimated_usd": float(order.total_estimated_usd),
        "submitted_at": order.submitted_at,
        "expires_at": order.expires_at,
        "items": [{"pseudo_study_uid": it.pseudo_study_uid, "state": it.state} for it in items],
        "transfer_jobs": [
            {"transfer_job_id": j.transfer_job_id, "state": j.state, "attempts": j.attempt_count}
            for j in jobs
        ],
        "history": [
            {"from": h.from_state, "to": h.to_state, "actor": h.actor, "at": h.at} for h in history
        ],
    }
    _emit(payload, as_json=as_json)


@order_group.command("list", help="List orders by buyer/status")
@click.option("--buyer-id")
@click.option("--status", "status_filter")
@click.option("--limit", default=50, show_default=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def order_list(
    ctx: click.Context, buyer_id: str | None, status_filter: str | None, limit: int, as_json: bool
) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        q = s.query(Order)
        if status_filter:
            q = q.filter(Order.status == status_filter)
        if buyer_id:
            from radivault_search.db.models import Buyer

            buyer = s.query(Buyer).filter_by(buyer_id=buyer_id).one_or_none()
            if buyer is None:
                click.echo(f"buyer {buyer_id} not found", err=True)
                sys.exit(65)
            q = q.filter(Order.buyer_pk == buyer.buyer_pk)
        rows = q.order_by(Order.submitted_at.desc()).limit(limit).all()
    _emit(
        [
            {
                "order_id": o.order_id,
                "status": o.status,
                "tier": o.tier,
                "n_studies": o.n_studies,
                "submitted_at": o.submitted_at,
            }
            for o in rows
        ],
        as_json=as_json,
    )


@order_group.command("history", help="Show order_state_history for an order")
@click.option("--order-id", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def order_history(ctx: click.Context, order_id: str, as_json: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        order = s.query(Order).filter_by(order_id=order_id).one_or_none()
        if order is None:
            click.echo(f"order {order_id} not found", err=True)
            sys.exit(65)
        rows = (
            s.query(OrderStateHistory)
            .filter(OrderStateHistory.order_pk == order.order_pk)
            .order_by(OrderStateHistory.at.asc())
            .all()
        )
    _emit(
        [
            {
                "from": h.from_state,
                "to": h.to_state,
                "event": h.event,
                "actor": h.actor,
                "at": h.at,
                "reason": h.reason,
            }
            for h in rows
        ],
        as_json=as_json,
    )


@order_group.command("stats", help="Aggregate order state counts")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def order_stats(ctx: click.Context, as_json: bool) -> None:
    from sqlalchemy import func

    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        rows = s.query(Order.status, func.count(Order.order_pk)).group_by(Order.status).all()
    _emit({status: int(n) for status, n in rows}, as_json=as_json)


@order_group.command("force-advance", help="Admin FSM override (advance state)")
@click.option("--order-id", required=True)
@click.option("--to", "to_state", required=True)
@click.option("--reason", required=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def order_force_advance(
    ctx: click.Context, order_id: str, to_state: str, reason: str, dry_run: bool
) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        order = s.query(Order).filter_by(order_id=order_id).one_or_none()
        if order is None:
            click.echo(f"order {order_id} not found", err=True)
            sys.exit(65)
        if dry_run:
            click.echo(f"would advance {order.order_id} from {order.status} to {to_state}")
            return
        if not is_allowed(order.status, to_state, "admin"):
            click.echo(
                f"ERR: transition {order.status} -> {to_state} not allowed by admin",
                err=True,
            )
            sys.exit(73)
        transition(
            s,
            order_pk=order.order_pk,
            from_state=order.status,
            to_state=to_state,
            actor="admin",
            event="order.force_advance",
            reason=reason,
            actor_ref="fulfillment-admin",
        )
        s.commit()
    click.echo(f"ok: {order_id} -> {to_state}")


@order_group.command("cancel", help="Admin cancellation (force supported for in-flight)")
@click.option("--order-id", required=True)
@click.option("--force", is_flag=True)
@click.option("--reason", required=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def order_cancel_cmd(
    ctx: click.Context, order_id: str, force: bool, reason: str, dry_run: bool
) -> None:
    from radivault_fulfillment.cancellation.service import cancel_as_admin, cancel_as_buyer

    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        order = s.query(Order).filter_by(order_id=order_id).one_or_none()
        if order is None:
            click.echo(f"order {order_id} not found", err=True)
            sys.exit(65)
        if dry_run:
            click.echo(f"would cancel {order_id} (current status={order.status})")
            return
        try:
            if force:
                cancel_as_admin(s, order=order, admin_user="fulfillment-admin", reason=reason)
            else:
                cancel_as_buyer(s, order=order, reason=reason)
            s.commit()
        except Exception as exc:
            click.echo(f"ERR: {exc}", err=True)
            sys.exit(73)
    click.echo(f"ok: {order_id} cancelled")


@order_group.command("expire-stale", help="Manually trigger expiry reaper")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def order_expire_stale(ctx: click.Context, dry_run: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        if dry_run:
            from radivault_fulfillment.orders.repository import find_expired_orders

            rows = find_expired_orders(s, limit=100)
            click.echo(f"would expire {len(rows)} orders")
            return
        n = reap_expired_orders(s, limit=100)
        s.commit()
    click.echo(f"expired: {n}")


# ---------------------------------------------------------------- transfer-job
@cli.group("transfer-job", help="Transfer-job inspection/recovery")
def tj_group() -> None:
    pass


@tj_group.command("inspect", help="Show a transfer_job row")
@click.option("--job-id", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def tj_inspect(ctx: click.Context, job_id: str, as_json: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        job = s.query(TransferJob).filter_by(transfer_job_id=job_id).one_or_none()
        if job is None:
            click.echo(f"job {job_id} not found", err=True)
            sys.exit(65)
    _emit(
        {
            "transfer_job_id": job.transfer_job_id,
            "state": job.state,
            "hospital_pk": job.hospital_pk,
            "attempts": job.attempt_count,
            "lease_owner": job.lease_owner,
            "lease_expires_at": job.lease_expires_at,
            "studies": job.studies,
            "last_error": job.last_error_detail,
        },
        as_json=as_json,
    )


@tj_group.command("list", help="List transfer_jobs by state/hospital")
@click.option("--state", default=None)
@click.option("--hospital-pk", type=int, default=None)
@click.option("--limit", default=50)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def tj_list(
    ctx: click.Context,
    state: str | None,
    hospital_pk: int | None,
    limit: int,
    as_json: bool,
) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        q = s.query(TransferJob)
        if state:
            q = q.filter(TransferJob.state == state)
        if hospital_pk is not None:
            q = q.filter(TransferJob.hospital_pk == hospital_pk)
        rows = q.order_by(TransferJob.created_at.desc()).limit(limit).all()
    _emit(
        [
            {
                "transfer_job_id": r.transfer_job_id,
                "state": r.state,
                "attempts": r.attempt_count,
                "hospital_pk": r.hospital_pk,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        as_json=as_json,
    )


@tj_group.command("requeue", help="Force a transfer_job back to queued")
@click.option("--job-id", required=True)
@click.option("--reset-attempts", is_flag=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def tj_requeue(ctx: click.Context, job_id: str, reset_attempts: bool, dry_run: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        job = s.query(TransferJob).filter_by(transfer_job_id=job_id).one_or_none()
        if job is None:
            click.echo(f"job {job_id} not found", err=True)
            sys.exit(65)
        if dry_run:
            click.echo(f"would requeue {job_id} (current state={job.state})")
            return
        job.state = "queued"
        job.lease_owner = None
        job.lease_expires_at = None
        if reset_attempts:
            job.attempt_count = 0
        s.commit()
    click.echo(f"ok: requeued {job_id}")


@tj_group.command("release-lease", help="Clear a claim lease without state change")
@click.option("--job-id", required=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def tj_release_lease(ctx: click.Context, job_id: str, dry_run: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        job = s.query(TransferJob).filter_by(transfer_job_id=job_id).one_or_none()
        if job is None:
            click.echo(f"job {job_id} not found", err=True)
            sys.exit(65)
        if dry_run:
            click.echo(f"would release lease on {job_id}")
            return
        job.lease_owner = None
        job.lease_expires_at = None
        s.commit()
    click.echo(f"ok: lease released {job_id}")


# ---------------------------------------------------------------- dlq
@cli.group("dlq", help="Dead-letter queue tools")
def dlq_group() -> None:
    pass


@dlq_group.command("dump", help="List unresolved DLQ entries")
@click.option("--limit", default=50)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def dlq_dump(ctx: click.Context, limit: int, as_json: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        rows = (
            s.query(TransferJobDeadLetter)
            .filter(TransferJobDeadLetter.resolved_at.is_(None))
            .order_by(TransferJobDeadLetter.dead_at.desc())
            .limit(limit)
            .all()
        )
    _emit(
        [
            {
                "dlq_pk": r.dlq_pk,
                "transfer_job_pk": r.transfer_job_pk,
                "reason_code": r.reason_code,
                "attempts": r.attempts,
                "dead_at": r.dead_at,
            }
            for r in rows
        ],
        as_json=as_json,
    )


@dlq_group.command("requeue", help="Requeue a dead transfer_job and close DLQ")
@click.option("--job-id", required=True)
@click.option("--reset-attempts/--keep-attempts", default=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def dlq_requeue_cmd(ctx: click.Context, job_id: str, reset_attempts: bool, dry_run: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        if dry_run:
            click.echo(f"would requeue dead job {job_id}")
            return
        try:
            requeue_from_dlq(
                s,
                transfer_job_id=job_id,
                resolved_by="fulfillment-admin",
                reset_attempts=reset_attempts,
            )
            s.commit()
        except Exception as exc:
            click.echo(f"ERR: {exc}", err=True)
            sys.exit(73)
    click.echo(f"ok: requeued {job_id}")


@dlq_group.command("fail", help="Mark DLQ entry as permanently failed")
@click.option("--job-id", required=True)
@click.option("--reason", required=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def dlq_fail_cmd(ctx: click.Context, job_id: str, reason: str, dry_run: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        job = s.query(TransferJob).filter_by(transfer_job_id=job_id).one_or_none()
        if job is None:
            click.echo(f"job {job_id} not found", err=True)
            sys.exit(65)
        dlq = (
            s.query(TransferJobDeadLetter)
            .filter(
                TransferJobDeadLetter.transfer_job_pk == job.transfer_job_pk,
                TransferJobDeadLetter.resolved_at.is_(None),
            )
            .first()
        )
        if dlq is None:
            click.echo(f"no open DLQ entry for {job_id}", err=True)
            sys.exit(65)
        if dry_run:
            click.echo(f"would mark DLQ {dlq.dlq_pk} as failed_final")
            return
        dlq.resolved_at = datetime.now(tz=UTC)
        dlq.resolved_by = "fulfillment-admin"
        dlq.resolution = "failed_final"
        dlq.reason_detail = (dlq.reason_detail or "") + f" | manual: {reason}"
        s.commit()
    click.echo("ok: marked failed_final")


# ---------------------------------------------------------------- download
@cli.group("download", help="Download audit tools")
def download_group() -> None:
    pass


@download_group.command("audit", help="Show download_event rows for an order")
@click.option("--order-id", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def download_audit_cmd(ctx: click.Context, order_id: str, as_json: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        order = s.query(Order).filter_by(order_id=order_id).one_or_none()
        if order is None:
            click.echo(f"order {order_id} not found", err=True)
            sys.exit(65)
        rows = (
            s.query(DownloadEvent)
            .filter(DownloadEvent.order_pk == order.order_pk)
            .order_by(DownloadEvent.ts.desc())
            .all()
        )
    _emit(
        [
            {
                "event_type": r.event_type,
                "ts": r.ts,
                "signature_hash": r.signature_hash,
                "src_ip": r.src_ip,
                "user_agent": r.user_agent,
            }
            for r in rows
        ],
        as_json=as_json,
    )


@download_group.command("mint-stats", help="Aggregate mint counts over a window")
@click.option("--since", required=True)
@click.option("--until", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def download_mint_stats(ctx: click.Context, since: str, until: str, as_json: bool) -> None:
    from sqlalchemy import func

    since_dt = datetime.fromisoformat(since)
    until_dt = datetime.fromisoformat(until)
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        total = (
            s.query(func.count(DownloadEvent.event_pk))
            .filter(
                DownloadEvent.event_type == "url_minted",
                DownloadEvent.ts >= since_dt,
                DownloadEvent.ts < until_dt,
            )
            .scalar()
        )
    _emit(
        {"url_minted_total": int(total or 0), "since": since, "until": until},
        as_json=as_json,
    )


# ---------------------------------------------------------------- unlinked
@cli.group("unlinked", help="Unlinked study (orphaned) tools")
def unlinked_group() -> None:
    pass


@unlinked_group.command("list", help="List unlinked_study rows available for reassignment")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def unlinked_list(ctx: click.Context, as_json: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        rows = (
            s.query(UnlinkedStudy)
            .filter(UnlinkedStudy.disposition == "available_for_reassignment")
            .order_by(UnlinkedStudy.detached_at.desc())
            .all()
        )
    _emit(
        [
            {
                "pseudo_study_uid": r.pseudo_study_uid,
                "hospital_pk": r.hospital_pk,
                "detached_at": r.detached_at,
                "original_order_pk": r.original_order_pk,
            }
            for r in rows
        ],
        as_json=as_json,
    )


@unlinked_group.command("reassign", help="Attach an unlinked study to a new order")
@click.option("--study-uid", required=True)
@click.option("--new-order-id", required=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def unlinked_reassign(ctx: click.Context, study_uid: str, new_order_id: str, dry_run: bool) -> None:
    factory = _session_factory_from_ctx(ctx)
    with factory() as s:
        un = (
            s.query(UnlinkedStudy)
            .filter(
                UnlinkedStudy.pseudo_study_uid == study_uid,
                UnlinkedStudy.disposition == "available_for_reassignment",
            )
            .first()
        )
        if un is None:
            click.echo(f"no available unlinked study for {study_uid}", err=True)
            sys.exit(65)
        new_order = s.query(Order).filter_by(order_id=new_order_id).one_or_none()
        if new_order is None:
            click.echo(f"target order {new_order_id} not found", err=True)
            sys.exit(65)
        if dry_run:
            click.echo(f"would attach {study_uid} to {new_order_id}")
            return
        un.disposition = "reassigned"
        un.reassigned_to_order_pk = new_order.order_pk
        un.reassigned_at = datetime.now(tz=UTC)
        s.commit()
    click.echo(f"ok: reassigned {study_uid} -> {new_order_id}")


# ---------------------------------------------------------------- migrate
@cli.group("migrate", help="Alembic helpers")
def migrate_group() -> None:
    pass


@migrate_group.command("current", help="Print current alembic revision")
@click.pass_context
def migrate_current(ctx: click.Context) -> None:
    from alembic import command
    from alembic.config import Config

    cfg_path = ctx.obj.get("alembic_ini") or "alembic.ini"
    cfg = Config(cfg_path)
    command.current(cfg)


@migrate_group.command("up", help="Run alembic upgrade")
@click.option("--revision", default="head")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def migrate_up(ctx: click.Context, revision: str, dry_run: bool) -> None:
    from alembic import command
    from alembic.config import Config

    cfg_path = ctx.obj.get("alembic_ini") or "alembic.ini"
    cfg = Config(cfg_path)
    if dry_run:
        click.echo(f"would run: alembic upgrade {revision}")
        return
    command.upgrade(cfg, revision)


if __name__ == "__main__":
    cli()
