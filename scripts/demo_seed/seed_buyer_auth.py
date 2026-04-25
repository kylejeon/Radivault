"""Seed a demo buyer email/password credential for the buyer-auth feature.

dev-spec-buyer-auth FR-AUTH-12.

What this script does
---------------------
1. Calls the portal's running ``/api/auth/signup`` endpoint with the
   demo credentials below — using the public HTTP surface so the same
   in-memory store the dev server uses receives the row.
2. Writes the plaintext API key returned by signup (rv_live_…, shown
   ONCE) to ``scripts/demo_seed/.demo_buyer_auth.local.txt`` (gitignored,
   chmod 0600) so the demo operator can copy it into curl flows without
   a re-signup round-trip.
3. Idempotent: if the email already exists (HTTP 409 ERR_EMAIL_TAKEN)
   the script logs and exits 0.

Why HTTP and not direct DB
--------------------------
The auth store in v0.1 is process-local in-memory inside the Next.js
portal container (planner Q10 default). A direct DB seed would write to
Postgres but the portal would not see it until the v0.1.1 Postgres
backend lands. Using the portal's own HTTP API guarantees the seed
lands in the same store the running portal reads from.

In v0.1.1 (Postgres backend), this script will switch to the
search-admin CLI pattern that ``seed_buyer.py`` already uses.

Demo credentials
----------------
  email:    demo@buyer.example
  password: radivault-demo-2026
  org:      Demo Buyer Global AI
  intent:   commercial-ai

Apply (after the portal is up on the configured PORTAL_URL):

  python scripts/demo_seed/seed_buyer_auth.py

Or via docker:

  docker compose exec portal \
    python /app/scripts/demo_seed/seed_buyer_auth.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("demo_seed.buyer_auth")

DEFAULT_EMAIL = "demo@buyer.example"
DEFAULT_PASSWORD = "radivault-demo-2026"
DEFAULT_ORG = "Demo Buyer Global AI"
DEFAULT_INTENT = "commercial-ai"
DEFAULT_PORTAL_URL = "http://localhost:3000"
DEFAULT_OUT_PATH = Path(__file__).parent / ".demo_buyer_auth.local.txt"


def signup(
    portal_url: str,
    *,
    email: str,
    password: str,
    organization: str,
    intent: str,
) -> dict:
    """POST /api/auth/signup. Returns the parsed JSON body."""
    body = json.dumps(
        {
            "email": email,
            "password": password,
            "organization": organization,
            "intent": intent,
            "tosPrivacyConsent": True,
            "marketingEmailOptIn": False,
            "pipaConsents": None,
            "locale": "en",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url=portal_url.rstrip("/") + "/api/auth/signup",
        method="POST",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = {}
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            pass
        if exc.code == 409 and payload.get("error", {}).get("code") == "ERR_EMAIL_TAKEN":
            log.info(
                "buyer_exists email=%s — idempotent skip (no plaintext re-issued)",
                email,
            )
            return {"_already_exists": True, "email": email}
        sys.stderr.write(
            f"[ERR_SEED_AUTH_SIGNUP_FAILED] HTTP {exc.code}\n"
            f"  body: {json.dumps(payload, indent=2)}\n"
        )
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed a demo email/password buyer (FR-AUTH-12)"
    )
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--organization", default=DEFAULT_ORG)
    parser.add_argument(
        "--intent",
        default=DEFAULT_INTENT,
        choices=["research", "commercial-ai", "clinical-trial", "other"],
    )
    parser.add_argument(
        "--portal-url",
        default=os.environ.get("PORTAL_URL", DEFAULT_PORTAL_URL),
    )
    parser.add_argument(
        "--out-path",
        type=Path,
        default=DEFAULT_OUT_PATH,
        help="Where to write the freshly-issued plaintext API key (chmod 0600).",
    )
    parser.add_argument(
        "--skip-if-key-file-exists",
        action="store_true",
        help="If --out-path already exists, skip signup (for repeat demo bring-up).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.skip_if_key_file_exists and args.out_path.exists():
        log.info("skip auth seed — key file already present at %s", args.out_path)
        return 0

    payload = signup(
        args.portal_url,
        email=args.email,
        password=args.password,
        organization=args.organization,
        intent=args.intent,
    )

    if payload.get("_already_exists"):
        # Don't overwrite the existing key file — operator may already have
        # captured the original plaintext.
        return 0

    plaintext = payload.get("apiKeyRevealOnce")
    if not plaintext:
        sys.stderr.write(
            "[ERR_SEED_AUTH_NO_PLAINTEXT] /api/auth/signup did not include "
            "apiKeyRevealOnce in its response.\n"
            f"  body: {json.dumps(payload, indent=2)}\n"
        )
        return 3

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(plaintext + "\n", encoding="utf-8")
    os.chmod(args.out_path, 0o600)

    sys.stdout.write(
        "\n".join(
            [
                "=" * 72,
                " RadiVault demo buyer auth credentials seeded",
                "=" * 72,
                f" email      : {args.email}",
                f" password   : {args.password}",
                f" org        : {args.organization}",
                f" intent     : {args.intent}",
                f" buyerId    : {payload.get('buyerId')}",
                f" kid        : {payload.get('apiKeyKid')}",
                f" written_to : {args.out_path}",
                "-" * 72,
                " Plaintext API key (shown ONCE, copy now):",
                "",
                f"   {plaintext}",
                "",
                "=" * 72,
                "",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
