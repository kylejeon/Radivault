"""Flow A method code resolver (gateway-flow-a-qido).

Flow A (metadata-only) sends identifier-level pseudonymization only; pixel
de-identification is deferred to Flow B. The method code sequence emitted
here is a static ruleset-scoped declaration, not a per-instance derivation —
Flow A never touches instance tags (the pipeline's QIDO fast-path skips
the WADO metadata pull and the de-id engine entirely), so the codes are
committed at ruleset-definition time.

Ruleset extensions are registered in :data:`FLOW_A_METHOD_CODES_BY_RULESET`
and cross-referenced in ``docs/specs/dev-spec-gateway-agent.md`` §11 (the
DICOM PS3.16 CID 7050 mapping table).
"""

from __future__ import annotations

FLOW_A_METHOD_CODES_BY_RULESET: dict[str, list[str]] = {
    # v0.1.0: DICOM PS3.15 Annex E Basic Application Confidentiality Profile.
    # The Flow A manifest declares identifier-level de-id via method code
    # 113100; pixel-level de-id (codes 113101..) is a Flow B concern because
    # the pixel payload never leaves the Gateway in Flow A.
    "v0.1.0": ["113100"],
}


def resolve_flow_a_method_codes(ruleset_version: str) -> list[str]:
    """Return a fresh copy of the method code sequence for ``ruleset_version``.

    Raises :class:`ValueError` with a bilingual hint when the ruleset has no
    registered mapping — this forces planners to extend the table alongside
    every new ruleset version rather than silently shipping an empty
    ``method_code_sequence`` that Central would later reject at validation.
    """
    try:
        return list(FLOW_A_METHOD_CODES_BY_RULESET[ruleset_version])
    except KeyError as exc:
        raise ValueError(
            f"no Flow A method code mapping for ruleset_version={ruleset_version!r}"
        ) from exc
