"""Business rules on top of manifest pydantic schema (dev-spec §4.6)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from radivault_central.db.models import Hospital
from radivault_central.errors import (
    ManifestAnon,
    ManifestDeid,
    ManifestRuleset,
    ManifestSalt,
    ManifestSchema,
    ManifestTooBig,
    ManifestTooMany,
    ManifestVersion,
)
from radivault_central.manifest.schema import Manifest, ManifestMetadataOnly

ALLOWED_ANON_FLAG = "fully_anonymized"
REQUIRED_DEID_CODE = "113100"


@dataclass
class ManifestValidator:
    """Stateless helper that turns raw manifest bytes into a validated Manifest."""

    hospital: Hospital
    max_manifest_bytes: int = 1_048_576

    def parse_and_validate(self, raw: bytes) -> Manifest:
        decoded = self._decode(raw)
        try:
            manifest = Manifest.model_validate(decoded)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first.get("loc", [])) or "?"
            raise ManifestSchema(detail=f"{loc}: {first.get('msg', 'invalid')}") from exc

        self._check_version(manifest)
        self._check_anonymization(manifest)
        self._check_ruleset(manifest)
        self._check_salt(manifest)
        self._check_deid_methods(manifest)
        self._check_hospital_limits(manifest)
        return manifest

    def parse_and_validate_metadata_only(self, raw: bytes) -> ManifestMetadataOnly:
        """Parse + validate a metadata-only manifest (Flow A).

        Re-uses every business rule applied to a full-payload manifest — the
        anonymization flag, ruleset allowlist, salt version, and DICOM
        method-code check — but accepts an empty ``files`` array and
        ``n_instances == 0``. Downstream callers will persist the study row
        with ``central_object_present=False``.
        """
        decoded = self._decode(raw)
        try:
            manifest = ManifestMetadataOnly.model_validate(decoded)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first.get("loc", [])) or "?"
            raise ManifestSchema(detail=f"{loc}: {first.get('msg', 'invalid')}") from exc

        self._check_version(manifest)
        self._check_anonymization(manifest)
        self._check_ruleset(manifest)
        self._check_salt(manifest)
        self._check_deid_methods(manifest)
        self._check_hospital_limits(manifest)
        return manifest

    # ------------------------------------------------------------------
    def _decode(self, raw: bytes) -> dict:
        if not raw:
            raise ManifestSchema(detail="empty manifest body")
        if len(raw) > self.max_manifest_bytes:
            raise ManifestTooBig(detail="manifest payload larger than limit")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManifestSchema(detail=f"manifest JSON decode failed: {exc}") from exc

    # ------------------------------------------------------------------
    def _check_version(self, manifest: Manifest) -> None:
        # metadata-thumbnail-ingest FR-META-1: accept v1 (legacy) and v2 (new
        # study/series/thumbnail fields). Higher versions are rejected so the
        # cross-team contract stays explicit.
        if manifest.manifest_version not in (1, 2):
            raise ManifestVersion(
                detail=f"manifest_version={manifest.manifest_version} unsupported"
            )

    def _check_anonymization(self, manifest: Manifest) -> None:
        if manifest.anonymization_flag != ALLOWED_ANON_FLAG:
            raise ManifestAnon(
                detail=(
                    f"anonymization_flag={manifest.anonymization_flag!r} "
                    f"— must be {ALLOWED_ANON_FLAG!r}"
                )
            )

    def _check_ruleset(self, manifest: Manifest) -> None:
        allowed: list[str] = list(self.hospital.allowed_ruleset_versions or ["v0.1.0"])
        if manifest.deid.ruleset_version not in allowed:
            raise ManifestRuleset(
                detail=(
                    f"ruleset_version={manifest.deid.ruleset_version!r} "
                    f"not in hospital allowlist {allowed}"
                )
            )

    def _check_salt(self, manifest: Manifest) -> None:
        if manifest.deid.salt_version != self.hospital.salt_version_current:
            raise ManifestSalt(
                detail=(
                    f"salt_version={manifest.deid.salt_version} "
                    f"current={self.hospital.salt_version_current}"
                )
            )

    def _check_deid_methods(self, manifest: Manifest) -> None:
        if REQUIRED_DEID_CODE not in manifest.deid.method_code_sequence:
            raise ManifestDeid(detail=f"method_code_sequence missing required {REQUIRED_DEID_CODE}")

    def _check_hospital_limits(self, manifest: Manifest) -> None:
        if manifest.n_instances > self.hospital.max_instances_per_study:
            raise ManifestTooMany(
                detail=(
                    f"n_instances={manifest.n_instances} > "
                    f"max_instances_per_study={self.hospital.max_instances_per_study}"
                )
            )
        if manifest.total_bytes > self.hospital.max_study_bytes:
            raise ManifestTooBig(
                detail=(
                    f"total_bytes={manifest.total_bytes} > "
                    f"max_study_bytes={self.hospital.max_study_bytes}"
                )
            )
