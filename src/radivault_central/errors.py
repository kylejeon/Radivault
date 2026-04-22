"""Error taxonomy + FastAPI exception handlers (dev-spec §5 / §7.7, design-spec §2.2).

Every public API error funnels through a :class:`CentralError` subclass. The
handler emits the canonical envelope::

    {
      "error": "<CODE>",
      "detail": "<en>",
      "message_ko": "<ko>",
      "message_en": "<en>",
      "request_id": "<ulid>",
      "doc_url": "https://docs.radivault.io/central-ingest/errors/<CODE>",
      "retry_after": <int|null>
    }

The exact field set is mandated by design-spec §2.2 (fields 5 required + 2
optional). Dev-spec §7 originally specified a 3-field envelope; the design-spec
supersets it and this module implements the superset.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("radivault_central.errors")


DOC_BASE = "https://docs.radivault.io/central-ingest/errors"


class CentralError(Exception):
    """Base class for every public Central Ingest error.

    Subclasses declare ``code``, ``status_code``, and bilingual messages. A
    matching handler in this module emits the standard envelope with the
    correct HTTP status.
    """

    code: str = "ERR_INTERNAL"
    status_code: int = 500
    message_en: str = "An unexpected error occurred."
    message_ko: str = "알 수 없는 오류가 발생했습니다."
    retry_after: int | None = None

    def __init__(
        self,
        detail: str | None = None,
        *,
        message_ko: str | None = None,
        message_en: str | None = None,
        retry_after: int | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(detail or self.message_en)
        self.detail = detail or self.message_en
        if message_ko:
            self.message_ko = message_ko
        if message_en:
            self.message_en = message_en
        if retry_after is not None:
            self.retry_after = retry_after
        self.hint = hint

    def to_envelope(self, request_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.code,
            "detail": self.detail,
            "message_ko": self.message_ko,
            "message_en": self.message_en,
            "request_id": request_id,
            "doc_url": f"{DOC_BASE}/{self.code}",
            "retry_after": self.retry_after,
        }
        if self.hint:
            payload["hint"] = self.hint
        return payload


# --- Auth --------------------------------------------------------------------
class AuthMissing(CentralError):
    code = "ERR_AUTH_MISSING"
    status_code = 401
    message_en = "Authorization header missing or malformed."
    message_ko = "인증 헤더가 없거나 형식이 잘못되었습니다."


class AuthExpired(CentralError):
    code = "ERR_AUTH_EXPIRED"
    status_code = 401
    message_en = "Token has expired or been revoked."
    message_ko = "인증 토큰이 만료되었거나 철회되었습니다."


class AuthMismatch(CentralError):
    code = "ERR_AUTH_MISMATCH"
    status_code = 403
    message_en = "Token hospital_id does not match manifest/gateway."
    message_ko = "토큰의 병원과 요청 대상이 일치하지 않습니다."


# --- Idempotency -------------------------------------------------------------
class IdempMissing(CentralError):
    code = "ERR_IDEMP_MISSING"
    status_code = 400
    message_en = "Idempotency-Key header is required."
    message_ko = "Idempotency-Key 헤더가 필요합니다."


class IdempFormat(CentralError):
    code = "ERR_IDEMP_FORMAT"
    status_code = 400
    message_en = "Idempotency-Key format invalid (16-128 chars, [A-Za-z0-9_.-])."
    message_ko = "Idempotency-Key 형식이 잘못되었습니다."


class IdempMismatch(CentralError):
    code = "ERR_IDEMP_MISMATCH"
    status_code = 409
    message_en = "Same Idempotency-Key with a different payload."
    message_ko = "동일 Idempotency-Key에 다른 요청 바디가 제출되었습니다."


class IdempUnavailable(CentralError):
    code = "ERR_IDEMP_UNAVAILABLE"
    status_code = 503
    message_en = "Idempotency backend (Redis) is unavailable."
    message_ko = "서버 상태 확인 중입니다. 잠시 후 재시도하세요."
    retry_after = 30


# --- Manifest ----------------------------------------------------------------
class ManifestSchema(CentralError):
    code = "ERR_MANIFEST_SCHEMA"
    status_code = 400
    message_en = "Manifest failed schema validation."
    message_ko = "manifest 스키마 검증에 실패했습니다."


class ManifestVersion(CentralError):
    code = "ERR_MANIFEST_VERSION"
    status_code = 400
    message_en = "Unsupported manifest_version."
    message_ko = "지원하지 않는 manifest 버전입니다."


class ManifestSha256(CentralError):
    code = "ERR_MANIFEST_SHA256"
    status_code = 400
    message_en = "File sha256 mismatch between manifest and payload."
    message_ko = "파일 sha256 체크섬이 manifest와 일치하지 않습니다."


class ManifestRuleset(CentralError):
    code = "ERR_MANIFEST_RULESET"
    status_code = 400
    message_en = "ruleset_version not in hospital allowlist."
    message_ko = "ruleset_version이 병원 허용 목록에 없습니다."


class ManifestSalt(CentralError):
    code = "ERR_MANIFEST_SALT"
    status_code = 400
    message_en = "salt_version does not match hospital current salt."
    message_ko = "salt_version이 현재 병원 설정과 다릅니다."


class ManifestDeid(CentralError):
    code = "ERR_MANIFEST_DEID"
    status_code = 400
    message_en = "method_code_sequence must contain DICOM code 113100."
    message_ko = "De-ID 방법 코드(113100)가 누락되었습니다."


class ManifestAnon(CentralError):
    code = "ERR_MANIFEST_ANON"
    status_code = 403
    message_en = "manifest.anonymization_flag must be 'fully_anonymized'."
    message_ko = "manifest의 anonymization_flag가 fully_anonymized 여야 합니다."


class ManifestDuplicate(CentralError):
    code = "ERR_MANIFEST_DUP"
    status_code = 409
    message_en = "pseudo_study_uid already ingested."
    message_ko = "이미 수신된 스터디입니다."


class ManifestTooMany(CentralError):
    code = "ERR_MANIFEST_TOOMANY"
    status_code = 413
    message_en = "n_instances exceeds hospital max."
    message_ko = "instance 수가 병원 한도를 초과했습니다."


class ManifestTooBig(CentralError):
    code = "ERR_MANIFEST_TOOBIG"
    status_code = 413
    message_en = "total_bytes exceeds hospital max."
    message_ko = "전체 용량이 병원 한도를 초과했습니다."


# --- Anchor ------------------------------------------------------------------
class AnchorSchema(CentralError):
    code = "ERR_ANCHOR_SCHEMA"
    status_code = 400
    message_en = "Anchor payload failed schema validation."
    message_ko = "Anchor 페이로드 스키마 검증 실패."


class AnchorRange(CentralError):
    code = "ERR_ANCHOR_RANGE"
    status_code = 400
    message_en = "Anchor seq_lo must equal previous seq_hi + 1."
    message_ko = "앵커 seq 범위가 이전 앵커와 연속적이지 않습니다."


class AnchorInitial(CentralError):
    code = "ERR_ANCHOR_INITIAL"
    status_code = 400
    message_en = "First anchor must start with seq_lo == 1."
    message_ko = "첫 앵커는 seq_lo == 1 이어야 합니다."


class AnchorMono(CentralError):
    code = "ERR_ANCHOR_MONO"
    status_code = 400
    message_en = "anchored_at must be strictly increasing."
    message_ko = "anchored_at 시각이 직전 앵커보다 같거나 이전입니다."


class AnchorOrder(CentralError):
    code = "ERR_ANCHOR_ORDER"
    status_code = 400
    message_en = "seq_lo must be <= seq_hi."
    message_ko = "seq_lo가 seq_hi보다 큽니다."


class AnchorDuplicate(CentralError):
    code = "ERR_ANCHOR_DUP"
    status_code = 409
    message_en = "Anchor range already recorded."
    message_ko = "이미 기록된 앵커 범위입니다."


class AnchorHashDuplicate(CentralError):
    code = "ERR_ANCHOR_HASH_DUP"
    status_code = 409
    message_en = "Anchor head_hash already recorded."
    message_ko = "이미 기록된 앵커 head_hash입니다."


# --- Storage / DB / Rate / Generic ------------------------------------------
class StorageWriteError(CentralError):
    code = "ERR_STORE_WRITE"
    status_code = 502
    message_en = "Object storage write failed after retries."
    message_ko = "객체 스토리지 쓰기에 실패했습니다."


class DbUnavailable(CentralError):
    code = "ERR_DB_UNAVAILABLE"
    status_code = 503
    message_en = "Database is unavailable."
    message_ko = "데이터베이스를 사용할 수 없습니다."
    retry_after = 30


class RateLimited(CentralError):
    code = "ERR_RATE_LIMITED"
    status_code = 429
    message_en = "Rate limit exceeded."
    message_ko = "요청 한도를 초과했습니다."
    retry_after = 60


class RateQuotaDaily(CentralError):
    code = "ERR_RATE_QUOTA_DAILY"
    status_code = 429
    message_en = "Daily byte quota exceeded."
    message_ko = "일일 바이트 쿼터를 초과했습니다."
    retry_after = 3600


class RateQuotaMonthly(CentralError):
    code = "ERR_RATE_QUOTA_MONTHLY"
    status_code = 429
    message_en = "Monthly byte quota exceeded."
    message_ko = "월간 바이트 쿼터를 초과했습니다."
    retry_after = 86400


class NotImplementedStub(CentralError):
    code = "ERR_NOT_IMPLEMENTED"
    status_code = 501
    message_en = "Endpoint is a v0.1 stub; feature deferred."
    message_ko = "v0.1 스텁입니다. 해당 기능은 차기 버전에서 제공됩니다."


class UnsupportedMedia(CentralError):
    code = "ERR_UNSUPPORTED_MEDIA"
    status_code = 415
    message_en = "Content-Type not supported by this endpoint."
    message_ko = "지원되지 않는 Content-Type 입니다."


class IngestContentType(CentralError):
    code = "ERR_INGEST_CTYPE"
    status_code = 400
    message_en = "Ingest endpoint requires multipart/form-data."
    message_ko = "업로드 엔드포인트는 multipart/form-data 가 필요합니다."


# ---------------------------------------------------------------------------
# Handler installation
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Attach CentralError handlers + coerce validation errors to ERR_MANIFEST_SCHEMA."""

    @app.exception_handler(CentralError)
    async def _central(request: Request, exc: CentralError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        envelope = exc.to_envelope(request_id=request_id)
        headers: dict[str, str] = {"X-Request-Id": request_id}
        if exc.retry_after is not None:
            headers["Retry-After"] = str(exc.retry_after)
        if exc.code == "ERR_AUTH_MISSING":
            headers["WWW-Authenticate"] = 'Bearer realm="central-ingest"'
        log.warning(
            "central_error",
            extra={
                "event": "api.error",
                "error_code": exc.code,
                "status": exc.status_code,
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(status_code=exc.status_code, content=envelope, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        wrapped = ManifestSchema(detail=_first_error(exc.errors()))
        return await _central(request, wrapped)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Map FastAPI-native HTTPException into the envelope shape.
        if exc.status_code == 404:
            wrapped: CentralError = _NotFound(detail=str(exc.detail))
        elif exc.status_code == 405:
            wrapped = _MethodNotAllowed(detail=str(exc.detail))
        elif exc.status_code == 415:
            wrapped = UnsupportedMedia(detail=str(exc.detail))
        else:
            wrapped = _Generic(status=exc.status_code, detail=str(exc.detail))
        return await _central(request, wrapped)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception", extra={"path": request.url.path})
        wrapped = CentralError(detail="unexpected server error")
        return await _central(request, wrapped)


def _first_error(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return "validation error"
    err = errors[0]
    loc = ".".join(str(x) for x in err.get("loc", [])) or "?"
    return f"{loc}: {err.get('msg', 'invalid')}"


class _NotFound(CentralError):
    code = "ERR_NOT_FOUND"
    status_code = 404
    message_en = "Resource not found."
    message_ko = "리소스를 찾을 수 없습니다."


class _MethodNotAllowed(CentralError):
    code = "ERR_METHOD_NOT_ALLOWED"
    status_code = 405
    message_en = "HTTP method not allowed for this path."
    message_ko = "허용되지 않은 HTTP 메서드입니다."


class _Generic(CentralError):
    def __init__(self, *, status: int, detail: str) -> None:
        super().__init__(detail=detail)
        self.status_code = status
        self.code = f"ERR_HTTP_{status}"
