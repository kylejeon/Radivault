"""Click CLI subcommands for ``radivault-gateway transfer ...``.

Registered via the main gateway CLI in :mod:`radivault_gateway.cli.main`.

jpg-preview-defacing CAVEAT-1 closeout (round 2):
``transfer start`` and ``transfer test`` now wrap the upstream runner
with ``with_preview_pipeline`` whenever ``PREVIEW_PIPELINE_ENABLED=true``.
The wrapper is supplied with the production :class:`PreviewClients`
adapters (MinIO + Postgres) constructed from environment variables so
the CLI exercises the new pipeline end-to-end.

When the flag is OFF (default), the CLI behaves bit-for-bit identically
to round 1: the runner is plain ``mock_runner`` (or a real upload runner
in production), no preview clients are constructed, and no MinIO /
Postgres calls happen.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable

import click

from radivault_gateway.preview_clients import maybe_preview_clients
from radivault_gateway.preview_pipeline import is_pipeline_enabled
from radivault_gateway.preview_provider import gateway_series_inputs_provider
from radivault_gateway.transfer.claim import Claim, ClaimClient
from radivault_gateway.transfer.config import TransferConfig
from radivault_gateway.transfer.consumer import JobResult, TransferConsumer
from radivault_gateway.transfer.progress import ProgressReporter
from radivault_gateway.transfer.runner import build_runner, with_preview_pipeline

log = logging.getLogger("radivault_gateway.transfer.cli")


def _config_from_click(ctx: click.Context) -> TransferConfig:
    """Pull transfer.* from the loaded gateway config.

    Gateway config loads via YAML into a dataclass tree; the transfer
    subtree is additive (§14 G-1) and defaults to ``enabled=false``.
    """
    data = ctx.obj.get("transfer_config") or {}
    return TransferConfig(**{k: v for k, v in data.items() if v is not None})


@click.group(
    name="transfer",
    help="Order-fulfilment transfer-job consumer (opt-in; disabled by default)",
)
@click.pass_context
def transfer_group(ctx: click.Context) -> None:
    ctx.ensure_object(dict)


@transfer_group.command("start", help="Run the transfer consumer daemon loop")
@click.option(
    "--central-url",
    default=None,
    help="Override fulfillment endpoint (else uses transfer.central_url)",
)
@click.option(
    "--auth-token",
    default=None,
    help="Bearer token (else transfer.auth_token/central.upload_token)",
)
@click.pass_context
def transfer_start(ctx: click.Context, central_url: str | None, auth_token: str | None) -> None:
    cfg = _config_from_click(ctx)
    if central_url:
        cfg.central_url = central_url
    if auth_token:
        cfg.auth_token = auth_token
    if not cfg.enabled:
        click.echo(
            "transfer.enabled=false in config; set transfer.enabled=true to run",
            err=True,
        )
        sys.exit(64)
    if not cfg.auth_token:
        click.echo("ERR_CFG: transfer.auth_token missing", err=True)
        sys.exit(64)
    client = ClaimClient(central_url=cfg.central_url, auth_token=cfg.auth_token)
    enabled = is_pipeline_enabled()
    with maybe_preview_clients(enabled) as clients:
        runner = _build_wrapped_runner(clients=clients)
        consumer = TransferConsumer(config=cfg, client=client, runner=runner)
        try:
            consumer.run_forever()
        finally:
            client.close()


@transfer_group.command("status", help="Show transfer consumer in-flight snapshot")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def transfer_status(ctx: click.Context, as_json: bool) -> None:
    cfg = _config_from_click(ctx)
    payload = {
        "enabled": cfg.enabled,
        "central_url": cfg.central_url,
        "poll_wait_seconds": cfg.poll_wait_seconds,
        "max_concurrent_jobs": cfg.max_concurrent_jobs,
    }
    if as_json:
        click.echo(json.dumps(payload, indent=2))
    else:
        for k, v in payload.items():
            click.echo(f"{k}: {v}")


@transfer_group.command(
    "test",
    help="Dry-run one claim → mock fetch → complete round trip (no daemon loop)",
)
@click.option("--central-url", default=None)
@click.option("--auth-token", default=None)
@click.pass_context
def transfer_test(ctx: click.Context, central_url: str | None, auth_token: str | None) -> None:
    cfg = _config_from_click(ctx)
    if central_url:
        cfg.central_url = central_url
    if auth_token:
        cfg.auth_token = auth_token
    if not cfg.enabled:
        cfg.enabled = True  # explicit test override
    if not cfg.auth_token:
        click.echo("ERR_CFG: transfer.auth_token missing", err=True)
        sys.exit(64)
    client = ClaimClient(central_url=cfg.central_url, auth_token=cfg.auth_token)
    enabled = is_pipeline_enabled()
    with maybe_preview_clients(enabled) as clients:
        runner = _build_wrapped_runner(clients=clients)
        consumer = TransferConsumer(config=cfg, client=client, runner=runner)
        try:
            outcome = consumer.run_once()
            click.echo(json.dumps(outcome, indent=2))
        finally:
            client.close()


# ---------------------------------------------------------------------------
# Runner factory — exposed as a private helper so unit tests can poke
# the wrapping logic without spinning a Click context.
# ---------------------------------------------------------------------------


def _build_wrapped_runner(
    *, clients: object | None
) -> Callable[[Claim, ProgressReporter], JobResult]:
    """Return the consumer-facing runner.

    If ``clients`` is None (flag off OR construction failed), fall back
    to the bare upstream runner — preserving bit-for-bit legacy behaviour.

    If ``clients`` is a :class:`PreviewClients`, wrap the upstream
    runner with :func:`with_preview_pipeline`, supplying the production
    MinIO + Postgres adapters and the on-disk staging-aware
    :func:`gateway_series_inputs_provider`.
    """
    upstream = build_runner()
    if clients is None:
        return upstream
    # PreviewClients duck-typed; the import is light enough to do here.
    from radivault_gateway.preview_clients import PreviewClients  # noqa: PLC0415

    if not isinstance(clients, PreviewClients):  # pragma: no cover - defensive
        log.warning(
            "preview_clients_unexpected_type",
            extra={"event": "preview.cli.warn", "type": type(clients).__name__},
        )
        return upstream
    return with_preview_pipeline(
        upstream,
        minio_client=clients.minio,
        audit_writer=clients.audit,
        frame_writer=clients.frames,
        series_inputs_provider=gateway_series_inputs_provider,
    )
