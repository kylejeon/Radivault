"""Click-based CLI for the gateway agent.

Implements the command tree described in design-spec §3 and dev-spec §4.6.
Exit codes match §7.4 / §3.9.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import click

from radivault_gateway import RULESET_VERSION, __version__
from radivault_gateway.audit import AuditLogger, verify_chain
from radivault_gateway.config import ConfigError, GatewayConfig, load_config
from radivault_gateway.logging_config import configure_logging

DEFAULT_CONFIG_PATH = os.environ.get("RADIVAULT_CONFIG", "/etc/radivault/gateway.yml")


def _load_or_exit(path: str) -> GatewayConfig:
    try:
        return load_config(path)
    except ConfigError as exc:
        click.echo(exc.format_human(), err=True)
        # Map code prefixes to exit codes.
        if exc.code.startswith("ERR_CFG_"):
            sys.exit(64)
        sys.exit(70)


@click.group(
    help="RadiVault Gateway Agent — PACS → De-ID → Central Upload\n"
    "병원 내 DICOM 익명화 게이트웨이 / Hospital on-premise DICOM de-identification gateway",
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.option(
    "-c",
    "--config",
    "config_path",
    default=DEFAULT_CONFIG_PATH,
    show_default=True,
    help="Path to config YAML (환경변수 RADIVAULT_CONFIG 로도 지정 가능)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARN", "WARNING", "ERROR"], case_sensitive=False),
    default=None,
    help="Override logging level",
)
@click.option("--no-color", is_flag=True, help="Disable ANSI colour output")
@click.option("--quiet", is_flag=True, help="Suppress INFO-level output")
@click.version_option(version=__version__, prog_name="radivault-gateway")
@click.pass_context
def cli(
    ctx: click.Context,
    config_path: str,
    log_level: str | None,
    no_color: bool,
    quiet: bool,
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["log_level"] = log_level
    ctx.obj["no_color"] = no_color or os.environ.get("NO_COLOR") is not None
    ctx.obj["quiet"] = quiet
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---- version ----


@cli.command(help="Print agent version and build info (버전 정보)")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON")
def version(json_output: bool) -> None:
    info = {
        "agent": __version__,
        "ruleset": RULESET_VERSION,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
    }
    try:
        import pydicom  # type: ignore[import-not-found]

        info["pydicom"] = pydicom.__version__
    except Exception:
        info["pydicom"] = "unknown"
    if json_output:
        click.echo(json.dumps(info, indent=0).replace("\n", ""))
        return
    click.echo(f"gateway-agent  {info['agent']}")
    click.echo(f"ruleset        {info['ruleset']}")
    click.echo(f"python         {info['python']}")
    click.echo(f"pydicom        {info['pydicom']}")
    click.echo(f"platform       {info['platform']}")


# ---- audit verify ----


@cli.group(help="Audit log commands")
def audit() -> None:  # pragma: no cover - click group wrapper
    pass


@audit.command("verify", help="Verify audit log SHA-256 hash chain (체인 무결성 검증)")
@click.argument("path", type=click.Path(exists=False, dir_okay=False, path_type=Path))
def audit_verify(path: Path) -> None:
    if not path.exists():
        click.echo(
            f"[ERR_AUD_001] 감사 로그 파일을 찾을 수 없습니다 / audit log not found: {path}",
            err=True,
        )
        sys.exit(2)
    click.echo(f"Reading {path}...")
    result = verify_chain(path)
    if result.ok:
        click.echo(f"PASS  seq range [0, {result.head_seq}]  head_hash={result.head_hash}")
        click.echo(f"      {result.lines} lines verified")
        sys.exit(0)
    click.echo(f"FAIL  chain broken at seq={result.first_mismatch_seq}", err=True)
    if result.expected_prev_hash is not None:
        click.echo(f"      expected prev_hash={result.expected_prev_hash}", err=True)
    if result.actual_prev_hash is not None:
        click.echo(f"      actual   prev_hash={result.actual_prev_hash}", err=True)
    if result.error:
        click.echo(f"      error: {result.error}", err=True)
    sys.exit(1)


# ---- de-id-test ----


@cli.command("de-id-test", help="Dry-run de-identification on a single DICOM (단일 파일 테스트)")
@click.argument("input_path", type=click.Path(exists=False, dir_okay=False, path_type=Path))
@click.option(
    "-o", "--output", "output_path", type=click.Path(dir_okay=False, path_type=Path), default=None
)
@click.option("--show-diff", is_flag=True, help="Show tag-by-tag before/after table")
@click.pass_context
def de_id_test(
    ctx: click.Context,
    input_path: Path,
    output_path: Path | None,
    show_diff: bool,
) -> None:
    if not input_path.exists():
        click.echo(
            f"[ERR_DEID_010] 입력 파일을 찾을 수 없습니다 / input file not found: {input_path}",
            err=True,
        )
        sys.exit(1)
    try:
        import pydicom

        ds_orig = pydicom.dcmread(input_path, force=False)
    except Exception as exc:
        click.echo(f"[ERR_DEID_011] DICOM 파싱 실패 / invalid DICOM: {exc}", err=True)
        sys.exit(1)

    cfg = _load_or_exit(ctx.obj["config_path"])

    from radivault_gateway.deid import DeidEngine
    from radivault_gateway.state import StateDB

    with tempfile.TemporaryDirectory(prefix="radivault_deidtest_") as tmpdir:
        tmp = Path(tmpdir)
        src_dir = tmp / "in"
        src_dir.mkdir()
        shutil.copy(input_path, src_dir / input_path.name)
        db = StateDB(tmp / "state.sqlite3")
        db.set_agent_identity(
            gateway_id=cfg.agent.gateway_id,
            hospital_id=cfg.agent.hospital_id,
            org_root_oid=cfg.agent.org_root_oid,
            salt_version=cfg.deid.salt_version,
        )
        engine = DeidEngine(
            salt=cfg.deid.salt,
            salt_version=cfg.deid.salt_version,
            org_root_oid=cfg.agent.org_root_oid,
            state_db=db,
            retain=cfg.deid.retain_options,
            burnin_quarantine_modalities=cfg.deid.burnin_quarantine_modalities,
            ruleset_version=cfg.deid.ruleset_version,
            version_string=__version__,
        )
        out_dir = tmp / "out"
        try:
            result = engine.deidentify_study(src_dir, out_dir)
        except Exception as exc:
            click.echo(f"[ERR_DEID_020] 익명화 실패 / deid failed: {exc}", err=True)
            sys.exit(1)
        reverify = engine.reverify(out_dir)
        ds_after = pydicom.dcmread(result.output_paths[0], force=False)

        click.echo(f"Input:   {input_path}")
        click.echo(f"Ruleset: {cfg.deid.ruleset_version}")
        click.echo("")
        if show_diff:
            _print_diff(ds_orig, ds_after)
        click.echo(
            f"Reverify: {'PASS' if reverify.ok else 'FAIL'}  ({len(reverify.offending)} offending)"
        )
        if not reverify.ok:
            for group, element, reason in reverify.offending:
                click.echo(f"  ({group:04X},{element:04X}) {reason}", err=True)
            click.echo("This file would be BLOCKED from upload in production.", err=True)
            click.echo("이 파일은 운영 환경에서 업로드가 차단됩니다.", err=True)
            click.echo(
                "See: https://docs.radivault.io/gateway-agent/errors/ERR_DEID_020",
                err=True,
            )
            sys.exit(2)

        if output_path is not None:
            shutil.copy(result.output_paths[0], output_path)
            click.echo(f"Wrote de-identified file to {output_path}")
    sys.exit(0)


def _print_diff(ds_orig: object, ds_after: object) -> None:
    tags_of_interest = [
        (0x0010, 0x0010, "PatientName"),
        (0x0010, 0x0020, "PatientID"),
        (0x0010, 0x0030, "PatientBirthDate"),
        (0x0008, 0x0020, "StudyDate"),
        (0x0020, 0x000D, "StudyInstanceUID"),
        (0x0008, 0x0080, "InstitutionName"),
        (0x0008, 0x0090, "ReferringPhysicianName"),
    ]
    click.echo(f"{'Tag':<12}{'Name':<26}{'Before':<20}{'After'}")
    for g, e, name in tags_of_interest:
        before = str(ds_orig.get(name, "<absent>"))
        after = str(ds_after.get(name, "<removed>"))
        click.echo(f"({g:04X},{e:04X}) {name:<26}{before[:18]:<20}{after[:30]}")


# ---- sync-once ----


@cli.command("sync-once", help="Run one synchronisation cycle and exit (1회성 동기화)")
@click.option("--since", type=click.DateTime(formats=["%Y-%m-%d"]), default=None)
@click.option("--until", type=click.DateTime(formats=["%Y-%m-%d"]), default=None)
@click.option("--dry-run", is_flag=True, help="Fetch + de-id but do NOT upload")
@click.option("--limit", type=int, default=None, help="Cap at N studies for this run")
@click.pass_context
def sync_once(
    ctx: click.Context,
    since: datetime | None,
    until: datetime | None,
    dry_run: bool,
    limit: int | None,
) -> None:
    cfg = _load_or_exit(ctx.obj["config_path"])
    configure_logging(
        level=ctx.obj.get("log_level") or cfg.logging.level,
        json_output=cfg.logging.json_output,
    )
    pipeline = _build_pipeline(cfg)
    summary = pipeline.run_once(
        since=since.date() if since else None,
        until=until.date() if until else None,
        dry_run=dry_run,
        limit=limit,
    )
    for i, outcome in enumerate(summary.outcomes, 1):
        pseudo = outcome.pseudo_study_uid or "?"
        click.echo(
            f"[{i}/{summary.total}] {pseudo}  fetch {outcome.fetch_ms}ms  "
            f"deid {outcome.deid_ms}ms  upload {outcome.upload_ms}ms  {outcome.state.value.upper()}"
        )
    click.echo(
        f"Summary  uploaded={summary.uploaded}  quarantined={summary.quarantined}  "
        f"failed={summary.failed}"
    )
    if summary.failed:
        sys.exit(1)
    sys.exit(0)


# ---- start (daemon) ----


@cli.command(help="Run as a foreground daemon (주기 동기화 데몬 실행)")
@click.option("--oneshot", is_flag=True, help="Exit after one full sync cycle")
@click.option("--poll-interval", type=int, default=None, help="Override poll interval seconds")
@click.pass_context
def start(ctx: click.Context, oneshot: bool, poll_interval: int | None) -> None:
    cfg = _load_or_exit(ctx.obj["config_path"])
    configure_logging(
        level=ctx.obj.get("log_level") or cfg.logging.level,
        json_output=cfg.logging.json_output,
    )
    interval = poll_interval or cfg.pacs.poll_interval_seconds
    anchor_interval = cfg.audit.anchor_interval_seconds
    pipeline = _build_pipeline(cfg)
    # Reuse pipeline's upload client + audit logger for anchor scheduling so
    # head_hash always reflects the most recent chain state.
    audit_logger = pipeline._audit
    upload_client = pipeline._upload
    click.echo(
        f"[radivault-gateway] starting, poll_interval={interval}s "
        f"anchor_interval={anchor_interval}s"
    )
    import signal
    import time

    stopping = {"flag": False}

    def _stop(*_args: object) -> None:
        stopping["flag"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    # Anchor once immediately after the first tick so operators see central
    # connectivity at startup; subsequent anchors follow anchor_interval cadence.
    last_anchor_at = time.monotonic() - anchor_interval

    def _maybe_anchor() -> None:
        """FR-25 / AC-19: post hourly audit anchor to central.

        Failure to anchor must not crash the daemon; we log WARN and let the
        next tick retry with a merged seq range.
        """
        head_seq = audit_logger.head_seq
        head_hash = audit_logger.head_hash
        if head_seq < 0:
            # No events yet — nothing to anchor.
            return
        seq_range = (0, head_seq)
        try:
            resp = upload_client.post_audit_anchor(
                gateway_id=cfg.agent.gateway_id,
                seq_range=seq_range,
                head_hash=head_hash,
            )
        except Exception as exc:
            log_record = getattr(exc, "status_code", None)
            click.echo(
                f"[radivault-gateway] WARN anchor failed status={log_record} error={exc}",
                err=True,
            )
            audit_logger.append(
                "audit.anchor.failed",
                meta={"error": str(exc), "status_code": log_record},
            )
            return
        anchor_id = resp.get("anchor_id") if isinstance(resp, dict) else None
        click.echo(
            f"[radivault-gateway] INFO anchor ok seq_range={seq_range} "
            f"head_hash={head_hash[:23]}... anchor_id={anchor_id}"
        )
        audit_logger.append(
            "audit.anchor.uploaded",
            meta={
                "seq_range": [seq_range[0], seq_range[1]],
                "head_hash": head_hash,
                "anchor_id": anchor_id,
            },
        )

    while not stopping["flag"]:
        summary = pipeline.run_once()
        click.echo(
            f"tick uploaded={summary.uploaded} quarantined={summary.quarantined} "
            f"failed={summary.failed}"
        )
        if time.monotonic() - last_anchor_at >= anchor_interval:
            _maybe_anchor()
            last_anchor_at = time.monotonic()
        if oneshot:
            break
        # Sleep in small slices so signals land within ~1s.
        slept = 0
        while slept < interval and not stopping["flag"]:
            time.sleep(1)
            slept += 1
            if time.monotonic() - last_anchor_at >= anchor_interval:
                _maybe_anchor()
                last_anchor_at = time.monotonic()
    click.echo("[radivault-gateway] stopped")


# ---- status ----


@cli.command(help="Print agent status summary (상태 요약 출력)")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON")
@click.pass_context
def status(ctx: click.Context, json_output: bool) -> None:
    cfg = _load_or_exit(ctx.obj["config_path"])
    from radivault_gateway.audit import verify_chain
    from radivault_gateway.state import StateDB

    try:
        db = StateDB(cfg.state.db_path)
    except Exception as exc:
        click.echo(f"[ERR_DB_001] 상태 DB 접근 실패 / cannot access state DB: {exc}", err=True)
        sys.exit(1)
    counts = db.counts_by_state()
    audit_path = Path(cfg.audit.path)
    audit_exists = audit_path.exists()
    chain_ok = False
    head_seq = None
    head_hash = None
    if audit_exists:
        r = verify_chain(audit_path)
        chain_ok = r.ok
        head_seq = r.head_seq
        head_hash = r.head_hash

    data = {
        "agent": {
            "version": __version__,
            "gateway_id": cfg.agent.gateway_id,
            "hospital_id": cfg.agent.hospital_id,
            "ruleset_version": cfg.deid.ruleset_version,
        },
        "pipeline_24h": counts,
        "staging": {
            "path": str(cfg.staging.root),
            "threshold_pct": cfg.staging.max_disk_pct,
            "retention_hours": cfg.staging.retention_hours,
        },
        "audit": {
            "path": str(audit_path),
            "exists": audit_exists,
            "seq_head": head_seq,
            "head_hash": head_hash,
            "chain_status": "ok" if chain_ok else "fail" if audit_exists else "absent",
        },
    }
    if json_output:
        click.echo(json.dumps(data, indent=2))
        sys.exit(0)
    click.echo("RadiVault Gateway Agent")
    click.echo(f"  gateway_id: {cfg.agent.gateway_id}")
    click.echo(f"  hospital_id: {cfg.agent.hospital_id}")
    click.echo(f"  version: {__version__} (ruleset {cfg.deid.ruleset_version})")
    click.echo("Pipeline counts")
    for state_name, n in sorted(counts.items()):
        click.echo(f"  {state_name:20s}{n}")
    click.echo(
        f"Audit log  chain: {'OK' if chain_ok else 'FAIL' if audit_exists else 'ABSENT'}  head_seq={head_seq}"
    )
    sys.exit(0)


def _build_pipeline(cfg: GatewayConfig):
    from radivault_gateway.deid import DeidEngine
    from radivault_gateway.orchestrator import Pipeline
    from radivault_gateway.pacs import DicomWebPacsClient
    from radivault_gateway.staging import StagingManager
    from radivault_gateway.state import StateDB
    from radivault_gateway.upload import UploadClient

    db = StateDB(cfg.state.db_path)
    db.set_agent_identity(
        gateway_id=cfg.agent.gateway_id,
        hospital_id=cfg.agent.hospital_id,
        org_root_oid=cfg.agent.org_root_oid,
        salt_version=cfg.deid.salt_version,
    )
    audit_logger = AuditLogger(cfg.audit.path, gateway_id=cfg.agent.gateway_id)
    staging = StagingManager(
        cfg.staging.root,
        retention_hours=cfg.staging.retention_hours,
        max_disk_pct=cfg.staging.max_disk_pct,
    )
    deid = DeidEngine(
        salt=cfg.deid.salt,
        salt_version=cfg.deid.salt_version,
        org_root_oid=cfg.agent.org_root_oid,
        state_db=db,
        retain=cfg.deid.retain_options,
        burnin_quarantine_modalities=cfg.deid.burnin_quarantine_modalities,
        ruleset_version=cfg.deid.ruleset_version,
        version_string=__version__,
    )
    pacs = DicomWebPacsClient(
        cfg.pacs.base_url,
        auth_type=cfg.pacs.auth.type,
        token=cfg.pacs.auth.token,
        username=cfg.pacs.auth.username,
        password=cfg.pacs.auth.password,
        ca_bundle=cfg.pacs.ca_bundle,
    )
    upload = UploadClient(
        cfg.central.base_url,
        upload_token=cfg.central.upload_token,
        timeout_seconds=cfg.central.upload_timeout_seconds,
        max_retries=cfg.central.max_upload_retries,
    )
    return Pipeline(
        cfg,
        state_db=db,
        audit_logger=audit_logger,
        staging=staging,
        deid=deid,
        pacs=pacs,
        upload=upload,
    )


if __name__ == "__main__":  # pragma: no cover
    cli()
