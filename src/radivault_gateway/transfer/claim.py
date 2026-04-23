"""HTTP client wrapping the fulfillment long-poll + lease endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("radivault_gateway.transfer.claim")


@dataclass
class Claim:
    transfer_job_id: str
    order_id: str
    hospital_id: str
    studies: list[dict]
    lease_expires_at: str
    ruleset_version_required: str
    salt_version_required: int
    cancel_requested: bool


class ClaimClient:
    """Thin wrapper around httpx. Sync — matches the rest of gateway code."""

    def __init__(
        self,
        *,
        central_url: str,
        auth_token: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base = central_url.rstrip("/")
        self._token = auth_token
        self._http = http_client or httpx.Client(timeout=httpx.Timeout(60.0))

    def _headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        if idempotency_key:
            h["Idempotency-Key"] = idempotency_key
        return h

    def claim(self, *, wait_seconds: int = 30) -> Claim | None:
        url = f"{self._base}/v1/gateway/transfer-jobs"
        resp = self._http.get(
            url,
            params={"wait": wait_seconds, "max_jobs": 1},
            headers=self._headers(),
        )
        if resp.status_code == 204:
            return None
        resp.raise_for_status()
        data = resp.json()
        return Claim(
            transfer_job_id=data["transfer_job_id"],
            order_id=data["order_id"],
            hospital_id=data["hospital_id"],
            studies=data["studies"],
            lease_expires_at=data["lease_expires_at"],
            ruleset_version_required=data["ruleset_version_required"],
            salt_version_required=data["salt_version_required"],
            cancel_requested=bool(data.get("cancel_requested", False)),
        )

    def progress(
        self,
        *,
        transfer_job_id: str,
        n_fetched: int,
        n_deided: int,
        n_uploaded: int,
        lease_extend: bool,
        idempotency_key: str,
    ) -> dict[str, Any]:
        url = f"{self._base}/v1/gateway/transfer-jobs/{transfer_job_id}/progress"
        resp = self._http.post(
            url,
            json={
                "n_fetched": n_fetched,
                "n_deided": n_deided,
                "n_uploaded": n_uploaded,
                "lease_extend": lease_extend,
            },
            headers=self._headers(idempotency_key=idempotency_key),
        )
        resp.raise_for_status()
        return resp.json()

    def complete(
        self,
        *,
        transfer_job_id: str,
        manifest: list[dict],
        audit_ref: dict | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        url = f"{self._base}/v1/gateway/transfer-jobs/{transfer_job_id}/complete"
        resp = self._http.post(
            url,
            json={"manifest": manifest, "audit_ref": audit_ref},
            headers=self._headers(idempotency_key=idempotency_key),
        )
        resp.raise_for_status()
        return resp.json()

    def fail(
        self,
        *,
        transfer_job_id: str,
        reason_code: str,
        details: str,
        retryable: bool,
        idempotency_key: str,
    ) -> dict[str, Any]:
        url = f"{self._base}/v1/gateway/transfer-jobs/{transfer_job_id}/fail"
        resp = self._http.post(
            url,
            json={"reason_code": reason_code, "details": details, "retryable": retryable},
            headers=self._headers(idempotency_key=idempotency_key),
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._http.close()
