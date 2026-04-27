"""DICOM free-text description PHI scrub (text-search-description Phase 1.5).

dev-spec-text-search-description-phase15 §4.A FR-TS15-2 / FR-TS15-3 / FR-TS15-4.

Scrubs ``StudyDescription (0008,1030)``, ``SeriesDescription (0008,103E)``
and ``ProtocolName (0018,1030)`` against the 7-category blacklist regex set
+ 3-category whitelist YAML dictionary set described in the dev-spec PHI
matrix (§6.4).

Public API:
    extract_descriptions(ds) -> ExtractedDescriptions
    scrub_description(text) -> ScrubbedDescription
    SCRUB_VERSION

Compliance:
    - DICOM PS3.15 Annex E §E.3.5 (Clean Descriptors Option / DCM 113105)
      is the baseline; this module performs the additional whitelist-restore
      pass described as Step B in dev-spec FR-TS15-2.
    - PHI false-negative target < 1% (NFR-TS15-SEC-1) — measured by
      ``scripts/audit/scan_description_phi.py`` against the 250 sample
      manual audit.
    - Raw description NEVER persisted; only SHA-256 of before/after appears
      in the manifest's ``description_scrub_metadata`` block (FR-TS15-5,
      NFR-TS15-AUDIT-1).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

log = logging.getLogger("radivault_gateway.description_scrub")

# ---------------------------------------------------------------------------
# Constants

SCRUB_VERSION = "1.5.0"
"""Bump when blacklist patterns or whitelist YAML format changes — appears in
``description_scrub_metadata.scrub_version`` so audits can attribute a
particular scrub policy to a particular study."""

DESCRIPTION_LENGTH_CAP = 200
"""dev-spec FR-TS15-4 — varchar(200) cap. DICOM standard LO is 64 chars but
some PACS violate it; we defensively truncate."""

DICOM_TAG_STUDY_DESC = (0x0008, 0x1030)
DICOM_TAG_SERIES_DESC = (0x0008, 0x103E)
DICOM_TAG_PROTOCOL_NAME = (0x0018, 0x1030)


# ---------------------------------------------------------------------------
# Blacklist regex (R1-R6 from dev-spec §6.4)
#
# Order matters — patterns higher in the tuple have priority on overlapping
# spans. R5_DATE precedes R4_PATIENT_ID so an 8-digit date (20240115) is not
# attributed to LONG_DIGIT.

_BLACKLIST_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # R5_DATE — 8-digit yyyymmdd or ISO yyyy-mm-dd / yyyy/mm/dd or 'day N' /
    # '5y' / '12 yrs' age fragments. Listed first so 8-digit date does not
    # collide with R4_PATIENT_ID (>=7-digit catch-all).
    (
        "R5_DATE",
        re.compile(
            r"\b("
            r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"  # 2024-01-15 or 2024/01/15
            r"|\d{4}\d{2}\d{2}"              # 20240115
            r"|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}" # 1/15/2024
            r"|day[\s-]?\d+"                  # day 3 / day-3
            r"|\d{1,3}\s?(?:y|yr|yrs|years?)"  # 5y / 12 yrs
            r"|\d{1,3}\s?(?:m|mo|mos|month|months)" # 6 mo / 9 months
            r")\b",
            re.IGNORECASE,
        ),
    ),
    # R4_PATIENT_ID — explicit MRN/PT/ID prefix or bare 7+ digit run.
    (
        "R4_PATIENT_ID",
        re.compile(
            r"\b(?:MRN|PT|ID|CHART)[\s:#-]?\d{4,}\b|(?<!\d)\d{7,}(?!\d)",
            re.IGNORECASE,
        ),
    ),
    # R2_PHYSICIAN_PREFIX — Dr / by / MD / PhD / Prof + capitalised name.
    # Greedily consumes any chained physician-prefix tokens followed by the
    # final name word, so "by Dr Lee" matches in one pass instead of leaving
    # a "Lee" remnant after stripping "by Dr".
    (
        "R2_PHYSICIAN_PREFIX",
        re.compile(
            r"\b(?:(?:Dr\.?|by|MD|M\.D\.|PhD|Ph\.D\.|Prof\.?|Professor|Resident|RT)"
            r"(?:\.|,)?\s+){1,3}[A-Za-z]{2,}\b",
            re.IGNORECASE,
        ),
    ),
    # R6_OPERATOR_INITIALS — ``=AB``, ``_jw``, ``/RT`` style suffix
    # initials. Two-to-four letter run preceded by =/_/ or // and bounded.
    (
        "R6_OPERATOR_INITIALS",
        re.compile(r"[=_/]\s?[A-Za-z]{2,4}\b"),
    ),
    # R1_PATIENT_NAME_EN — capitalised English given/family name pattern.
    # Matches two-or-more capitalised words in a row (John Smith), a
    # capitalised word followed by an initial (Smith J / Smith J.), or an
    # initial followed by a capitalised word (J. Smith).
    #
    # Trade-off: also matches medical phrases like "Routine Screening" that
    # are not in the W3 whitelist. Pass-2 anatomy/protocol whitelist runs
    # AFTER this strip, so any anatomy token caught here is over-redacted —
    # acceptable in Phase 1.5 (Kyle decision).
    (
        "R1_PATIENT_NAME_EN",
        re.compile(
            r"\b[A-Z][a-z]{1,}(?:[\s,.]+[A-Z][a-z]+){1,3}\b"
            r"|\b[A-Z][a-z]+(?:[\s,.]+[A-Z]\.?){1,3}\b"
            r"|\b[A-Z]\.\s?[A-Z][a-z]+\b"
        ),
    ),
    # R1_PATIENT_NAME_KO — 2-4 contiguous Hangul syllables. Aggressive per
    # Kyle decision (over-redaction acceptable in Phase 1.5; whitelist
    # refinement deferred to Phase 2). Anatomy + diagnosis Hangul tokens
    # may legitimately match — accepted trade-off.
    (
        "R1_PATIENT_NAME_KO",
        re.compile(r"[가-힣]{2,4}(?=[\s,.]|$)"),
    ),
    # R3_INSTITUTION matched separately via YAML dictionary (see below).
)


# ---------------------------------------------------------------------------
# YAML dictionary loader (R3_INSTITUTION + W2_ANATOMY + W3_PROTOCOL_KEYWORD)

_DEFAULT_CONFIG_DIR = (
    Path(os.environ.get("RADIVAULT_PHI_CONFIG_DIR", "configs/phi"))
)


def _load_yaml_tokens(path: Path) -> set[str]:
    """Return a normalised set of tokens from a YAML dictionary file.

    Falls back to an empty set if the file is missing or malformed —
    extract_text.py logs a warning but does not block the gateway sync.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover — pyyaml is a runtime dep.
        log.warning("description_scrub_yaml_no_pyyaml path=%s", path)
        return set()

    if not path.exists():
        log.warning("description_scrub_yaml_missing path=%s", path)
        return set()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — defensive, never block ingest
        log.warning("description_scrub_yaml_parse_fail path=%s err=%s", path, exc)
        return set()

    if not isinstance(data, dict):
        return set()
    tokens = data.get("tokens") or []
    return {
        unicodedata.normalize("NFKC", str(t)).upper().strip()
        for t in tokens
        if t
    }


