"""Filesystem staging (FR-14..FR-17).

Layout: ``{root}/{pseudo_study_uid}/{pseudo_series_uid}/{pseudo_sop_uid}.dcm``.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path


log = logging.getLogger("radivault.staging")


class StagingManager:
    def __init__(self, root: str | Path, *, retention_hours: int = 72, max_disk_pct: int = 80) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.retention_hours = retention_hours
        self.max_disk_pct = max_disk_pct

    def study_dir(self, pseudo_study_uid: str) -> Path:
        return self.root / pseudo_study_uid

    def ensure_study_dir(self, pseudo_study_uid: str) -> Path:
        path = self.study_dir(pseudo_study_uid)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def cleanup_study(self, pseudo_study_uid: str) -> bool:
        """Remove the staging directory for a study. FR-15."""
        path = self.study_dir(pseudo_study_uid)
        if not path.exists():
            return True
        try:
            shutil.rmtree(path)
            return True
        except OSError as exc:
            log.error("staging cleanup failed", extra={
                "pseudo_study_uid": pseudo_study_uid,
                "error": str(exc),
            })
            return False

    def disk_usage_pct(self) -> float:
        total, used, _free = shutil.disk_usage(self.root)
        if total == 0:
            return 0.0
        return (used / total) * 100.0

    def backpressure_triggered(self) -> bool:
        """FR-17: if staging disk is above max_disk_pct, pause new fetches."""
        return self.disk_usage_pct() >= float(self.max_disk_pct)

    def stale_studies(self) -> list[Path]:
        """FR-16: return study dirs older than retention_hours (warn, do not delete)."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=self.retention_hours)
        stale: list[Path] = []
        for child in self.root.iterdir():
            if not child.is_dir():
                continue
            mtime = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                stale.append(child)
        return stale
