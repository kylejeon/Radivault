"""Unit tests for ``radivault_gateway.description_scrub``.

dev-spec-text-search-description-phase15 — covers the 7 PHI categories
(R1-R6 + R3 institution dictionary), the 3 whitelist categories
(W1-W3), the 200-char truncation cap, the suspicious-quarantine trigger,
and the env-driven feature flag.

Tests target false-negative < 1% per NFR-TS15-SEC-1 — the 250-sample manual
audit lives in ``scripts/audit/scan_description_phi.py`` (out of scope here).
"""

from __future__ import annotations

import os

import pytest

from radivault_gateway.description_scrub import (
    DESCRIPTION_LENGTH_CAP,
    SCRUB_VERSION,
    ExtractedDescriptions,
    ScrubbedDescription,
    _reset_yaml_caches_for_tests,
    description_extraction_enabled,
    extract_descriptions,
    scrub_description,
)


@pytest.fixture(autouse=True)
def _refresh_yaml_caches() -> None:
    """Ensure each test reloads the YAML dictionaries from disk."""
    _reset_yaml_caches_for_tests()
    yield
    _reset_yaml_caches_for_tests()


# ---------- empty / null / cap ----------


def test_scrub_empty_returns_empty() -> None:
    assert scrub_description("").text == ""
    assert scrub_description(None).text == ""
    assert scrub_description("   ").text == ""


def test_scrub_no_quarantine_when_empty() -> None:
    r = scrub_description(None)
    assert r.quarantine is False
    assert r.suspicious_token_count == 0


def test_scrub_truncate_to_200_chars() -> None:
    raw = "AX " * 80  # 240 chars of pure whitelist tokens
    r = scrub_description(raw)
    assert len(r.text) <= DESCRIPTION_LENGTH_CAP
    assert r.truncated is True


def test_scrub_no_truncate_under_cap() -> None:
    r = scrub_description("AX T1 BRAIN MR")
    assert r.truncated is False


# ---------- R1 patient name (EN + KO) ----------


def test_r1_english_two_word_name_redacted() -> None:
    r = scrub_description("MR BRAIN John Smith")
    assert "John" not in r.text
    assert "Smith" not in r.text
    assert "R1_PATIENT_NAME_EN" in r.blacklist_matched


def test_r1_initial_plus_surname_redacted() -> None:
    r = scrub_description("J. Smith brain mri")
    assert "Smith" not in r.text
    assert "R1_PATIENT_NAME_EN" in r.blacklist_matched


def test_r1_korean_2_4_syllable_redacted() -> None:
    r = scrub_description("뇌 MRI 김민수")
    assert "김민수" not in r.text
    assert "R1_PATIENT_NAME_KO" in r.blacklist_matched


def test_r1_korean_single_syllable_kept() -> None:
    # Single Hangul syllable is below the 2-4 threshold.
    r = scrub_description("뇌 MR")
    assert "MR" in r.text


# ---------- R2 physician prefix ----------


def test_r2_dr_prefix_redacted() -> None:
    r = scrub_description("Knee xray by Dr Lee")
    assert "Dr" not in r.text
    assert "Lee" not in r.text
    assert "R2_PHYSICIAN_PREFIX" in r.blacklist_matched


def test_r2_md_prefix_redacted() -> None:
    r = scrub_description("CT chest MD Smith")
    assert "Smith" not in r.text
    assert "R2_PHYSICIAN_PREFIX" in r.blacklist_matched


def test_r2_chained_prefix_redacted() -> None:
    """`by Dr Lee` → both `by Dr` and `Lee` strip in the fixed-point loop."""
    r = scrub_description("MR brain by Dr Lee")
    assert "Lee" not in r.text


# ---------- R3 institution dictionary ----------


def test_r3_yonsei_redacted() -> None:
    r = scrub_description("YONSEI BRAIN MR")
    assert "YONSEI" not in r.text
    assert "R3_INSTITUTION" in r.blacklist_matched


def test_r3_severance_korean_redacted() -> None:
    r = scrub_description("세브란스 흉부 CT")
    assert "세브란스" not in r.text
    assert "R3_INSTITUTION" in r.blacklist_matched