# Lazy module-level caches so the YAML files only deserialise once per
# process lifetime (gateway syncs hundreds of studies per cycle).
_INSTITUTION_TOKENS: set[str] | None = None
_ANATOMY_TOKENS: set[str] | None = None
_PROTOCOL_TOKENS: set[str] | None = None


def _institution_tokens() -> set[str]:
    global _INSTITUTION_TOKENS
    if _INSTITUTION_TOKENS is None:
        _INSTITUTION_TOKENS = _load_yaml_tokens(
            _DEFAULT_CONFIG_DIR / "institution_blacklist.yaml"
        )
    return _INSTITUTION_TOKENS


def _anatomy_tokens() -> set[str]:
    global _ANATOMY_TOKENS
    if _ANATOMY_TOKENS is None:
        _ANATOMY_TOKENS = _load_yaml_tokens(
            _DEFAULT_CONFIG_DIR / "anatomy_whitelist.yaml"
        )
    return _ANATOMY_TOKENS


def _protocol_tokens() -> set[str]:
    global _PROTOCOL_TOKENS
    if _PROTOCOL_TOKENS is None:
        _PROTOCOL_TOKENS = _load_yaml_tokens(
            _DEFAULT_CONFIG_DIR / "protocol_keyword_whitelist.yaml"
        )
    return _PROTOCOL_TOKENS


