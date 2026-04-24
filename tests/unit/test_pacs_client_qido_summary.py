"""Unit tests for :meth:`DicomWebPacsClient.fetch_study_qido_summary`.

gateway-flow-a-qido: Flow A's fast-path talks to QIDO-RS instead of WADO
metadata. This module pins the HTTP contract (path, ``Accept`` header),
the JSON-VR parsing (including the defensive null/missing-Value cases that
real Orthanc builds have emitted), and the "study not found" failure mode.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from radivault_gateway.pacs import DicomWebPacsClient, PacsError
from radivault_gateway.pacs.client import StudyQidoSummary


def _make_client(handler) -> DicomWebPacsClient:
    client = DicomWebPacsClient(
        "http://pacs.example/dicom-web",
        auth_type="bearer",
        token="tok",
        max_retries=1,
        retry_initial=0.0,
        retry_factor=1.0,
        retry_cap=0.0,
    )
    client._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Accept": "application/dicom+json", "Authorization": "Bearer tok"},
    )
    return client


def _qido_row(
    *,
    study_uid: str = "1.2.840.sample.1",
    modalities: list[str] | None = ("CT",),
    n_instances: int | None = 192,
    n_series: int | None = 3,
    study_date: str | None = "20240101",
) -> dict[str, Any]:
    """DICOMweb JSON VR form of a QIDO ``/studies`` row."""
    row: dict[str, Any] = {"0020000D": {"vr": "UI", "Value": [study_uid]}}
    if modalities is not None:
        row["00080061"] = {"vr": "CS", "Value": list(modalities)}
    if n_instances is not None:
        row["00201208"] = {"vr": "IS", "Value": [n_instances]}
    if n_series is not None:
        row["00201206"] = {"vr": "IS", "Value": [n_series]}
    if study_date is not None:
        row["00080020"] = {"vr": "DA", "Value": [study_date]}
    return row


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_fetch_study_qido_summary_parses_all_fields():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=[_qido_row(study_uid="1.2.840.q.1")])

    client = _make_client(handler)
    try:
        result = client.fetch_study_qido_summary("1.2.840.q.1")
    finally:
        client.close()

    assert isinstance(result, StudyQidoSummary)
    assert result.study_instance_uid == "1.2.840.q.1"
    assert result.modalities == ["CT"]
    assert result.n_instances == 192
    assert result.n_series == 3
    assert result.study_date == "20240101"
    # Fast-path latency tracked for audit parity with Flow B fetch_ms.
    assert result.duration_ms >= 0
    # URL must hit /studies with the UID as a query parameter — not
    # /studies/{uid}/metadata which is the slow WADO call Flow A replaces.
    assert captured["url"].startswith("http://pacs.example/dicom-web/studies")
    assert "/metadata" not in captured["url"]
    assert captured["params"]["StudyInstanceUID"] == "1.2.840.q.1"


# ---------------------------------------------------------------------------
# Defensive parsing — missing / null Value fields
# ---------------------------------------------------------------------------


def test_fetch_study_qido_summary_defaults_when_modalities_block_missing():
    """Some mini DICOMweb servers (notably dcm4chee in minimal profile) omit
    the ``00080061`` block entirely. We default to an empty modalities list
    rather than raising, so the Flow A manifest stays well-formed."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_qido_row(modalities=None)])

    client = _make_client(handler)
    try:
        result = client.fetch_study_qido_summary("1.2.840.noplans.1")
    finally:
        client.close()
    assert result.modalities == []
    assert result.n_instances == 192  # unaffected by the missing block


def test_fetch_study_qido_summary_defaults_when_value_array_null():
    """Orthanc has emitted ``{"vr":"CS","Value":null}`` on some builds. The
    summary helper treats it as empty, not as a parse error."""

    def handler(request: httpx.Request) -> httpx.Response:
        row = _qido_row()
        row["00080061"] = {"vr": "CS", "Value": None}  # type: ignore[assignment]
        row["00201208"] = {"vr": "IS", "Value": None}  # type: ignore[assignment]
        return httpx.Response(200, json=[row])

    client = _make_client(handler)
    try:
        result = client.fetch_study_qido_summary("1.2.840.null.1")
    finally:
        client.close()
    assert result.modalities == []
    assert result.n_instances == 0


def test_fetch_study_qido_summary_defaults_when_value_array_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        row = _qido_row(modalities=[], n_instances=None)
        row["00201208"] = {"vr": "IS", "Value": []}
        return httpx.Response(200, json=[row])

    client = _make_client(handler)
    try:
        result = client.fetch_study_qido_summary("1.2.840.empty.1")
    finally:
        client.close()
    assert result.modalities == []
    assert result.n_instances == 0
    assert result.n_series == 3  # other fields still parse


def test_fetch_study_qido_summary_survives_non_integer_instance_count():
    """The VR=IS spec says integer strings; a misbehaving PACS that sends a
    non-numeric value should not crash the sync loop — we fall back to 0
    and let the Hospital Portal render ``—``."""

    def handler(request: httpx.Request) -> httpx.Response:
        row = _qido_row()
        row["00201208"] = {"vr": "IS", "Value": ["NOT_A_NUMBER"]}
        return httpx.Response(200, json=[row])

    client = _make_client(handler)
    try:
        result = client.fetch_study_qido_summary("1.2.840.weird.1")
    finally:
        client.close()
    assert result.n_instances == 0


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_fetch_study_qido_summary_empty_array_raises_study_not_found():
    """QIDO returns an empty JSON array when no study matches. That is the
    only ambiguous signal — Orthanc does not 404 on unknown UIDs — so we
    must treat an empty body as ``study not found``."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    try:
        with pytest.raises(PacsError) as exc:
            client.fetch_study_qido_summary("1.2.840.missing.1")
    finally:
        client.close()
    assert "study not found" in str(exc.value)


def test_fetch_study_qido_summary_204_raises_study_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = _make_client(handler)
    try:
        with pytest.raises(PacsError) as exc:
            client.fetch_study_qido_summary("1.2.840.nocontent.1")
    finally:
        client.close()
    assert "study not found" in str(exc.value)


def test_fetch_study_qido_summary_http_error_raises_pacserror():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    client = _make_client(handler)
    try:
        with pytest.raises(PacsError) as exc:
            client.fetch_study_qido_summary("1.2.840.forbidden.1")
    finally:
        client.close()
    assert exc.value.status_code == 403


def test_fetch_study_qido_summary_non_array_body_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "an array"})

    client = _make_client(handler)
    try:
        with pytest.raises(PacsError) as exc:
            client.fetch_study_qido_summary("1.2.840.weird.1")
    finally:
        client.close()
    assert "study not found" in str(exc.value)


def test_fetch_study_qido_summary_non_json_body_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"<html>error</html>", headers={"content-type": "text/html"}
        )

    client = _make_client(handler)
    try:
        with pytest.raises(PacsError) as exc:
            client.fetch_study_qido_summary("1.2.840.html.1")
    finally:
        client.close()
    assert "non-JSON" in str(exc.value)