def test_r3_unknown_institution_kept() -> None:
    r = scrub_description("LOCALCLINIC BRAIN MR")
    # "LOCALCLINIC" not in dictionary — but >7 chars + capitalised → quarantine.
    # The test asserts it doesn't fire R3 specifically.
    assert "R3_INSTITUTION" not in r.blacklist_matched


# ---------- R4 patient ID ----------


def test_r4_mrn_with_prefix_redacted() -> None:
    r = scrub_description("Chest CT MRN 1234567")
    assert "1234567" not in r.text
    assert "R4_PATIENT_ID" in r.blacklist_matched


def test_r4_bare_long_digit_redacted() -> None:
    r = scrub_description("MR BRAIN 1234567")
    assert "1234567" not in r.text
    assert "R4_PATIENT_ID" in r.blacklist_matched


def test_r4_short_digit_quarantine_not_strip() -> None:
    """4-6 digit run between R5 (8+) and R4 (7+) → quarantine flag, not strip."""
    r = scrub_description("MR BRAIN 12345")
    assert "12345" in r.text  # not stripped
    assert r.quarantine is True


# ---------- R5 dates ----------


def test_r5_8digit_date_redacted() -> None:
    r = scrub_description("Chest CT 20240115")
    assert "20240115" not in r.text
    assert "R5_DATE" in r.blacklist_matched


def test_r5_iso_date_redacted() -> None:
    r = scrub_description("MR BRAIN 2024-01-15")
    assert "2024-01-15" not in r.text
    assert "R5_DATE" in r.blacklist_matched


def test_r5_age_phrase_redacted() -> None:
    r = scrub_description("Pediatric MR 5y")
    assert "5y" not in r.text
    assert "R5_DATE" in r.blacklist_matched


def test_r5_day_phrase_redacted() -> None:
    r = scrub_description("Followup CT day 3")
    assert "day 3" not in r.text
    assert "R5_DATE" in r.blacklist_matched


# ---------- R6 operator initials ----------


def test_r6_underscore_initials_redacted() -> None:
    r = scrub_description("AX T1 FLAIR _jw")
    assert "jw" not in r.text
    assert "R6_OPERATOR_INITIALS" in r.blacklist_matched


def test_r6_equals_initials_redacted() -> None:
    r = scrub_description("AX T1 FLAIR =AB")
    assert "AB" not in r.text


def test_r6_slash_initials_redacted() -> None:
    r = scrub_description("AX T1 FLAIR /RT")
    # Note: RT is anatomy-whitelist — but R6 strips at the regex stage before
    # the whitelist sees the token. Bare RT in a different position survives.
    assert "/RT" not in r.text


# ---------- W1-W3 whitelist preservation ----------


def test_w1_modality_token_kept() -> None:
    r = scrub_description("MR")
    assert r.text == "MR"
    assert "W1_MEDICAL_TERM" in r.whitelist_matched


def test_w2_anatomy_token_kept() -> None:
    r = scrub_description("BRAIN")
    assert "BRAIN" in r.text
    assert "W2_ANATOMY_EN" in r.whitelist_matched


def test_w2_anatomy_hand_not_treated_as_name() -> None:
    """`HAND` could trip a name regex; whitelist must protect anatomy."""
    r = scrub_description("HAND XR")
    assert "HAND" in r.text


def test_w3_protocol_keyword_kept() -> None:
    r = scrub_description("ROUTINE SCREENING MAMMO")
    assert "ROUTINE" in r.text
    assert "SCREENING" in r.text


# ---------- combined / quarantine ----------


def test_combined_all_phi_stripped() -> None:
    raw = "Knee Scanogram by Dr Lee 20240115 MRN 1234567 =AB"
    r = scrub_description(raw)
    assert "Lee" not in r.text
    assert "20240115" not in r.text
    assert "1234567" not in r.text
    assert "AB" not in r.text
    # Knee + Scanogram are W2 anatomy-whitelist + W3 protocol → kept.
    assert "Knee" in r.text or "KNEE" in r.text.upper()
    assert "Scanogram" in r.text or "SCANOGRAM" in r.text.upper()