def _reset_yaml_caches_for_tests() -> None:
    """Test-only hook so unit tests can re-load YAML dicts after monkeypatching."""
    global _INSTITUTION_TOKENS, _ANATOMY_TOKENS, _PROTOCOL_TOKENS
    _INSTITUTION_TOKENS = None
    _ANATOMY_TOKENS = None
    _PROTOCOL_TOKENS = None


# ---------------------------------------------------------------------------
# W1_MEDICAL_TERM whitelist — small inline set, no YAML overhead.

_W1_MEDICAL_TERM = {
    "MR", "MRI", "CT", "US", "XR", "PT", "MG", "PET", "DX", "CR", "NM",
    "DR", "RF", "XA", "SR", "SEG", "PR",
}


# ---------------------------------------------------------------------------
# Scrub result types

@dataclass(frozen=True)
class ScrubbedDescription:
    """Result of scrubbing one description string.

    ``text`` is the post-scrub safe string (may be empty when all tokens were
    stripped). ``quarantine`` flips True when a suspicious unclassified token
    survived all whitelists — central will mark the parent study
    ``preview_status='phi_detected'`` (FR-TS15-10).
    """

    text: str
    blacklist_matched: list[str] = field(default_factory=list)
    whitelist_matched: list[str] = field(default_factory=list)
    quarantine: bool = False
    truncated: bool = False
    suspicious_token_count: int = 0
    before_hash: str = ""
    after_hash: str = ""


@dataclass(frozen=True)
class ExtractedDescriptions:
    """Per-study descriptions extracted + scrubbed by the gateway extractor.

    Attaches to manifest schema v2.1 (FR-TS15-5) — central writes
    ``study.study_description`` / ``study.protocol_name`` /
    ``series.series_description`` from these fields.
    """

    study_description: ScrubbedDescription
    protocol_name: ScrubbedDescription
    series_descriptions: list[ScrubbedDescription] = field(default_factory=list)

    @property
    def quarantine(self) -> bool:
        """True iff any of the 3 fields hit the quarantine trigger."""
        return (
            self.study_description.quarantine
            or self.protocol_name.quarantine
            or any(s.quarantine for s in self.series_descriptions)
        )

    @property
    def aggregated_blacklist(self) -> list[str]:
        seen: list[str] = []
        for r in (self.study_description, self.protocol_name, *self.series_descriptions):
            for code in r.blacklist_matched:
                if code not in seen:
                    seen.append(code)
        return seen

    @property
    def aggregated_whitelist(self) -> list[str]:
        seen: list[str] = []
        for r in (self.study_description, self.protocol_name, *self.series_descriptions):
            for code in r.whitelist_matched:
                if code not in seen:
                    seen.append(code)
        return seen

    @property
    def suspicious_token_count_total(self) -> int:
        return sum(
            r.suspicious_token_count
            for r in (
                self.study_description,
                self.protocol_name,
                *self.series_descriptions,
            )
        )


# ---------------------------------------------------------------------------
# Tokenisation helpers
#
# Tokens are word-runs of letters/digits, preserving original whitespace +
# punctuation in between for re-assembly.

_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")


