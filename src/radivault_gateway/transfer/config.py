"""Gateway ``transfer.*`` config subtree (dev-spec §6.6 + §14 G-1).

Default ``enabled=False`` ensures existing Gateway deployments are unaffected
until an operator opts in.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TransferConfig:
    enabled: bool = False
    central_url: str = "https://fulfillment.radivault.io"
    auth_token: str | None = None
    poll_wait_seconds: int = 30
    max_concurrent_jobs: int = 2
    lease_extend_interval_seconds: int = 300
    progress_report_interval_seconds: int = 60
    retry_backoff_initial_seconds: int = 30
    retry_backoff_factor: int = 2
    retry_backoff_cap_seconds: int = 600
