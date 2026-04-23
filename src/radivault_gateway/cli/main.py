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
from radivault_gateway.cli.pixel_selftest import pixel_selftest
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
        "ruleset_full": f"{RULESET_VERSION} + pixel v0.1",
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
    }
    try:
        import pydicom  # type: ignore[import-not-found]

        info["pydicom"] = pydicom.__version__
    except Exception:
        info["pydicom"] = "unknown"

    # Pixel engine versions (design-spec §2.7). Four lines; ``(absent)`` when
    # the component is not installed.
    info["pytesseract"] = _module_version("pytesseract")
    info["tesseract"] = _binary_version("tesseract", "--version")
    info["pydeface"] = _module_version("pydeface")
    info["fsl_flirt"] = _binary_version("flirt", "-version")

    if json_output:
        click.echo(json.dumps(info, indent=0).replace("\n", ""))
        return
    click.echo(f"gateway-agent  {info['agent']}")
    click.echo(f"ruleset        {info['ruleset_full']}")
    click.echo(f"python         {info['python']}")
    click.echo(f"pydicom        {info['pydicom']}")
    click.echo(f"platform       {info['platform']}")
    click.echo(f"pytesseract    {info['pytesseract']}")
    click.echo(f"tesseract      {info['tesseract']}")
    click.echo(f"pydeface       {info['pydeface']}")
    click.echo(f"FSL flirt      {info['fsl_flirt']}")


def _module_version(name: str) -> str:
    try:
        mod = __import__(name)
        return str(getattr(mod, "__version__", "unknown"))
    except ImportError:
        return "(absent)"


