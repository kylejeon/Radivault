"""Version endpoint (dev-spec §7.10)."""

from __future__ import annotations

import os
import sys

from fastapi import APIRouter, Request

from radivault_fulfillment import __version__

router = APIRouter(tags=["version"])


@router.get("/v1/version")
def version(request: Request) -> dict:
    return {
        "service": "radivault-fulfillment",
        "version": __version__,
        "api_contract_version": getattr(
            getattr(request.app.state, "settings", None), "app", None
        )
        and getattr(request.app.state.settings.app, "api_contract_version", "1")
        or "1",
        "git_sha": os.environ.get("RADIVAULT_GIT_SHA", "unknown"),
        "python_version": ".".join(str(s) for s in sys.version_info[:3]),
    }
