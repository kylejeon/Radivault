"""PHI scrub for search-bar free-text queries (dev-spec-text-search-description FR-TS-10).

Buyers may accidentally (or, rarely, intentionally) type patient identifiers
into the search bar — names, MRNs, phone numbers, RRNs, emails. Phase 1.0
scrubs the audit copy with a fixed set of 7 regex patterns, keeping the
``raw_query`` intact for 30 days (PIPA §28-8 retention budget) but writing
``masked_query`` + ``phi_flagged_patterns`` immediately on insert.

Intentional design choices:

- **Over-redaction is allowed.** A Korean noun like "심장" might match
  ``KOREAN_NAME``; that is acceptable for Phase 1.0 because the masked copy
  is only used for long-term audit grouping and patient-safety statistics.
  Phase 2 will whitelist ``kcd_label_ko`` tokens.
- **No external services.** Pattern matching is a pure-python regex pass — no
  Presidio, no NLP. This keeps the audit insert hot path under 5 ms (NFR-TS-PERF-4).
- **Pattern names only.** ``phi_flagged_patterns`` records the *kind* of
  redaction ("KOREAN_NAME", "RRN", …) — never the raw value.
- **Order matters.** RRN is scanned before LONG_DIGIT so a 13-digit RRN does
  not get caught by the generic 7+-digit fallback.

Public API:
    scrub_query(raw: str) -> ScrubResult  # ``masked``, ``patterns``
    mask_query(raw: str) -> tuple[str, int]  # back-compat thin shim
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["ScrubResult", "scrub_query", "mask_query", "PATTERNS"]


# Pattern order matters — the first regex that matches a span owns it. RRN
# (13-digit Korean resident number, with or without hyphen) is checked
# before the generic LONG_DIGIT fallback so RRNs are tagged precisely.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # 6-digit + 7-digit Korean resident registration number (주민등록번호).
    ("RRN", re.compile(r"\b\d{6}-?\d{7}\b")),
    # MRN-like prefix + digits, e.g. ``MRN: 12345``, ``PT 9876``, ``ID:42``.
    ("MRN", re.compile(r"\b(?:MRN|PT|ID)[\s:]?\d{4,}\b", re.IGNORECASE)),
    # Korean mobile / landline. ``02-1234-5678`` or ``010-1234-5678``.
    ("PHONE", re.compile(r"\b0\d{1,2}-?\d{3,4}-?\d{4}\b")),
    # Email — narrow ASCII set; anchors keep it from eating ``brain@`` style
    # nonsense.
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    # Capitalised English name: ``Smith``, ``J. Smith``, ``Smith, J.``.
    # Avoids common medical leading words by requiring the second token to
    # also be capitalised (``brain MR`` will not match).
    (
        "ENGLISH_NAME",
        re.compile(
            r"\b[A-Z][a-z]+(?:[\s,.]+[A-Z]\.?)?(?:[\s,.]+[A-Z][a-z]+)\b"
        ),
    ),
    # Korean name: 2-4 contiguous Hangul syllables, bounded by whitespace,
    # comma, or string end. Over-matches medical Hangul tokens — see module
    # docstring for the Phase 2 whitelist mitigation plan.
    ("KOREAN_NAME", re.compile(r"[가-힣]{2,4}(?=[\s,]|$)")),
    # Catch-all: 7+ contiguous digits not already tagged. Picks up legacy
    # MRN-like numbers without a prefix.
    ("LONG_DIGIT", re.compile(r"\b\d{7,}\b")),
)


@dataclass(frozen=True)
class ScrubResult:
    masked: str
    patterns: list[str]

    @property
    def redaction_count(self) -> int:
        return len(self.patterns)


def scrub_query(raw: str | None) -> ScrubResult:
    """Apply ``PATTERNS`` in order and return the masked copy + flagged kinds.

    Parameters
    ----------
    raw:
        The buyer's verbatim search input. ``None`` and empty strings short-
        circuit to an empty :class:`ScrubResult`.

    Returns
    -------
    ScrubResult
        ``masked``   — input with each PHI span replaced by ``[REDACTED:KIND]``.
        ``patterns`` — *unique, in order of first occurrence* list of pattern
        names that fired. Used for audit metric tagging — never contains
        the raw matched value.
    """
    if not raw:
        return ScrubResult(masked="", patterns=[])

    masked = raw
    flagged: list[str] = []
    for name, regex in PATTERNS:
        # Use a callable replacement so re.sub still walks the original string
        # offsets (avoids re-matching inside our own ``[REDACTED:…]`` token).
        def _repl(_m: re.Match[str], _name: str = name) -> str:
            if _name not in flagged:
                flagged.append(_name)
            return f"[REDACTED:{_name}]"

        masked = regex.sub(_repl, masked)

    return ScrubResult(masked=masked, patterns=flagged)


def mask_query(raw: str | None) -> tuple[str, int]:
    """Thin back-compat shim returning ``(masked_query, redaction_count)``."""
    result = scrub_query(raw)
    return result.masked, result.redaction_count