def _binary_version(binary: str, flag: str) -> str:
    path = shutil.which(binary)
    if path is None:
        return "(absent)"
    try:
        import subprocess

        out = subprocess.run([binary, flag], capture_output=True, text=True, timeout=5)
        head = (
            (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else ""
        )
        return head or "present"
    except Exception:
        return "present"


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
@click.option("--pixel", "pixel", is_flag=True, help="Also run pixel stage (OCR + defacing)")
@click.option(
    "--ocr-only", "ocr_only", is_flag=True, help="Skip defacing even if modality/body matches"
)
@click.option(
    "--deface-only", "deface_only", is_flag=True, help="Skip OCR even if BurnedInAnnotation=YES"
)
@click.option("--both", "both", is_flag=True, help="OCR + defacing (alias for --pixel)")
@click.option(
    "--show-boxes", "show_boxes", is_flag=True, help="Print OCR bbox table (hash + coord %)"
)
@click.option(
    "--show-voxel-stats",
    "show_voxel_stats",
    is_flag=True,
    help="Print defacing removed_voxel_ratio",
)
@click.pass_context
def de_id_test(
    ctx: click.Context,
    input_path: Path,
    output_path: Path | None,
    show_diff: bool,
    pixel: bool,
    ocr_only: bool,
    deface_only: bool,
    both: bool,
    show_boxes: bool,
    show_voxel_stats: bool,
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

        # Pixel stage (v0.2). Guard: flag relationships per design-spec §2.3.1
        pixel_any = pixel or both or ocr_only or deface_only or show_boxes or show_voxel_stats
        if pixel_any:
            if ocr_only and deface_only:
                click.echo(
                    "[ERR_CLI_010] --ocr-only and --deface-only are mutually exclusive",
                    err=True,
                )
                sys.exit(1)
            if (ocr_only or deface_only) and not (pixel or both):
                click.echo(
                    "[ERR_CLI_011] --ocr-only/--deface-only require --pixel",
                    err=True,
                )
                sys.exit(1)
            _run_pixel_de_id_test(
                cfg=cfg,
                staged_dir=out_dir,
                ocr_only=ocr_only,
                deface_only=deface_only,
                show_boxes=show_boxes,
                show_voxel_stats=show_voxel_stats,
            )
    sys.exit(0)


def _run_pixel_de_id_test(
    *,
    cfg: GatewayConfig,
    staged_dir: Path,
    ocr_only: bool,
    deface_only: bool,
    show_boxes: bool,
    show_voxel_stats: bool,
) -> None:
    """Mini wrapper: run PixelDeidEngine against a temp staged dir.

    Exits 4 when the configured engine is not available, 3 when the study
    would be quarantined.
    """
    from radivault_gateway.deid.pixel import (
        PixelDeidEngineError,
        PixelQuarantineRequired,
        build_pixel_deid_engine,
        format_cli_error,
    )

    test_cfg = cfg.deid.pixel.model_copy(deep=True)
    test_cfg.enabled = True
    if ocr_only:
        test_cfg.defacing.enabled = False
    if deface_only:
        test_cfg.ocr.enabled = False
    try:
        engine = build_pixel_deid_engine(test_cfg)
    except PixelDeidEngineError as exc:
        click.echo(format_cli_error(exc.code, detail=exc.message), err=True)
        sys.exit(4)
    if engine is None:
        click.echo("Pixel stage skipped (disabled).")
        return
    click.echo("")
    click.echo("Pixel Stage (v0.2)")
    triage = engine.triage(staged_dir)
    click.echo(f"  triage        {triage.decision.value}  (reason: {triage.reason})")
    try:
        result = engine.process_study(
            staged_dir,
            pseudo_study_uid="cli-test",
            study_description=None,
            modality_set=set(),
            body_part=None,
        )
    except PixelQuarantineRequired as exc:
        click.echo(format_cli_error(exc.code, reason=exc.reason), err=True)
        click.echo("운영 환경에서는 이 스터디가 격리됩니다(state=pixel_failed).", err=True)
        sys.exit(3)
    except PixelDeidEngineError as exc:
        click.echo(format_cli_error(exc.code, detail=exc.message), err=True)
        sys.exit(4)
    if result.ocr_applied:
        click.echo(f"  engine        {result.library_ocr} (decision={result.decision})")
        click.echo(
            f"  OCR           frames={result.n_frames_ocr}  "
            f"boxes_applied={result.n_boxes_redacted}  "
            f"avg_conf={result.avg_confidence:.2f}"
        )
    if show_boxes:
        # Boxes are held only transiently inside the engine — redaction already
        # stripped the text. We surface aggregate stats here; per-box hashes
        # are logged to audit with hash-only payloads (FR-38).
        click.echo("  boxes         (stats-only; hashed text never printed — FR-38)")
    if result.defacing_applied:
        click.echo(
            f"  defacing      {result.library_deface}  "
            f"removed_voxel_ratio={result.removed_voxel_ratio:.3f}"
        )
    if show_voxel_stats:
        click.echo(
            f"  voxel_stats   removed={result.removed_voxel_ratio:.3f} "
            f"duration_ms={result.deface_duration_ms}"
        )
    click.echo("  Exit status   OK")


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
    # FR-36 / AC-18: pixel-stage crash recovery at startup.
    if cfg.deid.pixel.enabled:
        from radivault_gateway.orchestrator.recovery import (
            recover_orphaned_pixel_processing,
        )

        recovery = recover_orphaned_pixel_processing(
            pipeline._db,
            audit=audit_logger,
            staging=pipeline._staging,
        )
        if recovery.recovered:
            click.echo(
                f"[radivault-gateway] pixel recovery: rolled back "
                f"{recovery.recovered} orphaned pixel_processing study(ies)"
            )
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
    from radivault_gateway.staging import StagingManager
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

    # AC-12 / FR-16: surface staging entries older than retention_hours.
    # Threshold in seconds so callers (and the dev-spec anchor test fixture)
    # can override via staging.retention_hours.
    threshold_seconds = int(cfg.staging.retention_hours) * 3600
    stale_count = 0
    try:
        staging = StagingManager(
            cfg.staging.root,
            retention_hours=cfg.staging.retention_hours,
            max_disk_pct=cfg.staging.max_disk_pct,
        )
        stale_count = len(staging.stale_studies(threshold_seconds=threshold_seconds))
    except Exception as exc:
        click.echo(f"[WARN] staging stale-scan failed: {exc}", err=True)

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
            "stale_count": stale_count,
        },
        "audit": {
            "path": str(audit_path),
            "exists": audit_exists,
            "seq_head": head_seq,
            "head_hash": head_hash,
            "chain_status": "ok" if chain_ok else "fail" if audit_exists else "absent",
        },
    }
    if cfg.deid.pixel.enabled:
        data["pixel"] = _pixel_status(cfg, db)
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
    # Design-spec §6.2 ``Staging`` block: show retention + stale count.
    click.echo("Staging")
    click.echo(f"  path           {cfg.staging.root}")
    click.echo(
        f"  retention      {cfg.staging.retention_hours}h  threshold {cfg.staging.max_disk_pct}%"
    )
    click.echo(f"  Stale: {stale_count}")
    click.echo(
        f"Audit log  chain: {'OK' if chain_ok else 'FAIL' if audit_exists else 'ABSENT'}  "
        f"head_seq={head_seq}"
    )
    if cfg.deid.pixel.enabled:
        pixel_data = data.get("pixel", {})
        _render_pixel_status(pixel_data)
    sys.exit(0)