def _classify_token(token: str) -> tuple[str, str | None]:
    """Classify a single token into (verdict, code).

    verdict ∈ ``{"keep", "strip", "quarantine"}``. Code is the matched
    R1-R6 / W1-W3 pattern name (None for "keep" without explicit whitelist).
    """
    norm = unicodedata.normalize("NFKC", token).upper()
    bare = norm.strip(".,;:!?()[]{}'\"")

    if not bare:
        return "keep", None

    # 1. Whitelist short-circuits — anatomy / protocol vocab survives even
    #    if it might trip a name regex (HAND, RT, etc.).
    if bare in _W1_MEDICAL_TERM:
        return "keep", "W1_MEDICAL_TERM"
    if bare in _anatomy_tokens():
        return "keep", "W2_ANATOMY_EN"
    if bare in _protocol_tokens():
        return "keep", "W3_PROTOCOL_KEYWORD"

    # 2. R3_INSTITUTION — YAML dictionary. Hangul institution tokens may
    #    appear as substrings inside a longer Hangul run; check both exact
    #    and substring containment.
    inst_set = _institution_tokens()
    if bare in inst_set:
        return "strip", "R3_INSTITUTION"
    for inst in inst_set:
        if inst and inst in bare:
            return "strip", "R3_INSTITUTION"

    # 3. Hangul-name R1_PATIENT_NAME_KO — applied to single-token Hangul
    #    runs of 2-4 syllables. Aggressive (Kyle decision); over-redaction
    #    of anatomy Hangul like 심장/폐 is acceptable in Phase 1.5.
    if 2 <= len(bare) <= 4 and all("가" <= c <= "힣" for c in bare):
        return "strip", "R1_PATIENT_NAME_KO"

    # 4. Pure-digit 4-6 → suspicious (R5_DATE handles 8+, R4 handles 7+
    #    with prefix).
    if token.isdigit() and 4 <= len(token) <= 6:
        return "quarantine", None

    # 5. Heuristic suspicion — long unknown tokens or mixed-case proper
    #    nouns. These trigger study-level quarantine.
    if _is_suspicious_unknown(token, bare):
        return "quarantine", None

    # 6. Unknown short token — keep (medical English free-text default).
    return "keep", None


def _is_suspicious_unknown(token: str, bare_upper: str) -> bool:
    """Heuristic: an unknown token that *looks* like PHI rather than vocab.

    - Length > 20 → suspicious (long names / IDs).
    - Mixed-case proper noun pattern (Capital + lowercase letters, length
      4+) → suspicious unless it's a numeric+letter mix.
    """
    if len(bare_upper) > 20:
        return True
    if (
        len(token) >= 4
        and token[0].isupper()
        and token[1:].isalpha()
        and token[1:].islower()
    ):
        # Single proper-noun capitalised word (Yonsei, Severance) that
        # didn't match institution YAML → still suspicious as a name-like
        # leftover. Only fires when token is 4+ chars to avoid common
        # words ("Pre", "Post").
        return True
    return False


# ---------------------------------------------------------------------------
# Public scrub entrypoint

