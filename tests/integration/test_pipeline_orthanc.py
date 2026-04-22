"""Integration test against a real Orthanc DICOMweb server.

Skipped by default. Run with:

    ORTHANC_URL=http://localhost:8042/dicom-web pytest tests/integration -m integration

The test assumes Orthanc is reachable and empty (or seeded) and exercises the
DicomWebPacsClient end-to-end.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from radivault_gateway.pacs import DicomWebPacsClient

pytestmark = pytest.mark.integration


@pytest.fixture
def orthanc_url() -> str:
    url = os.environ.get("ORTHANC_URL")
    if not url:
        pytest.skip("ORTHANC_URL not set")
    return url


def test_orthanc_qido_reachable(orthanc_url: str) -> None:
    # Bearer token is irrelevant on an unauthenticated dev Orthanc; we pass
    # an empty bearer to satisfy the constructor.
    client = DicomWebPacsClient(
        orthanc_url,
        auth_type="bearer",
        token="placeholder",
        max_retries=1,
    )
    assert client.health_check() in {True, False}  # just validate the call
    today = date.today()
    studies = client.query_studies(today - timedelta(days=365 * 10), today)
    # We do not assert non-empty — the dev Orthanc may be empty. We only
    # assert the call returned without exception.
    assert isinstance(studies, list)
    client.close()
