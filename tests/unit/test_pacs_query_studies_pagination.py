"""Unit tests for :meth:`DicomWebPacsClient.query_studies` auto-pagination.

Regression pin: Orthanc caps an unbounded QIDO ``/studies`` response at 100
rows. Before the pagination loop was added the gateway's ``sync-once`` only
processed the first 100 studies of a 255-study source. These tests lock in
the walk-until-empty contract, the dedupe behaviour at page boundaries, and
the ``max_pages`` safety guard.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

import httpx
import pytest

from radivault_gateway.pacs import DicomWebPacsClient, PacsError


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> DicomWebPacsClient:
    client = DicomWebPacsClient(
        "http://pacs.example/dicom-web",
        auth_type="bearer",
        token="tok",
        max_retries=3,
        retry_initial=0.0,
        retry_factor=1.0,
        retry_cap=0.0,
    )
    client._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Accept": "application/dicom+json", "Authorization": "Bearer tok"},
    )
    return client


def _row(study_uid: str) -> dict[str, Any]:
    return {
        "0020000D": {"vr": "UI", "Value": [study_uid]},
        "00080061": {"vr": "CS", "Value": ["CT"]},
        "00100020": {"vr": "LO", "Value": ["P-1"]},
        "00080020": {"vr": "DA", "Value": ["20240101"]},
        "00201208": {"vr": "IS", "Value": [10]},
    }


# ---------------------------------------------------------------------------
# 1. Three pages: 500 (full) + 500 (full) + 0 (empty) → terminate on empty
# page. Exercises the "empty-body ⇒ stop" branch.
# ---------------------------------------------------------------------------


def test_query_studies_walks_until_empty_page():
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append(params)
        offset = int(params["offset"])
        if offset == 0:
            rows = [_row(f"1.2.840.p1.{i}") for i in range(500)]
        elif offset == 500:
            rows = [_row(f"1.2.840.p2.{i}") for i in range(500)]
        elif offset == 1000:
            rows = []
        else:
            raise AssertionError(f"unexpected offset {offset}")
        return httpx.Response(200, json=rows)

    client = _make_client(handler)
    try:
        result = client.query_studies(date(2024, 1, 1), date(2024, 12, 31))
    finally:
        client.close()

    # Three HTTP calls: two full pages force a probe, third page is empty.
    assert len(calls) == 3
    assert [c["offset"] for c in calls] == ["0", "500", "1000"]
    assert all(c["limit"] == "500" for c in calls)
    assert len(result) == 1000
    # Unique UIDs, in first-seen order preserved.
    assert result[0].study_instance_uid == "1.2.840.p1.0"
    assert result[499].study_instance_uid == "1.2.840.p1.499"
    assert result[500].study_instance_uid == "1.2.840.p2.0"
    assert result[-1].study_instance_uid == "1.2.840.p2.499"


# ---------------------------------------------------------------------------
# 2. Two pages: 500 + 250 (partial page short-circuits the extra round-trip).
# ---------------------------------------------------------------------------


def test_query_studies_partial_page_terminates_without_extra_call():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(dict(request.url.params)["offset"])
        calls.append(offset)
        if offset == 0:
            rows = [_row(f"1.2.840.q1.{i}") for i in range(500)]
        elif offset == 500:
            rows = [_row(f"1.2.840.q2.{i}") for i in range(250)]
        else:
            raise AssertionError(f"unexpected offset {offset}")
        return httpx.Response(200, json=rows)

    client = _make_client(handler)
    try:
        result = client.query_studies(date(2024, 1, 1), date(2024, 12, 31))
    finally:
        client.close()

    # Exactly 2 HTTP calls — partial page (<limit) signalled end of results.
    assert calls == [0, 500]
    assert len(result) == 750


# ---------------------------------------------------------------------------
# 3. First page empty → 1 call, empty list.
# ---------------------------------------------------------------------------


def test_query_studies_empty_first_page_returns_empty_list():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(int(dict(request.url.params)["offset"]))
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    try:
        result = client.query_studies(date(2024, 1, 1), date(2024, 12, 31))
    finally:
        client.close()

    assert calls == [0]
    assert result == []


# ---------------------------------------------------------------------------
# 4. Duplicate UID across page boundary → dedupe to N-1, first-seen order kept.
# ---------------------------------------------------------------------------


def test_query_studies_dedupes_duplicate_uids_across_page_boundary():
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(dict(request.url.params)["offset"])
        if offset == 0:
            # Last row of page 1 has UID "dup".
            rows = [_row(f"1.2.840.d.{i}") for i in range(499)] + [_row("1.2.840.dup")]
        elif offset == 500:
            # First row of page 2 is the same "dup" UID → should be deduped.
            rows = [_row("1.2.840.dup")] + [_row(f"1.2.840.e.{i}") for i in range(199)]
        else:
            raise AssertionError(f"unexpected offset {offset}")
        return httpx.Response(200, json=rows)

    client = _make_client(handler)
    try:
        result = client.query_studies(date(2024, 1, 1), date(2024, 12, 31))
    finally:
        client.close()

    # 500 (page 1) + 200 (page 2) - 1 duplicate = 699 unique rows.
    assert len(result) == 699
    uids = [r.study_instance_uid for r in result]
    # "dup" appears exactly once, at its first-seen position (tail of page 1).
    assert uids.count("1.2.840.dup") == 1
    assert uids.index("1.2.840.dup") == 499
    # Subsequent rows come from page 2 (no second "dup" re-insertion).
    assert uids[500] == "1.2.840.e.0"


# ---------------------------------------------------------------------------
# 5. max_pages guard → PacsError once the cap is hit.
# ---------------------------------------------------------------------------


def test_query_studies_max_pages_guard_raises():
    """A PACS that keeps echoing full pages must be bounded."""

    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        # Always return a *full* page so the loop never terminates naturally.
        rows = [_row(f"1.2.840.loop.{call_count['n']}.{i}") for i in range(500)]
        return httpx.Response(200, json=rows)

    client = _make_client(handler)
    try:
        with pytest.raises(PacsError, match="QIDO pagination exceeded max_pages"):
            client.query_studies(date(2024, 1, 1), date(2024, 12, 31))
    finally:
        client.close()

    # Exactly _QIDO_MAX_PAGES pages fetched before the guard fires.
    assert call_count["n"] == DicomWebPacsClient._QIDO_MAX_PAGES


# ---------------------------------------------------------------------------
# 6. Mid-pagination transient 500 → retries succeed; terminal 500 → PacsError.
# ---------------------------------------------------------------------------


def test_query_studies_mid_page_retry_recovers_then_terminates():
    state = {"offset0_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(dict(request.url.params)["offset"])
        if offset == 0:
            state["offset0_calls"] += 1
            if state["offset0_calls"] == 1:
                # First attempt fails transiently — retry logic must kick in.
                return httpx.Response(503, text="busy")
            return httpx.Response(200, json=[_row(f"1.2.840.r.{i}") for i in range(500)])
        if offset == 500:
            return httpx.Response(200, json=[_row(f"1.2.840.s.{i}") for i in range(100)])
        raise AssertionError(f"unexpected offset {offset}")

    client = _make_client(handler)
    try:
        result = client.query_studies(date(2024, 1, 1), date(2024, 12, 31))
    finally:
        client.close()

    # Page 1 needed 2 attempts (503 then 200); page 2 succeeded first try.
    assert state["offset0_calls"] == 2
    assert len(result) == 600


def test_query_studies_mid_page_terminal_failure_raises_pacserror():
    """When retries are exhausted mid-pagination the error must propagate."""

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(dict(request.url.params)["offset"])
        if offset == 0:
            return httpx.Response(200, json=[_row(f"1.2.840.t.{i}") for i in range(500)])
        # Second page always 503 → exhaust retries.
        return httpx.Response(503, text="down")

    client = _make_client(handler)
    try:
        with pytest.raises(PacsError):
            client.query_studies(date(2024, 1, 1), date(2024, 12, 31))
    finally:
        client.close()
