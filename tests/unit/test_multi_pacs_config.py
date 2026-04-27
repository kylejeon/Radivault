"""Multi-PACS sync — config schema unit tests (FR-MPS-1, FR-MPS-6).

Covers the dev-spec ``docs/specs/dev-spec-multi-pacs-sync.md`` §13 step 1
contract:

- legacy single-dict ``pacs:`` parses unchanged → 1-element ``pacs_endpoints``
  with ``id="default"`` and ``cfg.pacs`` exposing the same fields as the
  legacy single-PACS config (regression guard for the union shape).
- list-form ``pacs:`` parses with explicit ``id``, optional
  ``hospital_id`` / ``priority`` / ``enabled`` fields. Priority sort is
  deterministic; disabled endpoints are excluded by ``enabled_endpoints``.
- ``central.upload_tokens: {hospital_id: token}`` resolves via
  ``token_for_hospital`` with legacy ``upload_token`` fallback.
- Validation errors: empty list, duplicate id, missing id in list form, no
  upload credential.
"""

from __future__ import annotations

# Importing ``radivault_gateway.deid`` first avoids a pre-existing circular
# import (deid.engine imports radivault_gateway.config which has not finished
# initialising during test_config.py collection). This was already the case
# before the multi-PACS work landed; documented here so future maintainers
# understand the unusual import.
import radivault_gateway.deid  # noqa: F401 — circular-import primer

import pytest
from pydantic import ValidationError

from radivault_gateway.config import GatewayConfig, PacsEndpointConfig


def _base() -> dict:
    return {
        "version": 1,
        "agent": {
            "gateway_id": "gw_test",
            "hospital_id": "HOSP-001",
            "org_root_oid": "2.25.140737488355328",
        },
        "deid": {"salt": "0123456789abcdef" * 2, "salt_version": 1},
        "staging": {"root": "/tmp/stg"},
        "state": {"db_path": "/tmp/state.sqlite3"},
        "audit": {"path": "/tmp/audit.log"},
        "central": {
            "base_url": "https://central.example",
            "upload_token": "tok-fallback",
        },
    }


# ----------------------------------------------------------------------------
# Legacy single-dict pacs (regression guard)
# ----------------------------------------------------------------------------


def test_legacy_single_pacs_dict_normalises_to_one_endpoint() -> None:
    data = _base()
    data["pacs"] = {
        "base_url": "https://pacs.example/dicom-web",
        "auth": {"type": "bearer", "token": "tok"},
    }
    cfg = GatewayConfig.model_validate(data)
    # Default id assignment.
    assert cfg.pacs.id == "default"
    assert cfg.pacs.priority == 100
    assert cfg.pacs.enabled is True
    assert cfg.pacs.hospital_id is None
    # pacs_endpoints mirrors the legacy entry.
    assert len(cfg.pacs_endpoints) == 1
    assert cfg.pacs_endpoints[0].id == "default"
    assert cfg.pacs_endpoints[0].base_url == "https://pacs.example/dicom-web"
    # Hospital fallback to agent.hospital_id (FR-MPS-4).
    assert cfg.hospital_id_for(cfg.pacs) == "HOSP-001"
    # ``enabled_endpoints`` returns the single endpoint.
    enabled = cfg.enabled_endpoints()
    assert len(enabled) == 1
    assert enabled[0].id == "default"


def test_legacy_dict_with_explicit_id_preserved() -> None:
    """Explicit id in legacy single-dict shape is honoured (not overwritten)."""
    data = _base()
    data["pacs"] = {
        "id": "primary",
        "base_url": "https://pacs.example/dicom-web",
        "auth": {"type": "bearer", "token": "tok"},
    }
    cfg = GatewayConfig.model_validate(data)
    assert cfg.pacs.id == "primary"
    assert cfg.pacs_endpoints[0].id == "primary"


# ----------------------------------------------------------------------------
# Multi-PACS list form
# ----------------------------------------------------------------------------


