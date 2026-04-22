"""``GET /v1/version`` (dev-spec FR-20)."""

from __future__ import annotations

import os
import sys

from fastapi import APIRouter

from radivault_central import __version__

router = APIRouter()

_BUILT_AT = os.environ.get("RADIVAULT_BUILT_AT", "unknown")
_GIT_SHA = os.environ.get("RADIVAULT_GIT_SHA", "unknown")
_API_CONTRACT_VERSION = os.environ.get("RADIVAULT_API_CONTRACT_VERSION", "1")


@router.get("/v1/version", include_in_schema=True)
def version() -> dict[str, str]:
    return {
        "version": __version__,
        "git_sha": _GIT_SHA,
        "built_at": _BUILT_AT,
        "api_contract_version": _API_CONTRACT_VERSION,
        "python": sys.version.split()[0],
    }
