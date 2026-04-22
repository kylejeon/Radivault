"""Object store Protocol (dev-spec FR-46)."""

from __future__ import annotations

from typing import Protocol


class ObjectStoreError(RuntimeError):
    """Raised when a storage call fails after retries."""


class StoragePathTraversalError(ObjectStoreError):
    """Raised when a candidate key would escape the configured storage root.

    The guarded drivers reject keys whose resolved path is not a descendant of
    the storage root — typically because the key contained ``..`` segments, an
    absolute path, or a symlink that points outside the root.
    """

    code: str = "ERR_STORE_PATH_TRAVERSAL"


class ObjectStore(Protocol):
    """Narrow interface for the handful of operations the ingest path needs."""

    def put_object(
        self, key: str, data: bytes, *, content_type: str = "application/dicom"
    ) -> None: ...

    def delete_objects(self, keys: list[str]) -> None: ...

    def head_bucket(self) -> bool: ...