def test_multi_pacs_list_normalises_with_priority_sort() -> None:
    data = _base()
    data["pacs"] = [
        {
            "id": "orthanc-b",
            "base_url": "https://b.example/dicom-web",
            "auth": {"type": "bearer", "token": "t2"},
            "priority": 20,
            "hospital_id": "HOSP-002",
        },
        {
            "id": "orthanc-a",
            "base_url": "https://a.example/dicom-web",
            "auth": {"type": "bearer", "token": "t1"},
            "priority": 10,
        },
    ]
    cfg = GatewayConfig.model_validate(data)
    # Sorted by priority ascending.
    assert [e.id for e in cfg.pacs_endpoints] == ["orthanc-a", "orthanc-b"]
    # cfg.pacs is the first endpoint (legacy shape).
    assert cfg.pacs.id == "orthanc-a"
    assert cfg.pacs.base_url == "https://a.example/dicom-web"
    # Hospital resolution honours the per-endpoint override.
    assert cfg.hospital_id_for(cfg.pacs_endpoints[0]) == "HOSP-001"  # fallback
    assert cfg.hospital_id_for(cfg.pacs_endpoints[1]) == "HOSP-002"  # explicit


def test_disabled_endpoint_excluded_from_enabled_endpoints() -> None:
    data = _base()
    data["pacs"] = [
        {
            "id": "orthanc-a",
            "base_url": "https://a.example/dicom-web",
            "auth": {"type": "bearer", "token": "t1"},
            "priority": 10,
        },
        {
            "id": "orthanc-b",
            "base_url": "https://b.example/dicom-web",
            "auth": {"type": "bearer", "token": "t2"},
            "priority": 20,
            "enabled": False,
        },
    ]
    cfg = GatewayConfig.model_validate(data)
    assert len(cfg.pacs_endpoints) == 2  # both visible to ``--list-pacs``
    enabled = cfg.enabled_endpoints()
    assert [e.id for e in enabled] == ["orthanc-a"]


def test_normalisation_is_idempotent() -> None:
    """Running model_validate twice on the same data must produce equal output."""
    data = _base()
    data["pacs"] = [
        {
            "id": "p1",
            "base_url": "https://p1/dicom-web",
            "auth": {"type": "bearer", "token": "t1"},
        }
    ]
    cfg1 = GatewayConfig.model_validate(data)
    cfg2 = GatewayConfig.model_validate(data)
    assert cfg1.pacs_endpoints == cfg2.pacs_endpoints


# ----------------------------------------------------------------------------
# Validation errors
# ----------------------------------------------------------------------------


def test_empty_pacs_list_rejected() -> None:
    data = _base()
    data["pacs"] = []
    with pytest.raises(ValidationError) as exc:
        GatewayConfig.model_validate(data)
    assert "at least one endpoint required" in str(exc.value)


def test_duplicate_id_rejected() -> None:
    data = _base()
    data["pacs"] = [
        {
            "id": "dup",
            "base_url": "https://a/dicom-web",
            "auth": {"type": "bearer", "token": "t1"},
        },
        {
            "id": "dup",
            "base_url": "https://b/dicom-web",
            "auth": {"type": "bearer", "token": "t2"},
        },
    ]
    with pytest.raises(ValidationError) as exc:
        GatewayConfig.model_validate(data)
    assert "duplicated" in str(exc.value)


def test_missing_id_in_list_form_rejected() -> None:
    data = _base()
    data["pacs"] = [
        {
            "base_url": "https://a/dicom-web",
            "auth": {"type": "bearer", "token": "t1"},
        }
    ]
    with pytest.raises(ValidationError) as exc:
        GatewayConfig.model_validate(data)
    assert "'id' is required" in str(exc.value)


def test_invalid_id_format_rejected() -> None:
    """``id`` must match ``[a-z0-9_-]{1,32}``; uppercase forbidden."""
    data = _base()
    data["pacs"] = [
        {
            "id": "INVALID-CAPS",
            "base_url": "https://a/dicom-web",
            "auth": {"type": "bearer", "token": "t1"},
        }
    ]
    with pytest.raises(ValidationError):
        GatewayConfig.model_validate(data)