def _pixel_status(cfg: GatewayConfig, db) -> dict:
    """Build the status JSON ``pixel`` block (design-spec §2.5.3)."""
    try:
        pixel_events = db.list_pixel_audit_events(limit=500)
    except Exception:
        pixel_events = []
    triage_counts = {"ocr_required": 0, "ocr_conditional": 0, "skip": 0}
    ocr_stats = {"studies": 0, "avg_confidence": 0.0, "redacted_boxes": 0}
    deface_stats = {"studies": 0, "avg_removed_voxel_ratio": 0.0, "min_removed_voxel_ratio": 0.0}
    quarantine_stats = {
        "residual_text": 0,
        "residual_face_voxels": 0,
        "medical_exclusion": 0,
        "low_confidence": 0,
    }
    confs: list[float] = []
    ratios: list[float] = []
    for ev in pixel_events:
        op = ev.get("op")
        outcome = ev.get("outcome")
        reason = ev.get("reason") or ""
        if op == "triage":
            key = (reason or "").lower()
            if key.startswith("ocr_required"):
                triage_counts["ocr_required"] += 1
            elif key.startswith("ocr_conditional"):
                triage_counts["ocr_conditional"] += 1
            else:
                triage_counts["skip"] += 1
        elif op == "ocr" and outcome == "success":
            ocr_stats["studies"] += 1
            ocr_stats["redacted_boxes"] += int(ev.get("box_count") or 0)
            if ev.get("avg_confidence") is not None:
                confs.append(float(ev["avg_confidence"]))
        elif op == "deface" and outcome == "success":
            deface_stats["studies"] += 1
            if ev.get("removed_voxel_ratio") is not None:
                ratios.append(float(ev["removed_voxel_ratio"]))
        elif outcome == "quarantine":
            reason_key = reason.upper()
            if "RESIDUAL_TEXT" in reason_key:
                quarantine_stats["residual_text"] += 1
            elif "RESIDUAL_FACE" in reason_key:
                quarantine_stats["residual_face_voxels"] += 1
            elif "MEDICAL_EXCLUSION" in reason_key:
                quarantine_stats["medical_exclusion"] += 1
            elif "LOW_CONFIDENCE" in reason_key:
                quarantine_stats["low_confidence"] += 1
    if confs:
        ocr_stats["avg_confidence"] = round(sum(confs) / len(confs), 3)
    if ratios:
        deface_stats["avg_removed_voxel_ratio"] = round(sum(ratios) / len(ratios), 3)
        deface_stats["min_removed_voxel_ratio"] = round(min(ratios), 3)
    from radivault_gateway.deid.pixel.deface_engine import (
        MridefacerEngine,
        PydefaceEngine,
    )
    from radivault_gateway.deid.pixel.ocr_engine import (
        PaddleOcrEngine,
        TesseractOcrEngine,
    )

    ocr_engine_name = cfg.deid.pixel.ocr.engine
    defacing_library = cfg.deid.pixel.defacing.library
    ocr_available = (
        TesseractOcrEngine.is_available()
        if ocr_engine_name == "tesseract"
        else PaddleOcrEngine.is_available()
    )
    defacing_available = (
        PydefaceEngine().is_available()
        if defacing_library == "pydeface"
        else MridefacerEngine().is_available()
    )
    return {
        "enabled": True,
        "engines": {
            "ocr": {
                "name": ocr_engine_name,
                "version": (
                    TesseractOcrEngine().version()
                    if ocr_engine_name == "tesseract" and ocr_available
                    else "(absent)"
                ),
                "status": "ok" if ocr_available else "fail",
            },
            "defacing": {
                "name": defacing_library,
                "version": (PydefaceEngine().version() if defacing_available else "(absent)"),
                "status": "ok" if defacing_available else "fail",
            },
        },
        "triage_24h": triage_counts,
        "ocr_24h": ocr_stats,
        "deface_24h": deface_stats,
        "quarantine_24h": quarantine_stats,
        "engine_errors_24h": {"ocr": 0, "deface": 0, "deface_fallback_succeeded": 0},
    }


