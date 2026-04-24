"""Ensure the demo hospital row + optional admin token exist.

Dev-spec buyer-portal-demo §8 step 6 (``seed_hospital.py``).

Scope note
----------
Most of this ground is already covered by `docs/ops/install-guide.md §6`
("병원 생성 및 Bearer 토큰 발급") and `scripts/demo_setup/generate_demo_secrets.sh`.
That means this script is intentionally **thin**. Its jobs are:

1. Make ``ingest-admin init-hospital HOSP-001`` idempotent inside ``inject_all.sh``
   so a fresh operator can run the one-shot script without reading the install
   guide first.
2. Optionally issue an upstream bearer token (``--issue-token``) and print it
   to stdout. Writing to ``web/portal/.env.local`` remains the operator's job
   (we do NOT touch ``.env.local`` — see dev-spec "하지 말 것" #5).

If the hospital already exists and ``--issue-token`` is not passed, this is a
no-op that prints a short status line.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys

log = logging.getLogger("demo_seed.hospital")

DEFAULT_HOSPITAL_ID = "HOSP-001"
DEFAULT_HOSPITAL_NAME = "데모병원 (Demo Hospital)"
DEFAULT_CONTAINER = "radivault-central-1"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    log.debug("exec %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True)


def _ingest_admin(base: list[str], subargs: list[str]) -> list[str]:
    return [*list(base), "ingest-admin", *subargs]


def ensure_hospital(base_cmd: list[str], hospital_id: str, name: str) -> str:
    """Idempotent ``ingest-admin init-hospital``.

    Returns ``"enrolled"`` (new row), ``"exists"`` (already there), or raises.
    """
    result = _run(
        _ingest_admin(
            base_cmd,
            ["init-hospital", "--hospital-id", hospital_id, "--name", name],
        )
    )
    combined = (result.stdout or "") + (result.stderr or "")
    if result.returncode == 0 and "[OK] enrolled" in combined:
        return "enrolled"
    if "[EXISTS]" in combined or "already enrolled" in combined.lower():
        return "exists"
    if result.returncode == 0:
        # Unknown success line — don't fail, just log verbatim.
        log.warning("unexpected_init_hospital_output=%s", combined.strip())
        return "ok"
    sys.stderr.write(
        "[ERR_SEED_HOSPITAL_INIT_FAILED] init-hospital failed / 병원 생성 실패\n"
        f"  stderr: {result.stderr.strip() or '(empty)'}\n"
    )
    raise SystemExit(4)


def issue_admin_token(base_cmd: list[str], hospital_id: str, note: str) -> dict:
    result = _run(
        _ingest_admin(
            base_cmd,
            [
                "token",
                "issue",
                "--hospital-id",
                hospital_id,
                "--note",
                note,
                "--json",
            ],
        )
    )
    if result.returncode != 0:
        sys.stderr.write(
            "[ERR_SEED_TOKEN_ISSUE_FAILED] token issue failed / 토큰 발급 실패\n"
            f"  stderr: {result.stderr.strip() or '(empty)'}\n"
        )
        raise SystemExit(5)
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except Exception as exc:
        sys.stderr.write(
            "[ERR_SEED_TOKEN_PARSE_FAILED] could not parse ingest-admin output\n"
            f"  exc: {exc}\n  stdout: {result.stdout}\n"
        )
        raise SystemExit(6) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ensure demo hospital + (optional) bearer token (dev-spec §8 step 6)"
    )
    parser.add_argument("--hospital-id", default=DEFAULT_HOSPITAL_ID)
    parser.add_argument("--name", default=DEFAULT_HOSPITAL_NAME)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Run ingest-admin locally instead of via docker exec.",
    )
    parser.add_argument(
        "--issue-token",
        action="store_true",
        help=(
            "Also issue an upstream bearer token and print it. "
            "Operator must paste into web/portal/.env.local HOSPITAL_UPSTREAM_BEARER."
        ),
    )
    parser.add_argument(
        "--note",
        default="buyer-portal-demo seed",
        help="Note for the issued token.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.no_docker:
        if shutil.which("ingest-admin") is None:
            sys.stderr.write(
                "[ERR_SEED_CLI_MISSING] ingest-admin not on PATH. "
                "Install .[central] or drop --no-docker.\n"
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

    status = ensure_hospital(base_cmd, args.hospital_id, args.name)
    log.info("hospital_status id=%s status=%s", args.hospital_id, status)

    if not args.issue_token:
        sys.stdout.write(
            f"[OK] hospital {args.hospital_id} ready ({status}). "
            "Skipped token issuance (pass --issue-token to mint a new one).\n"
        )
        return 0

    payload = issue_admin_token(base_cmd, args.hospital_id, args.note)
    sys.stdout.write(
        "\n".join(
            [
                "=" * 72,
                f" RadiVault demo hospital token — {payload['hospital_id']}",
                "=" * 72,
                f" kid         : {payload['kid']}",
                f" expires_at  : {payload.get('expires_at') or 'never'}",
                f" note        : {payload.get('note') or '(none)'}",
                "-" * 72,
                " Plaintext bearer (shown ONCE, paste into .env.local):",
                "",
                f"   HOSPITAL_UPSTREAM_BEARER={payload['plaintext']}",
                "",
                "=" * 72,
                "",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