def scrub_description(raw: str | None) -> ScrubbedDescription:
    """Scrub one description string, returning the safe text + audit metadata.

    Empty / None input returns an empty ``ScrubbedDescription`` (no
    quarantine — "no description provided" is not PHI).

    Two-pass strategy:
      Pass 1 — regex strip multi-token PHI patterns (R2 physician prefix,
        R4 patient-id with prefix, R5 dates, R6 operator initials, R1 EN
        name) over the entire string in one go. Each match is replaced
        with a single space, preserving adjacent token alignment.
      Pass 2 — token-level classification on what remains: anatomy /
        protocol whitelists, R3 institution dictionary, R1 KO names,
        and suspicious-unknown quarantine triggers.
    """
    if raw is None or not raw.strip():
        return ScrubbedDescription(text="")

    raw_text = raw
    before_hash = "sha256:" + hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    blacklist_hits: list[str] = []
    whitelist_hits: list[str] = []
    suspicious_count = 0

    # ----- Pass 1a: R3_INSTITUTION YAML strip (Hangul + ASCII tokens) -----
    # Must run BEFORE R1_PATIENT_NAME_KO regex so a 2-4 syllable Hangul
    # institution token like 세브란스 is attributed to R3 instead of being
    # over-redacted as R1.
    working = raw_text
    inst_tokens = _institution_tokens()
    if inst_tokens:
        # Sort by length desc so the longer match wins (서울대학교병원 before 서울대병원).
        sorted_inst = sorted(inst_tokens, key=lambda t: -len(t))
        for inst in sorted_inst:
            if not inst:
                continue
            if inst in working.upper():
                # Case-insensitive replace for ASCII; Hangul is case-invariant.
                pat = re.compile(re.escape(inst), re.IGNORECASE)
                new_working, n = pat.subn(" ", working)
                if n > 0:
                    working = new_working
                    if "R3_INSTITUTION" not in blacklist_hits:
                        blacklist_hits.append("R3_INSTITUTION")

    # ----- Pass 1b: regex strip across the whole string -----
    # Each pattern is applied repeatedly until quiescent, AND the entire
    # pattern set is run in an outer fixed-point loop so chained PHI like
    # "by Dr Lee" (R2 strips "by Dr", then a second sweep needs R1 to
    # catch the bare "Lee" remnant) is fully redacted before Pass 2 runs.
    #
    # Special-case for R1_PATIENT_NAME_EN: a capitalised-word-pair regex
    # match is NOT a name if every word in the match is in the W2 anatomy
    # or W3 protocol whitelist (e.g. "Knee Scanogram" is anatomy + protocol,
    # not a person name). The replacement callback checks this before
    # stripping.
    anatomy_set = _anatomy_tokens()
    protocol_set = _protocol_tokens()

    def _all_whitelisted(span: str) -> bool:
        words = re.findall(r"[A-Za-z]+", span)
        if not words:
            return False
        for w in words:
            up = w.upper()
            if (
                up in _W1_MEDICAL_TERM
                or up in anatomy_set
                or up in protocol_set
            ):
                continue
            return False
        return True

    for _outer in range(4):  # bounded outer fixed-point (descriptions are short).
        any_change = False
        for code, regex in _BLACKLIST_PATTERNS:
            def _repl(_m: re.Match[str], _code: str = code) -> str:
                span = _m.group(0)
                # Whitelist veto only applies to R1_PATIENT_NAME_EN —
                # other categories (R2, R4, R5, R6) have unambiguous
                # signatures (digits, prefixes, separators).
                if _code == "R1_PATIENT_NAME_EN" and _all_whitelisted(span):
                    return span  # not a name, leave intact
                if _code not in blacklist_hits:
                    blacklist_hits.append(_code)
                return " "

            for _ in range(8):
                new_working, n = regex.subn(_repl, working)
                if new_working == working:
                    break
                working = new_working
                any_change = True
        if not any_change:
            break

    # Single-token capitalised name remnants (e.g. "Lee" after "by Dr Lee"
    # was partly stripped) may survive the regex pass because R1 requires
    # ≥2 capitalised tokens. Sweep them now using an explicit single-token
    # check that scopes to ALL-Lower-after-Capital words 3-12 chars long
    # not in the whitelist dictionaries.
    def _strip_lone_capitalised_name(text: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            tok = m.group(0)
            up = tok.upper()
            if (
                up in _W1_MEDICAL_TERM
                or up in anatomy_set
                or up in protocol_set
            ):
                return tok
            if "R1_PATIENT_NAME_EN" not in blacklist_hits:
                blacklist_hits.append("R1_PATIENT_NAME_EN")
            return " "

        return re.sub(r"\b[A-Z][a-z]{2,11}\b", _repl, text)

    working = _strip_lone_capitalised_name(working)

    # ----- Pass 2: per-token classification on what's left -----
    out_parts: list[str] = []
    last_end = 0
    for m in _TOKEN_RE.finditer(working):
        # Preserve the inter-token text (whitespace / punctuation) verbatim.
        out_parts.append(working[last_end:m.start()])
        token = m.group()
        verdict, code = _classify_token(token)
        if verdict == "keep":
            out_parts.append(token)
            if code and code not in whitelist_hits:
                whitelist_hits.append(code)
        elif verdict == "strip":
            if code and code not in blacklist_hits:
                blacklist_hits.append(code)
            out_parts.append(" ")
        elif verdict == "quarantine":
            suspicious_count += 1
            # Token still kept *visually* (so quarantined-but-released
            # studies are reviewable) but study is flagged.
            out_parts.append(token)
        last_end = m.end()
    out_parts.append(working[last_end:])

    # Normalise whitespace.
    scrubbed = re.sub(r"\s+", " ", "".join(out_parts)).strip()

    truncated = False
    if len(scrubbed) > DESCRIPTION_LENGTH_CAP:
        scrubbed = scrubbed[:DESCRIPTION_LENGTH_CAP]
        truncated = True
        log.info(
            "description_truncated raw_len=%d cap=%d",
            len(raw_text),
            DESCRIPTION_LENGTH_CAP,
        )

    after_hash = "sha256:" + hashlib.sha256(scrubbed.encode("utf-8")).hexdigest()

    return ScrubbedDescription(
        text=scrubbed,
        blacklist_matched=blacklist_hits,
        whitelist_matched=whitelist_hits,
        quarantine=suspicious_count > 0,
        truncated=truncated,
        suspicious_token_count=suspicious_count,
        before_hash=before_hash,
        after_hash=after_hash,
    )


# ---------------------------------------------------------------------------
# Pydicom integration

def extract_descriptions(ds, *, series_datasets: Iterable | None = None) -> ExtractedDescriptions:
    """Extract + scrub the 3 description fields from a pydicom Dataset.

    Parameters
    ----------
    ds:
        The first parseable pydicom ``Dataset`` of the study (study-level
        tags such as StudyDescription / ProtocolName live here).
    series_datasets:
        Iterable of one pydicom Dataset *per series* — used to pull
        SeriesDescription. May be empty: callers that don't have per-series
        datasets convenient pass ``None``; in that case
        ``series_descriptions`` is empty.

    Returns
    -------
    ExtractedDescriptions
        All 3 fields, each post-scrub, with audit metadata for manifest
        attachment (FR-TS15-5).
    """
    raw_study = _read_str(ds, DICOM_TAG_STUDY_DESC)
    raw_protocol = _read_str(ds, DICOM_TAG_PROTOCOL_NAME)
    study_scrub = scrub_description(raw_study)
    protocol_scrub = scrub_description(raw_protocol)

    series_scrubs: list[ScrubbedDescription] = []
    if series_datasets:
        for series_ds in series_datasets:
            raw_series = _read_str(series_ds, DICOM_TAG_SERIES_DESC)
            series_scrubs.append(scrub_description(raw_series))

    return ExtractedDescriptions(
        study_description=study_scrub,
        protocol_name=protocol_scrub,
        series_descriptions=series_scrubs,
    )


def _read_str(ds, tag: tuple[int, int]) -> str:
    """Best-effort string read from a pydicom dataset by (group, elem) tag."""
    if ds is None:
        return ""
    try:
        if tag in ds:
            v = ds[tag].value
            if v is None:
                return ""
            return str(v)
    except Exception:  # pragma: no cover — defensive against odd VRs
        return ""
    return ""


# ---------------------------------------------------------------------------
# Feature flag

def description_extraction_enabled() -> bool:
    """FR-TS15-16 — env-driven kill switch.

    ``DESCRIPTION_EXTRACTION_ENABLED=false`` (case-insensitive) makes the
    gateway extractor skip description scrubbing altogether (returns empty
    fields), so a runtime issue can be rolled back in < 30s without
    redeploying. Default ``true``.
    """
    raw = os.environ.get("DESCRIPTION_EXTRACTION_ENABLED", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")
