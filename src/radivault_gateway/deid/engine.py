"""De-ID engine implementing DICOM PS3.15 Annex E Basic Profile + options.

Implements FR-6..FR-13 (dev-spec §4.2) and the Annex A matrix (§13).

Design decisions:
- We bypass ``pydicom/deid`` and apply our own tag matrix because v0.1 needs
  deterministic UID pseudonymisation with per-hospital salt + per-patient date
  offsets that must round-trip via the StateDB. A small internal recipe is
  easier to audit against AC-32 than wiring pydicom/deid hooks.
- UID pseudonymisation: ``org_root_oid + '.' + decimal_truncate(sha256(salt||uid), 40)``.
  The resulting UID fits within 64 characters because org_root_oid is capped at
  48 chars (config schema enforces this) and the suffix is at most 13 decimal
  digits from 40 bits.
- Date shift: ``offset_days = (int.from_bytes(sha256(salt||patient_id)[:4]) % 3650) - 1825``.
  Deterministic per patient and persisted in ``patient_date_offset``.
- Burned-in quarantine: ``(0028,0301) == 'YES'`` OR modality in blacklist →
  raise :class:`QuarantineRequired`. No masking; the orchestrator moves the
  study to the quarantine directory.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pydicom
from pydicom.dataset import Dataset
from pydicom.tag import Tag

from radivault_gateway.config import RetainOptions
from radivault_gateway.state import StateDB

log = logging.getLogger("radivault.deid")


# DICOM Method Code Sequence codes (PS3.16 CID 7050)
METHOD_CODES = {
    "basic": ("113100", "Basic Application Confidentiality Profile"),
    "longitudinal_dates": (
        "113107",
        "Retain Longitudinal Temporal Information Modified Dates Option",
    ),
    "patient_characteristics": ("113108", "Retain Patient Characteristics Option"),
    "clean_descriptors": ("113105", "Clean Descriptors Option"),
    "clean_graphics": ("113109", "Retain Safe Private Option"),  # placeholder; real code differs
}

# Blacklist of PHI tags that must not remain after de-id (FR-13 reverify).
PHI_BLACKLIST: set[int] = {
    Tag(0x0010, 0x0010).element | (Tag(0x0010, 0x0010).group << 16),  # PatientName
    Tag(0x0010, 0x1040).element | (Tag(0x0010, 0x1040).group << 16),  # PatientAddress
    Tag(0x0010, 0x2154).element | (Tag(0x0010, 0x2154).group << 16),  # PatientTelephone
    Tag(0x0010, 0x0021).element | (Tag(0x0010, 0x0021).group << 16),  # IssuerOfPatientID
    Tag(0x0008, 0x0080).element | (Tag(0x0008, 0x0080).group << 16),  # InstitutionName
    Tag(0x0008, 0x0081).element | (Tag(0x0008, 0x0081).group << 16),  # InstitutionAddress
    Tag(0x0008, 0x1050).element | (Tag(0x0008, 0x1050).group << 16),  # PerformingPhysicianName
    Tag(0x0008, 0x1060).element | (Tag(0x0008, 0x1060).group << 16),  # NameOfPhysiciansReadingStudy
    Tag(0x0008, 0x1070).element | (Tag(0x0008, 0x1070).group << 16),  # OperatorsName
    Tag(0x0018, 0x1000).element | (Tag(0x0018, 0x1000).group << 16),  # DeviceSerialNumber
    Tag(0x0008, 0x1010).element | (Tag(0x0008, 0x1010).group << 16),  # StationName
    Tag(0x0020, 0x4000).element | (Tag(0x0020, 0x4000).group << 16),  # ImageComments
    Tag(0x0032, 0x4000).element | (Tag(0x0032, 0x4000).group << 16),  # StudyComments
    Tag(0x0040, 0x1400).element | (Tag(0x0040, 0x1400).group << 16),  # RequestedProcedureComments
}


# Annex A matrix: action codes.
# X=remove, Z=empty, D=dummy, U=pseudo-UID, K=keep, C=clean (whitelist)
ANNEX_E_MATRIX: dict[tuple[int, int], str] = {
    (0x0010, 0x0010): "Z",  # PatientName
    (0x0010, 0x0020): "D",  # PatientID
    (0x0010, 0x0021): "X",  # IssuerOfPatientID
    (0x0010, 0x0030): "D",  # PatientBirthDate
    (0x0010, 0x0040): "K",  # PatientSex
    (0x0010, 0x1010): "D",  # PatientAge
    (0x0010, 0x1040): "X",  # PatientAddress
    (0x0010, 0x2154): "X",  # PatientTelephoneNumbers
    (0x0008, 0x0050): "Z",  # AccessionNumber
    (0x0008, 0x0080): "X",  # InstitutionName
    (0x0008, 0x0081): "X",  # InstitutionAddress
    (0x0008, 0x0090): "Z",  # ReferringPhysicianName
    (0x0008, 0x1050): "X",  # PerformingPhysicianName
    (0x0008, 0x1060): "X",  # NameOfPhysiciansReadingStudy
    (0x0008, 0x1070): "X",  # OperatorsName
    (0x0020, 0x0010): "Z",  # StudyID
    (0x0020, 0x000D): "U",  # StudyInstanceUID
    (0x0020, 0x000E): "U",  # SeriesInstanceUID
    (0x0008, 0x0018): "U",  # SOPInstanceUID
    (0x0020, 0x0052): "U",  # FrameOfReferenceUID
    (0x0020, 0x0200): "U",  # SynchronizationFrameOfReferenceUID
    (0x0008, 0x0020): "D",  # StudyDate
    (0x0008, 0x0021): "D",  # SeriesDate
    (0x0008, 0x0022): "D",  # AcquisitionDate
    (0x0008, 0x0023): "D",  # ContentDate
    (0x0008, 0x0030): "D",  # StudyTime
    (0x0008, 0x0031): "D",  # SeriesTime
    (0x0008, 0x0032): "D",  # AcquisitionTime
    (0x0008, 0x0033): "D",  # ContentTime
    (0x0008, 0x1030): "C",  # StudyDescription
    (0x0008, 0x103E): "C",  # SeriesDescription
    (0x0020, 0x4000): "X",  # ImageComments
    (0x0032, 0x4000): "X",  # StudyComments
    (0x0040, 0x1400): "X",  # RequestedProcedureComments
    (0x0008, 0x0070): "K",  # Manufacturer
    (0x0008, 0x1090): "K",  # ManufacturerModelName
    (0x0018, 0x1000): "X",  # DeviceSerialNumber
    (0x0008, 0x1010): "X",  # StationName
    (0x0028, 0x0301): "K",  # BurnedInAnnotation
    (0x0008, 0x0005): "K",  # SpecificCharacterSet
}


# Date tags and time tags — applied after the matrix.
DATE_TAGS = {
    (0x0008, 0x0020),
    (0x0008, 0x0021),
    (0x0008, 0x0022),
    (0x0008, 0x0023),
    (0x0010, 0x0030),
}
TIME_TAGS = {(0x0008, 0x0030), (0x0008, 0x0031), (0x0008, 0x0032), (0x0008, 0x0033)}


# UID tags that must always be pseudonymised (FR-8, AC-6).
UID_TAGS = {
    (0x0020, 0x000D),
    (0x0020, 0x000E),
    (0x0008, 0x0018),
    (0x0020, 0x0052),
    (0x0020, 0x0200),
}


# Description whitelist (simple keyword match, case-insensitive). Anything not
# matching is cleared.
DESCRIPTOR_WHITELIST_RE = re.compile(
    r"\b(ct|mr|mri|cr|dx|us|pet|xa|nm|brain|chest|abdomen|spine|head|lumbar|cervical|thoracic|"
    r"pelvis|hip|knee|ankle|shoulder|elbow|wrist|hand|foot|with|without|contrast|w/o|w/)\b",
    re.IGNORECASE,
)


@dataclass
class DeidResult:
    pseudo_study_uid: str
    pseudo_series_uids: list[str]
    pseudo_sop_uids: list[str]
    n_instances: int
    n_bytes: int
    patient_offset_days: int
    duration_ms: int
    output_paths: list[Path] = field(default_factory=list)


@dataclass
class ReverifyResult:
    ok: bool
    offending: list[tuple[int, int, str]]  # (group, element, reason)


class QuarantineRequired(Exception):
    """Raised by :class:`DeidEngine` when burn-in is detected."""

    def __init__(self, reason: str, offending_sops: list[str] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.offending_sops = offending_sops or []


class DeidEngine:
    """Annex E Basic Profile + options de-identifier.

    Mutates datasets in-memory; callers pass input DICOM paths and an output
    directory where de-identified files are written using pseudo UIDs.
    """

    def __init__(
        self,
        *,
        salt: str,
        salt_version: int,
        org_root_oid: str,
        state_db: StateDB,
        retain: RetainOptions | None = None,
        burnin_quarantine_modalities: Iterable[str] = ("SC", "US", "OT"),
        ruleset_version: str = "v0.1.0",
        version_string: str = "0.1.0",
    ) -> None:
        self._salt_bytes = salt.encode("utf-8")
        self._salt_version = salt_version
        self._org_root = org_root_oid
        self._db = state_db
        self._retain = retain or RetainOptions()
        self._blacklist_mods = {m.upper() for m in burnin_quarantine_modalities}
        self._ruleset_version = ruleset_version
        self._version_string = version_string

    # ---- public API ----

    def deidentify_study(self, input_dir: Path, output_dir: Path) -> DeidResult:
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = sorted(input_dir.glob("*.dcm"))
        if not paths:
            raise FileNotFoundError(f"no .dcm files under {input_dir}")

        started = datetime.now()
        pseudo_study_uid: str | None = None
        pseudo_series_uids: set[str] = set()
        pseudo_sop_uids: list[str] = []
        output_paths: list[Path] = []
        total_bytes = 0
        patient_offset_days: int = 0

        for src in paths:
            ds = pydicom.dcmread(src, force=False)
            self._check_quarantine(ds, src)
            offset = self._ensure_patient_offset(ds)
            patient_offset_days = offset
            self._apply_matrix(ds, offset)
            self._set_method_tags(ds)

            new_study = self.pseudo_uid(ds.get("StudyInstanceUID"), "study")
            new_series = self.pseudo_uid(ds.get("SeriesInstanceUID"), "series")
            new_sop = self.pseudo_uid(ds.get("SOPInstanceUID"), "sop")
            ds.StudyInstanceUID = new_study
            ds.SeriesInstanceUID = new_series
            ds.SOPInstanceUID = new_sop
            if hasattr(ds, "file_meta") and getattr(
                ds.file_meta, "MediaStorageSOPInstanceUID", None
            ):
                ds.file_meta.MediaStorageSOPInstanceUID = new_sop

            pseudo_study_uid = new_study
            pseudo_series_uids.add(new_series)
            pseudo_sop_uids.append(new_sop)

            out_path = output_dir / f"{new_sop}.dcm"
            ds.save_as(out_path, enforce_file_format=False)
            output_paths.append(out_path)
            total_bytes += out_path.stat().st_size

        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        return DeidResult(
            pseudo_study_uid=pseudo_study_uid or "",
            pseudo_series_uids=sorted(pseudo_series_uids),
            pseudo_sop_uids=pseudo_sop_uids,
            n_instances=len(paths),
            n_bytes=total_bytes,
            patient_offset_days=patient_offset_days,
            duration_ms=duration_ms,
            output_paths=output_paths,
        )

    def reverify(self, deided_dir: Path) -> ReverifyResult:
        """FR-13: after de-id, re-scan for any blacklisted PHI tags.

        Blacklist = tags whose presence with a non-empty value would indicate
        PHI leakage. PatientName is special-cased to allow the canonical
        "ANON" replacement defined by FR-6/Annex A. Any other value triggers
        a reverify failure.
        """
        offending: list[tuple[int, int, str]] = []
        patient_name_tag = (0x0010, 0x0010)
        for path in sorted(Path(deided_dir).glob("*.dcm")):
            ds = pydicom.dcmread(path, force=False)
            for (group, element), _action in ANNEX_E_MATRIX.items():
                if (group, element) == patient_name_tag:
                    continue  # handled separately (Z-with-ANON is allowed)
                combined = (group << 16) | element
                if combined not in PHI_BLACKLIST:
                    continue
                tag = Tag(group, element)
                if tag in ds:
                    value = ds[tag].value
                    if value not in ("", None, b""):
                        offending.append((group, element, repr(value)[:80]))
            # PatientName: the Annex E matrix allowed "ANON" as the canonical
            # Z-replacement. Any other non-empty value is PHI leakage.
            if "PatientName" in ds:
                val = str(ds.PatientName)
                if val and val not in {"ANON", ""}:
                    offending.append((0x0010, 0x0010, f"PatientName={val!r}"))
        return ReverifyResult(ok=not offending, offending=offending)

    # ---- helpers ----

    def pseudo_uid(self, original: str | None, kind: str) -> str:
        """Deterministic UID pseudonymisation (FR-8).

        Writes a row to ``uid_map`` on first use so downstream audits can be
        reconciled. The original UID is kept only in the local SQLite.
        """
        if not original:
            return ""
        cached = self._db.lookup_pseudo_uid(str(original))
        if cached:
            return cached
        digest = hashlib.sha256(self._salt_bytes + str(original).encode("utf-8")).digest()
        # Take first 5 bytes (40 bits) and convert to decimal.
        suffix = str(int.from_bytes(digest[:5], "big"))
        pseudo = f"{self._org_root}.{suffix}"
        # DICOM UID max 64 characters.
        if len(pseudo) > 64:
            pseudo = pseudo[:64]
        self._db.upsert_uid_map(str(original), pseudo, kind=kind, salt_version=self._salt_version)
        return pseudo

    def _ensure_patient_offset(self, ds: Dataset) -> int:
        """FR-10: deterministic per-patient date offset in days."""
        pid = str(ds.get("PatientID", "")).strip()
        if not pid:
            return 0
        pid_hash = hashlib.sha256(self._salt_bytes + pid.encode("utf-8")).hexdigest()
        cached = self._db.lookup_patient_offset(pid_hash)
        if cached is not None:
            return cached
        digest = hashlib.sha256(self._salt_bytes + pid.encode("utf-8")).digest()
        offset = (int.from_bytes(digest[:4], "big") % 3650) - 1825
        self._db.upsert_patient_offset(pid_hash, offset, salt_version=self._salt_version)
        return offset

    def _check_quarantine(self, ds: Dataset, src: Path) -> None:
        """FR-11: burn-in detection → QuarantineRequired."""
        burned = str(ds.get("BurnedInAnnotation", "")).upper().strip()
        if burned == "YES":
            raise QuarantineRequired("burned_in_yes", [str(src.name)])
        modality = str(ds.get("Modality", "")).upper().strip()
        if modality in self._blacklist_mods:
            raise QuarantineRequired("blacklist_modality", [str(src.name)])

    def _apply_matrix(self, ds: Dataset, offset_days: int) -> None:
        for (group, element), action in ANNEX_E_MATRIX.items():
            tag = Tag(group, element)
            if (group, element) in UID_TAGS:
                # UIDs are handled explicitly below after matrix.
                continue
            if tag not in ds:
                continue
            self._apply_action(ds, tag, (group, element), action, offset_days)

        # Remove all private tags (FR matrix "모든 private tags X") unless
        # retain_options.safe_private is on — v0.1 forces off (FR-7).
        if not self._retain.safe_private:
            ds.remove_private_tags()

        # Device identity mode
        if self._retain.device_identity == "none":
            for group, element in ((0x0008, 0x0070), (0x0008, 0x1090)):
                tag = Tag(group, element)
                if tag in ds:
                    del ds[tag]

    def _apply_action(
        self,
        ds: Dataset,
        tag: Tag,
        ge: tuple[int, int],
        action: str,
        offset_days: int,
    ) -> None:
        if action == "X":
            del ds[tag]
            return
        if action == "Z":
            if ge == (0x0010, 0x0010):
                ds[tag].value = "ANON"
            else:
                ds[tag].value = ""
            return
        if action == "K":
            return
        if action == "D":
            if ge in DATE_TAGS:
                ds[tag].value = self._shift_date(str(ds[tag].value), offset_days, ge)
                return
            if ge in TIME_TAGS:
                ds[tag].value = self._mask_time(str(ds[tag].value))
                return
            if ge == (0x0010, 0x0020):  # PatientID -> dummy (hash-based)
                pid = str(ds[tag].value)
                digest = hashlib.sha256(self._salt_bytes + pid.encode("utf-8")).hexdigest()
                ds[tag].value = digest[:16]
                return
            if ge == (0x0010, 0x1010):  # PatientAge -> 5-year bin
                ds[tag].value = self._bin_age(str(ds[tag].value))
                return
            # Fallback: empty value
            ds[tag].value = ""
            return
        if action == "C":
            value = str(ds[tag].value or "")
            if self._retain.clean_descriptors and DESCRIPTOR_WHITELIST_RE.search(value):
                # Keep descriptor but strip non-whitelisted tokens.
                tokens = DESCRIPTOR_WHITELIST_RE.findall(value)
                ds[tag].value = " ".join(tokens).upper()
            else:
                ds[tag].value = ""
            return
        # Unknown action → safe default: clear.
        ds[tag].value = ""

    @staticmethod
    def _shift_date(raw: str, offset_days: int, ge: tuple[int, int]) -> str:
        raw = raw.strip()
        if not raw:
            return raw
        if ge == (0x0010, 0x0030):  # PatientBirthDate → year only
            if len(raw) >= 4:
                return raw[:4] + "0101"
            return raw
        # Normal YYYYMMDD
        try:
            d = datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            return ""
        from datetime import timedelta

        shifted = d + timedelta(days=offset_days)
        return shifted.strftime("%Y%m%d")

    @staticmethod
    def _mask_time(raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return raw
        # Keep HHMM, zero the rest (FR-10 세부: 분 단위까지만)
        if "." in raw:
            raw = raw.split(".", 1)[0]
        if len(raw) >= 4:
            return raw[:4] + "00"
        return raw.ljust(6, "0")

    @staticmethod
    def _bin_age(raw: str) -> str:
        # DICOM PatientAge format: nnnU where U is {D,W,M,Y}.
        match = re.match(r"(\d+)([DWMY])", raw.strip())
        if not match:
            return ""
        num, unit = int(match.group(1)), match.group(2)
        if unit == "Y":
            binned = (num // 5) * 5
            return f"{binned:03d}Y"
        return raw  # leave sub-year ages unchanged (neonatal context)

    def _set_method_tags(self, ds: Dataset) -> None:
        ds.PatientIdentityRemoved = "YES"
        ds.DeidentificationMethod = f"RadiVault v{self._version_string} Annex E Basic + options"
        # Method code sequence (0012,0064)
        seq: list[Dataset] = []
        code_pairs = [
            ("113100", "Basic Application Confidentiality Profile"),
        ]
        if self._retain.longitudinal_dates:
            code_pairs.append(
                (
                    "113107",
                    "Retain Longitudinal Temporal Information Modified Dates Option",
                )
            )
        if self._retain.patient_characteristics:
            code_pairs.append(("113108", "Retain Patient Characteristics Option"))
        if self._retain.clean_descriptors:
            code_pairs.append(("113105", "Clean Descriptors Option"))
        for code, meaning in code_pairs:
            item = Dataset()
            item.CodeValue = code
            item.CodingSchemeDesignator = "DCM"
            item.CodeMeaning = meaning
            seq.append(item)
        ds.DeidentificationMethodCodeSequence = seq
