"""Error taxonomy for radivault_fulfillment (dev-spec §7.11, §13.1).

Extends :class:`radivault_central.errors.CentralError` with the 24 new codes
the order-fulfillment feature introduces. All responses funnel through the
canonical envelope installed by :func:`register_exception_handlers`.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from radivault_central.errors import (
    AuthExpired,
    AuthMissing,
    CentralError,
    DbUnavailable,
    IdempFormat,
    IdempMissing,
    IdempUnavailable,
    RateLimited,
)

log = logging.getLogger("radivault_fulfillment.errors")

DOC_BASE = "https://docs.radivault.io/fulfillment/errors"


class FulfillmentError(CentralError):
    """Base class for fulfillment-specific errors."""

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


# --- Auth (2 new) ------------------------------------------------------------
class AuthWrongPlane(FulfillmentError):
    code = "ERR_AUTH_WRONG_PLANE"
    status_code = 401
    message_en = "Wrong token type for this endpoint plane."
    message_ko = "이 엔드포인트에 잘못된 종류의 인증 토큰이 사용되었습니다."


class AuthUnavailable(FulfillmentError):
    code = "ERR_AUTH_UNAVAILABLE"
    status_code = 503
    message_en = "Authentication infrastructure (Redis + DB) is unreachable."
    message_ko = "인증 인프라가 일시적으로 사용 불가합니다."
    retry_after = 30


# --- Request validation -----------------------------------------------------
class RequestSchema(FulfillmentError):
    code = "ERR_REQUEST_SCHEMA"
    status_code = 400
    message_en = "Request schema invalid."
    message_ko = "요청 스키마가 올바르지 않습니다."


# --- Order (13 new) ---------------------------------------------------------
class OrderDuplicateStudy(FulfillmentError):
    code = "ERR_ORDER_DUPLICATE_STUDY"
    status_code = 400
    message_en = "pseudo_study_uid duplicated within cohort."
    message_ko = "코호트에 중복된 study UID가 있습니다."


class OrderAgreementRequired(FulfillmentError):
    code = "ERR_ORDER_AGREEMENT_REQUIRED"
    status_code = 400
    message_en = "agreement_hash missing or does not match the current MSA."
    message_ko = "동의 해시가 누락되었거나 현재 MSA와 일치하지 않습니다."


class OrderScopeForbidden(FulfillmentError):
    code = "ERR_ORDER_SCOPE_FORBIDDEN"
    status_code = 403
    message_en = "Buyer scope prohibits one or more hospitals in cohort."
    message_ko = "구매자의 스코프가 코호트 내 병원 중 하나 이상을 금지합니다."


class OrderStudyNotFound(FulfillmentError):
    code = "ERR_ORDER_STUDY_NOT_FOUND"
    status_code = 404
    message_en = "One or more pseudo_study_uid is not indexed."
    message_ko = "하나 이상의 study UID가 인덱스에 없습니다."


class OrderNotFound(FulfillmentError):
    code = "ERR_ORDER_NOT_FOUND"
    status_code = 404
    message_en = "Order not found or not owned by this buyer."
    message_ko = "주문을 찾을 수 없거나 접근 권한이 없습니다."


class OrderNotReady(FulfillmentError):
    code = "ERR_ORDER_NOT_READY"
    status_code = 409
    message_en = "Order is not in 'ready_for_download' state."
    message_ko = "주문이 다운로드 준비 상태가 아닙니다."


class OrderStateTransition(FulfillmentError):
    code = "ERR_ORDER_STATE_TRANSITION"
    status_code = 409
    message_en = "Illegal order state transition for this actor."
    message_ko = "요청하신 상태 전이는 허용되지 않습니다."


class OrderExpired(FulfillmentError):
    code = "ERR_ORDER_EXPIRED"
    status_code = 410
    message_en = "Order has expired."
    message_ko = "주문이 만료되었습니다."


class OrderTerminal(FulfillmentError):
    code = "ERR_ORDER_TERMINAL"
    status_code = 410
    message_en = "Order is in a terminal state (cancelled or failed)."
    message_ko = "주문이 취소 또는 실패 상태로 종료되었습니다."


class OrderTooLarge(FulfillmentError):
    code = "ERR_ORDER_TOO_LARGE"
    status_code = 413
    message_en = "Cohort total_bytes exceeds tier cap."
    message_ko = "코호트 총 용량이 티어 상한을 초과합니다."


class OrderTierExceeded(FulfillmentError):
    code = "ERR_ORDER_TIER_EXCEEDED"
    status_code = 422
    message_en = "Cohort size exceeds tier cap."
    message_ko = "코호트 크기가 티어 상한을 초과합니다."


class OrderQuotaExceeded(FulfillmentError):
    code = "ERR_ORDER_QUOTA_EXCEEDED"
    status_code = 429
    message_en = "Daily order quota exceeded."
    message_ko = "일일 주문 한도를 초과했습니다."
    retry_after = 3600


# --- URL (3 new) ------------------------------------------------------------
class UrlTtlExceeded(FulfillmentError):
    code = "ERR_URL_TTL_EXCEEDED"
    status_code = 422
    message_en = "Requested ttl_seconds exceeds tier cap."
    message_ko = "요청한 TTL이 티어 상한을 초과합니다."


class UrlMintRate(FulfillmentError):
    code = "ERR_URL_MINT_RATE"
    status_code = 429
    message_en = "URL mint rate limit exceeded."
    message_ko = "URL 발급 요청 한도를 초과했습니다."
    retry_after = 5


class UrlMintFailed(FulfillmentError):
    code = "ERR_URL_MINT_FAILED"
    status_code = 502
    message_en = "Presigned URL signing failed (S3/KMS)."
    message_ko = "프리사인드 URL 발급에 실패했습니다."


# --- Job (7 new) ------------------------------------------------------------
class JobNotFound(FulfillmentError):
    code = "ERR_JOB_NOT_FOUND"
    status_code = 404
    message_en = "Transfer job not found."
    message_ko = "Transfer job을 찾을 수 없습니다."


class JobLeaseOwnership(FulfillmentError):
    code = "ERR_JOB_LEASE_OWNERSHIP"
    status_code = 403
    message_en = "Lease owner mismatch."
    message_ko = "Lease 소유자가 일치하지 않습니다."


class JobLeaseExpired(FulfillmentError):
    code = "ERR_JOB_LEASE_EXPIRED"
    status_code = 409
    message_en = "Lease has expired; re-claim required."
    message_ko = "Lease가 만료되어 재claim이 필요합니다."


class JobStateConflict(FulfillmentError):
    code = "ERR_JOB_STATE_CONFLICT"
    status_code = 409
    message_en = "Job state does not allow this operation."
    message_ko = "현재 Job 상태에서는 요청한 작업이 불가합니다."


class JobHospitalMismatch(FulfillmentError):
    code = "ERR_JOB_HOSPITAL_MISMATCH"
    status_code = 403
    message_en = "Gateway hospital does not own this job."
    message_ko = "해당 Job의 병원이 게이트웨이 소속과 일치하지 않습니다."


class JobManifestMismatch(FulfillmentError):
    code = "ERR_JOB_MANIFEST_MISMATCH"
    status_code = 400
    message_en = "Complete manifest diverges from claim studies."
    message_ko = "완료 manifest가 claim된 스터디와 일치하지 않습니다."


class JobCounterRegress(FulfillmentError):
    code = "ERR_JOB_COUNTER_REGRESS"
    status_code = 400
    message_en = "Progress counter decreased (must be monotonic)."
    message_ko = "진행률 카운터가 감소했습니다."


# ---------------------------------------------------------------------------
# Handler installation.
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Attach FulfillmentError/CentralError handlers + coerce validation errors."""

    @app.exception_handler(CentralError)
    async def _fulfillment(request: Request, exc: CentralError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        envelope = exc.to_envelope(request_id=request_id)
        if not isinstance(exc, FulfillmentError):
            envelope["doc_url"] = f"{DOC_BASE}/{exc.code}"
        headers: dict[str, str] = {"X-Request-Id": request_id}
        if exc.retry_after is not None:
            headers["Retry-After"] = str(exc.retry_after)
        if exc.code == "ERR_AUTH_MISSING":
            headers["WWW-Authenticate"] = 'Bearer realm="radivault-fulfillment"'
        log.warning(
            "fulfillment_error",
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
        wrapped = RequestSchema(detail=_first_error(exc.errors()))
        return await _fulfillment(request, wrapped)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            wrapped: CentralError = _NotFound(detail=str(exc.detail))
        elif exc.status_code == 405:
            wrapped = _MethodNotAllowed(detail=str(exc.detail))
        else:
            wrapped = _Generic(status=exc.status_code, detail=str(exc.detail))
        return await _fulfillment(request, wrapped)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception", extra={"path": request.url.path})
        wrapped = FulfillmentError(detail="unexpected server error")
        return await _fulfillment(request, wrapped)


def _first_error(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return "validation error"
    err = errors[0]
    loc = ".".join(str(x) for x in err.get("loc", [])) or "?"
    return f"{loc}: {err.get('msg', 'invalid')}"


class _NotFound(FulfillmentError):
    code = "ERR_NOT_FOUND"
    status_code = 404
    message_en = "Resource not found."
    message_ko = "리소스를 찾을 수 없습니다."


class _MethodNotAllowed(FulfillmentError):
    code = "ERR_METHOD_NOT_ALLOWED"
    status_code = 405
    message_en = "HTTP method not allowed for this path."
    message_ko = "허용되지 않은 HTTP 메서드입니다."


class _Generic(FulfillmentError):
    def __init__(self, *, status: int, detail: str) -> None:
        super().__init__(detail=detail)
        self.status_code = status
        self.code = f"ERR_HTTP_{status}"


__all__ = [
    "AuthExpired",
    "AuthMissing",
    "AuthUnavailable",
    "AuthWrongPlane",
    "DbUnavailable",
    "FulfillmentError",
    "IdempFormat",
    "IdempMissing",
    "IdempUnavailable",
    "JobCounterRegress",
    "JobHospitalMismatch",
    "JobLeaseExpired",
    "JobLeaseOwnership",
    "JobManifestMismatch",
    "JobNotFound",
    "JobStateConflict",
    "OrderAgreementRequired",
    "OrderDuplicateStudy",
    "OrderExpired",
    "OrderNotFound",
    "OrderNotReady",
    "OrderQuotaExceeded",
    "OrderScopeForbidden",
    "OrderStateTransition",
    "OrderStudyNotFound",
    "OrderTerminal",
    "OrderTierExceeded",
    "OrderTooLarge",
    "RateLimited",
    "RequestSchema",
    "UrlMintFailed",
    "UrlMintRate",
    "UrlTtlExceeded",
    "register_exception_handlers",
]
