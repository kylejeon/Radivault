"""Regression test — D-3: Gateway must emit ``anonymization_flag`` in manifest.

Central Ingest v0.1 enforces a hard gate on this field (dev-spec FR-9/FR-39),
so Gateway v0.1 would otherwise fail to talk to Central in production. The
fix in ``radivault_gateway/upload/client.py`` adds the field with the only
value Central accepts.
"""

from __future__ import annotations

from pathlib import Path

from radivault_gateway.upload.client import UploadClient


def test_build_manifest_sets_fully_anonymized_flag(tmp_path: Path) -> None:
    f = tmp_path / "a.dcm"
    f.write_bytes(b"dummy")
    client = UploadClient("https://example", upload_token="t", max_retries=1)
    manifest = client.build_manifest(
        gateway_id="gw_x",
        hospital_id="hosp_x",
        pseudo_study_uid="2.25.1",
        modalities=["MR"],
        ruleset_version="v0.1.0",
        salt_version=1,
        method_codes=["113100"],
        dcm_files=[f],
    )
    assert manifest["anonymization_flag"] == "fully_anonymized"
    client.close()
