"""Filesystem staging (FR-14..FR-17).

Layout: ``{root}/{pseudo_study_uid}/{pseudo_series_uid}/{pseudo_sop_uid}.dcm``.
"""

from __future__ import annotations

import contextlib
import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

log = logging.getLogger("radivault.staging")


class StagingManager:
    def __init__(
        self,
        root: str | Path,
        *,
        retention_hours: int = 72,
        max_disk_pct: int = 80,
        quarantine_root: str | Path | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            self.root.chmod(0o700)
        self.retention_hours = retention_hours
        self.max_disk_pct = max_disk_pct
        # Appendix B: /var/lib/radivault/quarantine/<pseudo_study_uid>/
        # default derived from staging.root.parent / quarantine
        self.quarantine_root = (
            Path(quarantine_root)
            if quarantine_root is not None
            else self.root.parent / "quarantine"
        )
        self.quarantine_root.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            self.quarantine_root.chmod(0o700)

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
            log.error(
                "staging cleanup failed",
                extra={
                    "pseudo_study_uid": pseudo_study_uid,
                    "error": str(exc),
                },
            )
            return False

    def quarantine_dir(self, identifier: str) -> Path:
        """Return the quarantine sub-directory path for a given identifier.

        The identifier is typically a pseudo_study_uid, or a ``quarantine_<hash>``
        token when the original study could not be pseudonymised (burn-in before
        UID mapping). The directory is created on demand with mode 0o700.
        """
        path = self.quarantine_root / identifier
        path.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            path.chmod(0o700)
        return path

    def move_to_quarantine(self, source_dir: Path, identifier: str) -> Path:
        """Move ``source_dir``'s contents into the quarantine directory.

        Preserves the evidence required by AC-8 / FR-11. Returns the quarantine
        directory path.
        """
        source_dir = Path(source_dir)
        target = self.quarantine_dir(identifier)
        if source_dir.exists():
            for child in source_dir.iterdir():
                shutil.move(str(child), str(target / child.name))
            # Non-empty or already gone; ignore — the files we care about
            # have been moved already.
            with contextlib.suppress(OSError):
                source_dir.rmdir()
        return target

    def disk_usage_pct(self) -> float:
        total, used, _free = shutil.disk_usage(self.root)
        if total == 0:
            return 0.0
        return (used / total) * 100.0

    def backpressure_triggered(self) -> bool:
        """FR-17: if staging disk is above max_disk_pct, pause new fetches."""
        return self.disk_usage_pct() >= float(self.max_disk_pct)

    def stale_studies(self, *, threshold_seconds: int | None = None) -> list[Path]:
        """FR-16: return study dirs older than the retention threshold.

        ``threshold_seconds`` overrides the default derived from
        ``retention_hours``. Does not delete anything — caller decides.
        """
        if threshold_seconds is None:
            threshold_seconds = int(self.retention_hours * 3600)
        cutoff = datetime.now(tz=UTC) - timedelta(seconds=threshold_seconds)
        stale: list[Path] = []
        for child in self.root.iterdir():
            if not child.is_dir():
                continue
            mtime = datetime.fromtimestamp(child.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                stale.append(child)
        return stale
