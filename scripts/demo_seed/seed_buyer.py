"""Seed a demo buyer + API key for the buyer-portal-demo.

Dev-spec buyer-portal-demo §8 step 5 (``seed_buyer.py``).

What it does
------------
1. Calls ``search-admin buyer create`` (idempotent — re-issues ERR_ADMIN_BUYER_DUPLICATE
   which we treat as success).
2. Calls ``search-admin key issue --json`` to mint one ``rv_live_*`` API key.
3. Prints the plaintext to stdout **once** and writes a gitignored copy to
   ``scripts/demo_seed/.buyer_key.local.txt`` for the demo operator.

This script is scoped to the **buyer** side. The portal BFF secret file
(``web/portal/.env.local``) is owned by ``scripts/demo_setup/generate_demo_secrets.sh``
and we deliberately do not touch it here.

Why ``docker exec`` by default
------------------------------
The ``search-admin`` entrypoint lives inside ``radivault-search-1``, which
already has the correct Postgres DSN wired through ``docker-compose.search.yml``.
Running the CLI from outside the container would require re-deriving the DSN,
so we shell into the container instead. ``--no-docker`` allows running the
in-process CLI when the caller has the DB env set up (useful for tests).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("demo_seed.buyer")

DEFAULT_BUYER_ID = "buy_demo001"
DEFAULT_COMPANY = "Demo Buyer Global AI"
DEFAULT_EMAIL = "demo-buyer@example.com"
DEFAULT_TIER = "paid"
DEFAULT_CONTAINER = "radivault-search-1"
DEFAULT_OUT_PATH = Path(__file__).parent / ".buyer_key.local.txt"


# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    log.debug("exec %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
    )


def _search_admin_cmd(base: list[str], subargs: list[str]) -> list[str]:
    """Stitch together the full command vector (docker exec or local)."""
    return [*list(base), "search-admin", *subargs]


# ---------------------------------------------------------------------------
# High-level ops
# ---------------------------------------------------------------------------


def buyer_exists(base_cmd: list[str], buyer_id: str) -> bool:
    result = _run(
        _search_admin_cmd(base_cmd, ["buyer", "show", "--buyer-id", buyer_id, "--json"])
    )
    return result.returncode == 0


def create_buyer(
    base_cmd: list[str],
    *,
    buyer_id: str,
    company: str,
    email: str,
    tier: str,
) -> None:
    """Create a buyer row. Idempotent — duplicate is treated as success."""
    result = _run(
        _search_admin_cmd(
            base_cmd,
            [
                "buyer",
                "create",
                "--buyer-id",
                buyer_id,
                "--company",
                company,
                "--contact-email",
                email,
                "--tier",
                tier,
                "--json",
            ],
        )
    )
    if result.returncode == 0:
        log.info("buyer_created buyer_id=%s", buyer_id)
        return
    # Existing row shows up as ERR_ADMIN_BUYER_DUPLICATE on stderr.
    combined = (result.stdout or "") + (result.stderr or "")
    if "ERR_ADMIN_BUYER_DUPLICATE" in combined:
        log.info("buyer_exists buyer_id=%s (idempotent skip)", buyer_id)
        return
    sys.stderr.write(
        "[ERR_SEED_BUYER_CREATE_FAILED] buyer create failed / 구매자 생성 실패\n"
        f"  stderr: {result.stderr.strip() or '(empty)'}\n"
        f"  stdout: {result.stdout.strip() or '(empty)'}\n"
    )
    raise SystemExit(4)


def issue_key(
    base_cmd: list[str],
    *,
    buyer_id: str,
    tier: str,
    expires_days: int,
    note: str | None = None,
) -> dict:
    """Issue a fresh API key. Returns the JSON dict with 'plaintext'."""
    argv = [
        "key",
        "issue",
        "--buyer-id",
        buyer_id,
        "--tier",
        tier,
        "--expires-days",
        str(expires_days),
        "--json",
    ]
    if note:
        # search-admin key issue has no --note (see cli.py §key_issue).
        # Fold the note into scope_json for discoverability in the DB.
        argv.extend(["--scope-json", json.dumps({"demo_note": note})])
    result = _run(_search_admin_cmd(base_cmd, argv))
    if result.returncode != 0:
        sys.stderr.write(
            "[ERR_SEED_KEY_ISSUE_FAILED] key issue failed / API 키 발급 실패\n"
            f"  stderr: {result.stderr.strip() or '(empty)'}\n"
        )
        raise SystemExit(5)
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except Exception as exc:
        sys.stderr.write(
            "[ERR_SEED_KEY_PARSE_FAILED] could not parse search-admin output\n"
            f"  exc: {exc}\n  stdout: {result.stdout}\n"
        )
        raise SystemExit(6) from None
    if "plaintext" not in payload:
        sys.stderr.write(
            "[ERR_SEED_KEY_NO_PLAINTEXT] search-admin output missing plaintext field\n"
        )
        raise SystemExit(7)
    return payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed a demo buyer + API key (dev-spec §8 step 5)"
    )
    parser.add_argument("--buyer-id", default=DEFAULT_BUYER_ID)
    parser.add_argument("--company", default=DEFAULT_COMPANY)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--tier", default=DEFAULT_TIER, choices=["preview", "paid"])
    parser.add_argument("--expires-days", type=int, default=180)
    parser.add_argument("--note", default="buyer-portal-demo seed")
    parser.add_argument(
        "--container",
        default=DEFAULT_CONTAINER,
        help="docker exec target (default radivault-search-1)",
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Run search-admin locally instead of via docker exec (needs DB env).",
    )
    parser.add_argument(
        "--out-path",
        type=Path,
        default=DEFAULT_OUT_PATH,
        help="Write plaintext key here (gitignored).",
    )
    parser.add_argument(
        "--skip-if-key-file-exists",
        action="store_true",
        help="If --out-path already exists, skip key issuance (idempotent).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.skip_if_key_file_exists and args.out_path.exists():
        log.info("skip buyer seed — key file already present at %s", args.out_path)
        return 0

    # Resolve base command (docker exec vs local).
    if args.no_docker:
        if shutil.which("search-admin") is None:
            sys.stderr.write(
                "[ERR_SEED_CLI_MISSING] search-admin not on PATH. "
                "Install .[search] or drop --no-docker.\n"
            )
            return 8
        base_cmd: list[str] = []
    else:
        if shutil.which("docker") is None:
            sys.stderr.write(
                "[ERR_SEED_DOCKER_MISSING] docker CLI not found. "
                "Install Docker or pass --no-docker.\n"
            )
            return 9
        base_cmd = ["docker", "exec", args.container]

    create_buyer(
        base_cmd,
        buyer_id=args.buyer_id,
        company=args.company,
        email=args.email,
        tier=args.tier,
    )

    payload = issue_key(
        base_cmd,
        buyer_id=args.buyer_id,
        tier=args.tier,
        expires_days=args.expires_days,
        note=args.note,
    )

    # Persist plaintext for the demo operator. Use 0600 so another local
    # user can't scoop it off disk.
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(payload["plaintext"] + "\n", encoding="utf-8")
    os.chmod(args.out_path, 0o600)

    # Stdout banner (matches search-admin box format but shorter).
    sys.stdout.write(
        "\n".join(
            [
                "=" * 72,
                " RadiVault demo buyer key issued",
                "=" * 72,
                f" buyer_id    : {payload['buyer_id']}",
                f" kid         : {payload['kid']}",
                f" tier        : {payload.get('tier', args.tier)}",
                f" expires_at  : {payload.get('expires_at') or 'never'}",
                f" written_to  : {args.out_path}",
                "-" * 72,
                " Plaintext key (shown ONCE, copy now):",
                "",
                f"   {payload['plaintext']}",
                "",
                "=" * 72,
                "",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