# ----------------------------------------------------------------------------
# Central upload_tokens / token_for_hospital (FR-MPS-6)
# ----------------------------------------------------------------------------


def test_upload_tokens_map_resolves_per_hospital() -> None:
    data = _base()
    data["pacs"] = {
        "base_url": "https://a/dicom-web",
        "auth": {"type": "bearer", "token": "t"},
    }
    data["central"] = {
        "base_url": "https://central.example",
        "upload_tokens": {"HOSP-001": "tok-1", "HOSP-002": "tok-2"},
    }
    cfg = GatewayConfig.model_validate(data)
    assert cfg.central.token_for_hospital("HOSP-001") == "tok-1"
    assert cfg.central.token_for_hospital("HOSP-002") == "tok-2"


def test_upload_tokens_falls_back_to_legacy_token_for_unknown_hospital() -> None:
    data = _base()
    data["pacs"] = {
        "base_url": "https://a/dicom-web",
        "auth": {"type": "bearer", "token": "t"},
    }
    data["central"] = {
        "base_url": "https://central.example",
        "upload_token": "fallback-token",
        "upload_tokens": {"HOSP-001": "tok-1"},
    }
    cfg = GatewayConfig.model_validate(data)
    assert cfg.central.token_for_hospital("HOSP-001") == "tok-1"
    # Unknown hospital → legacy fallback.
    assert cfg.central.token_for_hospital("HOSP-999") == "fallback-token"


def test_legacy_upload_token_resolves_for_any_hospital() -> None:
    """When only ``upload_token`` is set (no map), every hospital uses it."""
    data = _base()
    data["pacs"] = {
        "base_url": "https://a/dicom-web",
        "auth": {"type": "bearer", "token": "t"},
    }
    cfg = GatewayConfig.model_validate(data)
    assert cfg.central.token_for_hospital("HOSP-001") == "tok-fallback"
    assert cfg.central.token_for_hospital("HOSP-002") == "tok-fallback"


def test_no_upload_credential_rejected() -> None:
    data = _base()
    data["pacs"] = {
        "base_url": "https://a/dicom-web",
        "auth": {"type": "bearer", "token": "t"},
    }
    data["central"] = {"base_url": "https://central.example"}
    with pytest.raises(ValidationError) as exc:
        GatewayConfig.model_validate(data)
    assert "upload_token" in str(exc.value)


def test_token_for_hospital_keyerror_when_no_credential_at_all() -> None:
    """Bypassing ``model_validator`` with ``model_construct`` to verify the
    runtime ``KeyError`` path stays defensive in case future code disables
    the validator (e.g. a forced-construct path during config tests)."""
    from radivault_gateway.config.schema import CentralConfig

    cc = CentralConfig.model_construct(
        base_url="https://x", upload_token=None, upload_tokens=None
    )
    with pytest.raises(KeyError):
        cc.token_for_hospital("HOSP-001")


# ----------------------------------------------------------------------------
# Multi-PACS modality / lookback overrides per endpoint
# ----------------------------------------------------------------------------


def test_per_endpoint_query_modalities_independent() -> None:
    data = _base()
    data["pacs"] = [
        {
            "id": "ct-only",
            "base_url": "https://ct/dicom-web",
            "auth": {"type": "bearer", "token": "t1"},
            "query": {"modalities": ["CT"], "lookback_days": 30},
        },
        {
            "id": "mr-only",
            "base_url": "https://mr/dicom-web",
            "auth": {"type": "bearer", "token": "t2"},
            "query": {"modalities": ["MR"], "lookback_days": 7},
            "priority": 200,
        },
    ]
    cfg = GatewayConfig.model_validate(data)
    by_id = {e.id: e for e in cfg.pacs_endpoints}
    assert by_id["ct-only"].query.modalities == ["CT"]
    assert by_id["ct-only"].query.lookback_days == 30
    assert by_id["mr-only"].query.modalities == ["MR"]
    assert by_id["mr-only"].query.lookback_days == 7
