"""Local-filesystem object store — dev/test fallback when MinIO isn't running."""

from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath

from radivault_central.storage.base import (
    ObjectStoreError,
    StoragePathTraversalError,
)


class LocalFsObjectStore:
    """Writes objects as files under ``root`` — useful for pytest fixtures.

    All key inputs are path-traversal guarded: keys that resolve outside the
    configured root (via ``..`` segments, absolute paths, or symlinks) are
    rejected with :class:`StoragePathTraversalError`. This matches the S3
    driver's key-style semantics and prevents manifest-controlled strings
    (``filename``, ``pseudo_study_uid``) from escaping the storage sandbox.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._resolved_root = self.root.resolve()

    # ------------------------------------------------------------------
    def _safe_target(self, key: str) -> Path:
        """Resolve ``key`` under ``root`` and assert it stays inside the root.

        Rejects keys that are absolute, contain ``..`` segments, or that would
        resolve (after following any existing symlinks) outside ``self.root``.
        """
        if not key:
            raise StoragePathTraversalError("empty object key")
        # Disallow backslashes (Windows-style separators) and NUL bytes — both
        # are legitimate S3 characters but would be ambiguous on POSIX fs.
        if "\x00" in key or "\\" in key:
            raise StoragePathTraversalError(f"illegal characters in key: {key!r}")
        posix = PurePosixPath(key)
        if posix.is_absolute():
            raise StoragePathTraversalError(f"absolute key rejected: {key!r}")
        if any(part == ".." for part in posix.parts):
            raise StoragePathTraversalError(f"parent-segment key rejected: {key!r}")
        target = (self.root / key).resolve()
        try:
            target.relative_to(self._resolved_root)
        except ValueError as exc:
            raise StoragePathTraversalError(f"key resolves outside storage root: {key!r}") from exc
        return target

    # ------------------------------------------------------------------
    def put_object(self, key: str, data: bytes, *, content_type: str = "application/dicom") -> None:
        target = self._safe_target(key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError as exc:
            raise ObjectStoreError(f"local fs put failed: {exc}") from exc

    def delete_objects(self, keys: list[str]) -> None:
        for key in keys:
            try:
                path = self._safe_target(key)
            except StoragePathTraversalError:
                # Never follow a traversal key on cleanup — skip silently.
                continue
            try:
                if path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                continue

    def head_bucket(self) -> bool:
        return self.root.exists() and self.root.is_dir()