def _render_pixel_status(pixel_data: dict) -> None:
    if not pixel_data:
        return
    click.echo("Pixel stage  [v0.2]")
    engines = pixel_data.get("engines", {})
    ocr_eng = engines.get("ocr", {})
    deface_eng = engines.get("defacing", {})
    click.echo(
        f"  engines     {ocr_eng.get('name')} {ocr_eng.get('version')}  "
        f"{deface_eng.get('name')} {deface_eng.get('version')}"
    )
    triage = pixel_data.get("triage_24h", {})
    click.echo(
        "  24h triage  "
        f"OCR_REQUIRED {triage.get('ocr_required', 0)}  "
        f"SKIP {triage.get('skip', 0)}  "
        f"CONDITIONAL {triage.get('ocr_conditional', 0)}"
    )
    ocr_stats = pixel_data.get("ocr_24h", {})
    click.echo(
        "  24h OCR     "
        f"studies {ocr_stats.get('studies', 0)}  "
        f"avg_conf {ocr_stats.get('avg_confidence', 0.0)}  "
        f"redact_boxes {ocr_stats.get('redacted_boxes', 0)}"
    )
    deface_stats = pixel_data.get("deface_24h", {})
    click.echo(
        "  24h deface  "
        f"studies {deface_stats.get('studies', 0)}  "
        f"avg_removed_ratio {deface_stats.get('avg_removed_voxel_ratio', 0.0)}"
    )
    quarantine_stats = pixel_data.get("quarantine_24h", {})
    click.echo(
        "  quarantine  "
        f"residual_text {quarantine_stats.get('residual_text', 0)}  "
        f"residual_face {quarantine_stats.get('residual_face_voxels', 0)}  "
        f"medical_excl {quarantine_stats.get('medical_exclusion', 0)}"
    )


def _build_pipeline(cfg: GatewayConfig):
    from radivault_gateway.deid import DeidEngine
    from radivault_gateway.deid.pixel import build_pixel_deid_engine
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
        pixel_enabled=cfg.deid.pixel.enabled,
        pixel_ocr_modalities=cfg.deid.pixel.ocr.modality_allowlist,
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
        allow_insecure=cfg.central.allow_insecure,
    )
    try:
        pixel_engine = build_pixel_deid_engine(cfg.deid.pixel)
    except Exception as exc:
        from radivault_gateway.deid.pixel import (
            PixelDeidEngineError,
            format_cli_error,
        )

        if isinstance(exc, PixelDeidEngineError) and exc.code in {
            "ERR_CFG_PIXEL_ENGINE_MISSING",
            "ERR_PIXEL_DEFACE_LIBRARY_MISSING",
        }:
            click.echo(format_cli_error(exc.code, error=exc.message), err=True)
            sys.exit(64)
        raise
    return Pipeline(
        cfg,
        state_db=db,
        audit_logger=audit_logger,
        staging=staging,
        deid=deid,
        pacs=pacs,
        upload=upload,
        pixel=pixel_engine,
    )


# v0.2 de-id-pixel: register pixel-selftest subcommand. Always visible, even on
# the default (non-pixel) image — exit codes differ per available components.
cli.add_command(pixel_selftest)


@cli.group("metrics", help="Pixel-stage observability metrics (픽셀 단계 메트릭)")
def metrics_group() -> None:
    """Metrics commands (design-spec §4.3)."""


@metrics_group.command("dump", help="Dump Prometheus-format pixel metrics snapshot")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["prom", "text", "json"]),
    default="prom",
    show_default=True,
    help="Output format: prom=Prometheus exposition, text=readable, json=structured",
)
def metrics_dump(output_format: str) -> None:
    """Print the in-process pixel metrics registry (AC-D-12).

    The Gateway has no ``/metrics`` HTTP server in v0.2. This command
    materialises a fresh ``CollectorRegistry`` of the 10 pixel metrics
    (design-spec §4.3) and prints the exposition. Useful for smoke
    validation; external scraping is out-of-scope for the v0.2 MVP
    (see dev-spec §NFR "관측성" note).
    """
    import json as _json

    from radivault_gateway.deid.pixel import (
        build_pixel_metrics,
        dump_dict,
        dump_text,
    )

    metrics = build_pixel_metrics()
    if output_format == "prom":
        click.echo(dump_text(metrics), nl=False)
    elif output_format == "text":
        data = dump_dict(metrics)
        for name, family in data.items():
            click.echo(f"# {name} ({family['type']}) — {family['help']}")
            for sample in family["samples"]:
                labels = ",".join(f"{k}={v!r}" for k, v in sample["labels"].items())
                click.echo(f"  {sample['name']}{{{labels}}} {sample['value']}")
    else:
        click.echo(_json.dumps(dump_dict(metrics), indent=2, default=str))


# ---- transfer (order-fulfilment consumer subsystem, §14 G-1) ------------
# Imported + registered here so the top-level ``radivault-gateway --help``
# surfaces the ``transfer`` group. Disabled by default via
# ``transfer.enabled=false`` in gateway.yml.
from radivault_gateway.transfer.cli import transfer_group as _transfer_group  # noqa: E402

cli.add_command(_transfer_group)


if __name__ == "__main__":  # pragma: no cover
    cli()
