"""Click CLI subcommands for ``radivault-gateway transfer ...``.

Registered via the main gateway CLI in :mod:`radivault_gateway.cli.main`.
"""

from __future__ import annotations

import json
import sys

import click

from radivault_gateway.transfer.claim import ClaimClient
from radivault_gateway.transfer.config import TransferConfig
from radivault_gateway.transfer.consumer import TransferConsumer
from radivault_gateway.transfer.runner import build_runner


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
    consumer = TransferConsumer(config=cfg, client=client, runner=build_runner())
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
    consumer = TransferConsumer(config=cfg, client=client, runner=build_runner())
    try:
        outcome = consumer.run_once()
        click.echo(json.dumps(outcome, indent=2))
    finally:
        client.close()
