"""Local-filesystem object store — dev/test fallback when MinIO isn't running."""

from __future__ import annotations

import shutil
from pathlib import Path

from radivault_central.storage.base import ObjectStoreError


class LocalFsObjectStore:
    """Writes objects as files under ``root`` — useful for pytest fixtures."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_object(self, key: str, data: bytes, *, content_type: str = "application/dicom") -> None:
        target = self.root / key
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError as exc:
            raise ObjectStoreError(f"local fs put failed: {exc}") from exc

    def delete_objects(self, keys: list[str]) -> None:
        for key in keys:
            path = self.root / key
            try:
                if path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                continue

    def head_bucket(self) -> bool:
        return self.root.exists() and self.root.is_dir()
