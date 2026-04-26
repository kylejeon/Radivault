"""KCD-8 (Korean Standard Classification of Diseases) heuristic mapping.

dev-spec-buyer-search-v3 FR-V3-DATA-2.

Maps a (modality, body_part) tuple to a representative KCD-8 diagnosis code.
This is **heuristic only** — derived from public Korean health-statistics
distributions (HIRA top-diagnosis-by-procedure) so demo rows look clinically
plausible. v0.1.5 will replace this with a NLP-based StudyDescription mapping.

Both keys are normalised to uppercase before lookup. ``body_part`` may be
``None`` — we then fall back to a modality-only entry. Final fallback is
``Z00.0`` / "일반 의학적 검사" / "General medical examination".

The table is intentionally small (16 rules + default) to keep the demo
narrative defensible. Each entry references publicly available Korean
hospital outpatient claim distributions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KCDEntry:
    code: str
    label_ko: str
    label_en: str


# (modality, body_part_uppercase) → KCDEntry. Body parts use DICOM
# BodyPartExamined enumerated values (ABDOMEN/CHEST/HEAD/etc.).
_RULES: dict[tuple[str, str], KCDEntry] = {
    ("CT", "CHEST"): KCDEntry("I20.9", "협심증, 상세불명", "Angina pectoris, unspecified"),
    ("CT", "HEAD"): KCDEntry(
        "I63.9", "뇌경색, 상세불명", "Cerebral infarction, unspecified"
    ),
    ("CT", "ABDOMEN"): KCDEntry(
        "K85.9", "급성 췌장염, 상세불명", "Acute pancreatitis, unspecified"
    ),
    ("CT", "PELVIS"): KCDEntry("N20.0", "신장결석", "Calculus of kidney"),
    ("CT", "SPINE"): KCDEntry(
        "M51.9", "추간판 장애, 상세불명", "Intervertebral disc disorder, unspecified"
    ),
    ("CT", "NECK"): KCDEntry(
        "C73", "갑상선 악성 신생물", "Malignant neoplasm of thyroid gland"
    ),
    ("MR", "HEAD"): KCDEntry(
        "G45.9",
        "일과성 뇌허혈 발작, 상세불명",
        "Transient ischaemic attack, unspecified",
    ),
    ("MR", "BRAIN"): KCDEntry(
        "G45.9",
        "일과성 뇌허혈 발작, 상세불명",
        "Transient ischaemic attack, unspecified",
    ),
    ("MR", "CHEST"): KCDEntry(
        "I25.1", "죽상경화성 심장병", "Atherosclerotic heart disease"
    ),
    ("MR", "SPINE"): KCDEntry(
        "M51.9", "추간판 장애, 상세불명", "Intervertebral disc disorder, unspecified"
    ),
    ("MR", "KNEE"): KCDEntry(
        "M23.9", "무릎 내장, 상세불명", "Internal derangement of knee, unspecified"
    ),
    ("MG", "BREAST"): KCDEntry(
        "C50.9",
        "유방의 악성 신생물, 상세불명",
        "Malignant neoplasm of breast, unspecified",
    ),
    ("CR", "CHEST"): KCDEntry("J18.9", "폐렴, 상세불명", "Pneumonia, unspecified"),
    ("CR", "HAND"): KCDEntry(
        "S62.9", "손목 및 손의 골절", "Fracture of wrist and hand level"
    ),
    ("US", "ABDOMEN"): KCDEntry("K76.0", "지방간", "Fatty (change of) liver, NEC"),
    ("PT", "CHEST"): KCDEntry(
        "C34.9",
        "기관지 및 폐의 악성 신생물",
        "Malignant neoplasm of bronchus and lung",
    ),
}

DEFAULT_ENTRY = KCDEntry(
    "Z00.0", "일반 의학적 검사", "General medical examination"
)


def lookup_kcd(modality: str | None, body_part: str | None) -> KCDEntry:
    """Return KCDEntry for the (modality, body_part) pair.

    Falls back to ``DEFAULT_ENTRY`` (Z00.0) when no rule matches. ``modality``
    is required — passing ``None`` always yields the default. ``body_part``
    may be ``None``; only the modality-only fallback would apply, but the
    table currently has no modality-only entries so the result is always
    ``DEFAULT_ENTRY`` in that branch.
    """
    if not modality:
        return DEFAULT_ENTRY
    mod = modality.strip().upper()
    bp = (body_part or "").strip().upper()
    if not bp:
        return DEFAULT_ENTRY
    return _RULES.get((mod, bp), DEFAULT_ENTRY)


def all_rules() -> dict[tuple[str, str], KCDEntry]:
    """Read-only view of the rule table (for backfill scripts + tests)."""
    return dict(_RULES)


__all__ = ["KCDEntry", "DEFAULT_ENTRY", "lookup_kcd", "all_rules"]
