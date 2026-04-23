"""Triage evaluator tests (dev-spec §4.1, FR-1..FR-6)."""

from __future__ import annotations

from types import SimpleNamespace

from radivault_gateway.deid.pixel.triage import TriageDecision, triage_datasets


def _ds(**attrs) -> SimpleNamespace:
    ns = SimpleNamespace(**attrs)
    # Provide ``.get`` so triage can use it uniformly.
    ns.get = lambda name, default="": getattr(ns, name, default)  # type: ignore[attr-defined]
    return ns


def test_burned_in_yes_triggers_ocr_required():
    """AC-1: BurnedInAnnotation=YES → OCR_REQUIRED."""
    datasets = [_ds(BurnedInAnnotation="YES", Modality="CT")]
    r = triage_datasets(datasets, modality_allowlist=["SC", "US"])
    assert r.decision == TriageDecision.OCR_REQUIRED
    assert r.reason == "burn_in_tag"
    assert r.burned_in_seen is True


def test_modality_allowlist_triggers_ocr_required():
    """AC-2: Modality=US in allowlist → OCR_REQUIRED."""
    datasets = [_ds(BurnedInAnnotation="NO", Modality="US")]
    r = triage_datasets(datasets, modality_allowlist=["SC", "US", "OT"])
    assert r.decision == TriageDecision.OCR_REQUIRED
    assert r.reason == "modality_allowlist"
    assert r.burned_in_seen is False


def test_ct_no_burn_in_is_skip():
    """AC-3: Modality=CT + BurnedInAnnotation=NO → SKIP."""
    datasets = [_ds(BurnedInAnnotation="NO", Modality="CT")]
    r = triage_datasets(datasets, modality_allowlist=["US", "SC"])
    assert r.decision == TriageDecision.SKIP


def test_missing_tags_is_skip():
    datasets = [_ds()]
    r = triage_datasets(datasets, modality_allowlist=["US"])
    assert r.decision == TriageDecision.SKIP


def test_any_instance_with_burn_in_wins():
    """FR-2: at least one instance with BurnedInAnnotation=YES triggers OCR."""
    datasets = [
        _ds(BurnedInAnnotation="NO", Modality="MR"),
        _ds(BurnedInAnnotation="YES", Modality="MR"),
    ]
    r = triage_datasets(datasets, modality_allowlist=["SC"])
    assert r.decision == TriageDecision.OCR_REQUIRED
    assert r.reason == "burn_in_tag"


def test_triage_study_reads_dicom_files(make_synthetic_study):
    """Integration with pydicom: triage_study should read staged .dcm files."""
    from radivault_gateway.deid.pixel.triage import triage_study

    study = make_synthetic_study(burned_in="YES", modality="MR", n_instances=1)
    result = triage_study(study, modality_allowlist=["SC"])
    assert result.decision == TriageDecision.OCR_REQUIRED


def test_triage_allowlist_uppercased():
    """Allowlist matching is case-insensitive."""
    datasets = [_ds(Modality="us", BurnedInAnnotation="NO")]
    r = triage_datasets(datasets, modality_allowlist=["US"])
    assert r.decision == TriageDecision.OCR_REQUIRED
