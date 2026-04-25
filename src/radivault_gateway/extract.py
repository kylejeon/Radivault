"""DICOM header → buyer-facet metadata (dev-spec FR-META-2).

Pulls the 12 MVP fields the buyer search portal needs for facet filtering.
Empty / unparsable values are returned as ``None`` (placeholder strings are
forbidden by FR-META-3.2 — UI is responsible for the "Unknown" label).

The function operates on the **already-de-identified** dataset, so values
read here have passed Annex E rules (PatientSex 'K', BodyPartExamined 'K',
Manufacturer 'K', etc.). PatientAge is binned by the de-id engine to a 5-year
``nnnY`` value; this module re-bins to a human label like "30-34" / "90+".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pydicom

MAX_MANUFACTURER_LEN = 64
MAX_MODEL_LEN = 128


@dataclass
class StudyMetadata:
    """Twelve buyer-facet MVP fields (FR-META-2)."""

    body_part_examined: str | None = None
    patient_sex: str | None = None  # "M" | "F" | "O"
    patient_age_bucket: str | None = None  # "30-34" / "90+"
    manufacturer: str | None = None
    manufacturer_model_name: str | None = None
    study_date_shifted: date | None = None
    study_year: int | None = None
    slice_thickness_mm: float | None = None
    kvp: float | None = None
    n_series: int = 0
    n_instances: int = 0
    total_bytes: int = 0
    series: list[dict] = field(default_factory=list)


def _parse_age_bucket(raw: str | None) -> str | None:
    """DICOM PatientAge ``nnnY`` (already binned by de-id) → human label.

    Returns ``"30-34"`` for "030Y", ``"90+"`` for any age >= 90 (HIPAA Safe
    Harbor §164.514(b)(2)(i)). Returns ``None`` for empty / non-year units
    (neonatal D/W/M ages collapse to None for the MVP — facet bucket already
    covers them with the modality + body-part axis).
    """
    if not raw:
        return None
    raw = raw.strip().upper()
    if len(raw) < 2 or raw[-1] != "Y":
        return None
    try:
        years = int(raw[:-1])
    except ValueError:
        return None
    if years < 0:
        return None
    if years >= 90:
        return "90+"
    bucket_lo = (years // 5) * 5
    bucket_hi = bucket_lo + 4
    return f"{bucket_lo:02d}-{bucket_hi:02d}"


def _parse_birthdate_age(birth_raw: str, study_raw: str) -> str | None:
    """Compute PatientAge bucket from PatientBirthDate + StudyDate fallback."""
    if not birth_raw or not study_raw:
        return None
    try:
        birth_str = birth_raw.strip()
        study_str = study_raw.strip()
        if len(birth_str) < 4 or len(study_str) < 4:
            return None
        birth_year = int(birth_str[:4])
        study_year = int(study_str[:4])
        years = study_year - birth_year
    except ValueError:
        return None
    if years < 0:
        return None
    return _parse_age_bucket(f"{years:03d}Y")


def _parse_sex(raw: str | None) -> str | None:
    if not raw:
        return None
    val = raw.strip().upper()
    return val if val in ("M", "F", "O") else None


def _parse_body_part(raw: str | None) -> str | None:
    if not raw:
        return None
    val = raw.strip().upper()
    return val or None


def _trim(raw: str | None, max_len: int) -> str | None:
    if not raw:
        return None
    val = raw.strip()
    if not val:
        return None
    return val[:max_len]


def _parse_study_date(raw: str | None) -> date | None:
    """Parse already-shifted DICOM StudyDate (YYYYMMDD or YYYY-MM-DD)."""
    if not raw:
        return None
    val = raw.strip().replace("-", "")
    if len(val) < 8:
        return None
    try:
        return date(int(val[:4]), int(val[4:6]), int(val[6:8]))
    except ValueError:
        return None


def _parse_float(raw) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v


def extract_study_metadata(instances: list[Path]) -> StudyMetadata:
    """Extract the 12 MVP fields from a list of de-identified DICOM paths.

    Per FR-META-2, multi-instance studies use the **first parseable** instance
    for study/patient/manufacturer fields (DICOM standard guarantees consistency
    within a study). Series/instance counts are derived from the file list.
    """
    md = StudyMetadata()
    if not instances:
        return md

    series_map: dict[str, dict] = {}
    total_bytes = 0
    first_ds: pydicom.Dataset | None = None
    first_modality: str | None = None
    first_body_part: str | None = None

    for path in instances:
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True, force=False)
        except Exception:
            continue
        try:
            total_bytes += path.stat().st_size
        except OSError:
            pass

        if first_ds is None:
            first_ds = ds
            first_modality = str(getattr(ds, "Modality", "") or "").strip().upper() or None
            first_body_part = _parse_body_part(str(getattr(ds, "BodyPartExamined", "") or ""))

        series_uid = str(getattr(ds, "SeriesInstanceUID", "") or "")
        if not series_uid:
            continue
        entry = series_map.setdefault(
            series_uid,
            {
                "pseudo_series_uid": series_uid,
                "modality": str(getattr(ds, "Modality", "") or "").strip().upper() or None,
                "n_instances": 0,
                "body_part": _parse_body_part(
                    str(getattr(ds, "BodyPartExamined", "") or "")
                ),
                "slice_thickness_mm": _parse_float(getattr(ds, "SliceThickness", None)),
                "kvp": _parse_float(getattr(ds, "KVP", None)),
                "series_description_clean": None,
            },
        )
        entry["n_instances"] += 1

    md.n_series = len(series_map)
    md.n_instances = sum(s["n_instances"] for s in series_map.values())
    md.total_bytes = total_bytes
    md.series = list(series_map.values())

    if first_ds is None:
        return md

    md.body_part_examined = first_body_part
    md.manufacturer = _trim(str(getattr(first_ds, "Manufacturer", "") or ""), MAX_MANUFACTURER_LEN)
    md.manufacturer_model_name = _trim(
        str(getattr(first_ds, "ManufacturerModelName", "") or ""), MAX_MODEL_LEN
    )
    md.patient_sex = _parse_sex(str(getattr(first_ds, "PatientSex", "") or ""))

    age_raw = str(getattr(first_ds, "PatientAge", "") or "")
    md.patient_age_bucket = _parse_age_bucket(age_raw)
    if md.patient_age_bucket is None:
        # Fallback per FR-META-2 — derive from PatientBirthDate + StudyDate.
        md.patient_age_bucket = _parse_birthdate_age(
            str(getattr(first_ds, "PatientBirthDate", "") or ""),
            str(getattr(first_ds, "StudyDate", "") or ""),
        )

    md.study_date_shifted = _parse_study_date(str(getattr(first_ds, "StudyDate", "") or ""))
    md.study_year = md.study_date_shifted.year if md.study_date_shifted else None

    # CT/MR-only physics fields.
    if first_modality in ("CT", "MR"):
        md.slice_thickness_mm = _parse_float(getattr(first_ds, "SliceThickness", None))
    if first_modality == "CT":
        md.kvp = _parse_float(getattr(first_ds, "KVP", None))

    return md
