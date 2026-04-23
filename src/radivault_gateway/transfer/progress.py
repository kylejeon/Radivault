"""Progress-reporter helper — keeps a running counter + schedules lease renewal."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ProgressState:
    n_fetched: int = 0
    n_deided: int = 0
    n_uploaded: int = 0


@dataclass
class ProgressReporter:
    interval_seconds: int = 60
    lease_extend_every: int = 1  # every N reports
    state: ProgressState = field(default_factory=ProgressState)
    last_reported_at: float = 0.0
    reports_since_extend: int = 0

    def record(self, *, fetched: int = 0, deided: int = 0, uploaded: int = 0) -> None:
        self.state.n_fetched += fetched
        self.state.n_deided += deided
        self.state.n_uploaded += uploaded

    def due(self, *, now_fn=time.monotonic) -> bool:
        return (now_fn() - self.last_reported_at) >= self.interval_seconds

    def next_payload(self, *, now_fn=time.monotonic) -> dict:
        self.last_reported_at = now_fn()
        self.reports_since_extend += 1
        lease_extend = self.reports_since_extend >= self.lease_extend_every
        if lease_extend:
            self.reports_since_extend = 0
        return {
            "n_fetched": self.state.n_fetched,
            "n_deided": self.state.n_deided,
            "n_uploaded": self.state.n_uploaded,
            "lease_extend": lease_extend,
        }
