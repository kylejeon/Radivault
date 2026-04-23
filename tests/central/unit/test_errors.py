"""Error taxonomy smoke tests."""

from __future__ import annotations

from radivault_central.errors import (
    AnchorDuplicate,
    AuthExpired,
    AuthMismatch,
    AuthMissing,
    CentralError,
    IdempUnavailable,
    ManifestAnon,
    ManifestSchema,
    RateLimited,
    StorageWriteError,
)


def test_envelope_includes_required_fields():
    exc = ManifestAnon()
    env = exc.to_envelope(request_id="01HX")
    for field in (
        "error",
        "detail",
        "message_ko",
        "message_en",
        "request_id",
        "doc_url",
        "retry_after",
    ):
        assert field in env
    assert env["error"] == "ERR_MANIFEST_ANON"


def test_rate_limited_has_retry_after():
    exc = RateLimited(retry_after=27)
    env = exc.to_envelope(request_id="x")
    assert env["retry_after"] == 27


def test_doc_url_points_at_error_code():
    for cls in [
        AuthMissing,
        AuthExpired,
        AuthMismatch,
        ManifestSchema,
        ManifestAnon,
        AnchorDuplicate,
        StorageWriteError,
        IdempUnavailable,
    ]:
        exc = cls()
        env = exc.to_envelope(request_id="r")
        assert env["doc_url"].endswith(exc.code)


def test_status_codes_match_dev_spec():
    # dev-spec §7.7 mapping sanity.
    assert AuthMissing.status_code == 401
    assert AuthMismatch.status_code == 403
    assert ManifestAnon.status_code == 403
    assert StorageWriteError.status_code == 502
    assert RateLimited.status_code == 429


def test_base_class_default_500():
    base = CentralError()
    assert base.status_code == 500
    assert base.code == "ERR_INTERNAL"
