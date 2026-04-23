"""Medical exclusion regex matcher (dev-spec §4.4, FR-25/FR-26).

Matches ``StudyDescription`` against a configurable list of compiled regexes.
Matches cause defacing to be skipped and the study to be routed to the
v0.1 quarantine path with ``ERR_PIXEL_MEDICAL_EXCLUSION``. OCR redaction is
still attempted on these studies (burn-in text is orthogonal to facial ROI).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ExclusionMatch:
    matched: bool
    pattern: str | None = None
    category: str | None = None  # best-effort human label


class MedicalExclusionMatcher:
    """Compiles regex patterns once and exposes a ``matches()`` helper.

    Invalid patterns are rejected at construction time, not at match time —
    :class:`PixelDefacingConfig` already validates the regex strings so this
    check is defensive.
    """

    # Ordered longest-prefix-first so ``maxillofacial`` matches before the
    # generic ``facial`` hint (test_positive_matches relies on this).
    _CATEGORY_HINTS: tuple[tuple[str, str], ...] = (
        ("maxillofacial", "maxillofacial"),
        ("dental", "dental"),
        ("ent", "ent"),
        ("facial", "facial_trauma"),
        ("trauma", "facial_trauma"),
        ("sinus", "sinus"),
        ("orbit", "orbit"),
        ("ophthalm", "ophthalm"),
    )

    def __init__(self, patterns: Iterable[str]) -> None:
        self._compiled: list[tuple[str, re.Pattern[str]]] = []
        for raw in patterns:
            if not isinstance(raw, str) or not raw.strip():
                continue
            self._compiled.append((raw, re.compile(raw)))

    def matches(self, description: str | None) -> ExclusionMatch:
        if not description:
            return ExclusionMatch(matched=False)
        for raw, pat in self._compiled:
            if pat.search(description):
                return ExclusionMatch(
                    matched=True,
                    pattern=raw,
                    category=self._category_for(raw),
                )
        return ExclusionMatch(matched=False)

    def _category_for(self, pattern: str) -> str:
        lowered = pattern.lower()
        for hint, category in self._CATEGORY_HINTS:
            if hint in lowered:
                return category
        return "custom"