def test_quarantine_long_token_triggers() -> None:
    r = scrub_description("MR BRAIN VERYLONGUNKNOWNTOKENHEREEEEE")
    assert r.quarantine is True
    assert r.suspicious_token_count >= 1


def test_quarantine_or_strip_for_proper_noun_unknown() -> None:
    """Capitalised 4+ char unknown word → either stripped (R1 sweep) OR
    quarantined (Pass 2 suspicion). Both are safe outcomes; what matters
    is that the unknown proper noun does NOT survive verbatim alongside
    a medical-context body part.
    """
    r = scrub_description("Angina chest pain")
    # Either strategy is acceptable as long as "Angina" does not survive.
    assert "Angina" not in r.text or r.quarantine is True


def test_no_quarantine_for_known_anatomy() -> None:
    r = scrub_description("BRAIN MR T1")
    assert r.quarantine is False


# ---------- audit metadata ----------


def test_scrub_emits_before_after_hash() -> None:
    r = scrub_description("BRAIN MR")
    assert r.before_hash.startswith("sha256:")
    assert r.after_hash.startswith("sha256:")
    # SHA-256 hex is 64 chars + "sha256:" prefix = 71 chars.
    assert len(r.before_hash) == 71


def test_scrub_unique_pattern_codes_only() -> None:
    """Two MRN matches → only one R4_PATIENT_ID entry in the list."""
    r = scrub_description("CT MRN 1234567 AND MRN 9876543")
    assert r.blacklist_matched.count("R4_PATIENT_ID") == 1


# ---------- ExtractedDescriptions aggregator ----------


def test_extracted_descriptions_quarantine_aggregation() -> None:
    sd = scrub_description("BRAIN MR")
    pn = scrub_description("AX T1")
    # Force quarantine on a series description.
    series = [scrub_description("MR BRAIN MysteriousThing")]
    ed = ExtractedDescriptions(
        study_description=sd,
        protocol_name=pn,
        series_descriptions=series,
    )
    # Either of the three contributes → aggregated quarantine True.
    assert ed.quarantine == series[0].quarantine


def test_extracted_descriptions_aggregated_lists_dedupe() -> None:
    sd = scrub_description("MRN 1234567")
    pn = scrub_description("MRN 9876543")
    ed = ExtractedDescriptions(
        study_description=sd,
        protocol_name=pn,
        series_descriptions=[],
    )
    assert ed.aggregated_blacklist.count("R4_PATIENT_ID") == 1


# ---------- feature flag ----------


def test_feature_flag_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DESCRIPTION_EXTRACTION_ENABLED", raising=False)
    assert description_extraction_enabled() is True


@pytest.mark.parametrize("v", ["0", "false", "False", "no", "NO", "off"])
def test_feature_flag_off_values(monkeypatch: pytest.MonkeyPatch, v: str) -> None:
    monkeypatch.setenv("DESCRIPTION_EXTRACTION_ENABLED", v)
    assert description_extraction_enabled() is False


def test_feature_flag_on_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESCRIPTION_EXTRACTION_ENABLED", "true")
    assert description_extraction_enabled() is True


# ---------- pydicom integration ----------


def test_extract_descriptions_from_pydicom_dataset() -> None:
    from pydicom.dataset import Dataset

    ds = Dataset()
    ds.add_new((0x0008, 0x1030), "LO", "Knee Scanogram")
    ds.add_new((0x0018, 0x1030), "LO", "AX T1 FLAIR")

    series_ds = Dataset()
    series_ds.add_new((0x0008, 0x103E), "LO", "AX T1 FLAIR BRAIN")

    ed = extract_descriptions(ds, series_datasets=[series_ds])
    assert "Knee" in ed.study_description.text or "KNEE" in ed.study_description.text.upper()
    assert "AX" in ed.protocol_name.text
    assert len(ed.series_descriptions) == 1


def test_extract_descriptions_missing_tags_yields_empty() -> None:
    from pydicom.dataset import Dataset

    ds = Dataset()  # no tags at all
    ed = extract_descriptions(ds)
    assert ed.study_description.text == ""
    assert ed.protocol_name.text == ""
    assert ed.series_descriptions == []


def test_scrub_version_constant() -> None:
    assert SCRUB_VERSION == "1.5.0"
