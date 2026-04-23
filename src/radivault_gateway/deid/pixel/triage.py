"""Burn-in triage evaluator (dev-spec §4.1, FR-1..FR-6).

Inputs are the already-metadata-deided staged DICOMs. Returns one of three
decisions: ``OCR_REQUIRED`` / ``OCR_CONDITIONAL`` / ``SKIP``. The conditional
decision is reserved for the v0.2.1 heuristic fallback (edge density +
histogram bimodality, not implemented in v0.2).

The evaluator inspects tags only; no pixel decoding happens here so it is cheap
even for large studies.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


class TriageDecision(enum.StrEnum):
    OCR_REQUIRED = "OCR_REQUIRED"
    OCR_CONDITIONAL = "OCR_CONDITIONAL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class TriageResult:
    decision: TriageDecision
    reason: str  # 'burn_in_tag' | 'modality_allowlist' | 'neither' | etc.
    inspected_instances: int
    burned_in_seen: bool


def triage_datasets(
    datasets: Iterable[object],
    *,
    modality_allowlist: Iterable[str],
) -> TriageResult:
    """Pure triage using already-loaded pydicom Datasets.

    Preferred entry point for unit tests. Any object with ``get(attr, default)``
    semantics is accepted so tests can pass plain dicts or SimpleNamespace.
    """
    allow = {m.upper().strip() for m in modality_allowlist}
    burned_seen = False
    modalities: set[str] = set()
    n = 0
    for ds in datasets:
        n += 1
        burned = _get_field(ds, "BurnedInAnnotation", "").upper().strip()
        if burned == "YES":
            burned_seen = True
        modality = _get_field(ds, "Modality", "").upper().strip()
        if modality:
            modalities.add(modality)

    if burned_seen:
        return TriageResult(
            decision=TriageDecision.OCR_REQUIRED,
            reason="burn_in_tag",
            inspected_instances=n,
            burned_in_seen=True,
        )
    if modalities & allow:
        return TriageResult(
            decision=TriageDecision.OCR_REQUIRED,
            reason="modality_allowlist",
            inspected_instances=n,
            burned_in_seen=False,
        )
    return TriageResult(
        decision=TriageDecision.SKIP,
        reason="neither",
        inspected_instances=n,
        burned_in_seen=False,
    )


def triage_study(
    staged_dir: Path,
    *,
    modality_allowlist: Iterable[str],
) -> TriageResult:
    """File-based triage. Reads *.dcm files under ``staged_dir`` recursively.

    pydicom is imported lazily to keep this module import-safe even on hosts
    without the pixel extras installed.
    """
    import pydicom

    paths = sorted(Path(staged_dir).rglob("*.dcm"))
    datasets = []
    for p in paths:
        try:
            ds = pydicom.dcmread(p, stop_before_pixels=True, force=False)
        except Exception:
            continue
        datasets.append(ds)
    return triage_datasets(datasets, modality_allowlist=modality_allowlist)


def _get_field(ds: object, name: str, default: str) -> str:
    try:
        value = ds.get(name, default)  # type: ignore[attr-defined]
    except AttributeError:
        value = getattr(ds, name, default)
    if value is None:
        return default
    return str(value)
