"""Error taxonomy for radivault_search (dev-spec §7.6, design-spec §2.x).

Extends ``radivault_central.errors.CentralError`` with the new codes called out
by the search dev-spec (FR-2, FR-12, FR-16..20, FR-23, FR-26/27, FR-41, etc.).
All errors funnel through the standard 7-field envelope installed by
:func:`register_exception_handlers`.
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
    IdempUnavailable,
    RateLimited,
)

log = logging.getLogger("radivault_search.errors")

DOC_BASE = "https://docs.radivault.io/search/errors"


class SearchError(CentralError):
    """Base class for radivault_search-specific errors.

    Overrides ``to_envelope`` to use the search docs URL prefix; otherwise
    shares the central envelope shape.
    """

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
class AuthFormat(SearchError):
    code = "ERR_AUTH_FORMAT"
    status_code = 401
    message_en = "API key format invalid."
    message_ko = "키 형식이 올바르지 않습니다."


class ScopeForbidden(SearchError):
    code = "ERR_SCOPE_FORBIDDEN"
    status_code = 403
    message_en = "Insufficient scope for this resource."
    message_ko = "해당 데이터 접근 권한이 없습니다."


# --- Request validation ------------------------------------------------------
class RequestSchema(SearchError):
    code = "ERR_REQUEST_SCHEMA"
    status_code = 400
    message_en = "Request schema invalid."
    message_ko = "요청 스키마가 올바르지 않습니다."


class FilterTooMany(SearchError):
    code = "ERR_FILTER_TOO_MANY"
    status_code = 400
    message_en = "IN filter exceeds 10 items."
    message_ko = "필터에 10개를 초과하는 값이 있습니다."


class PageLimit(SearchError):
    code = "ERR_PAGE_LIMIT"
    status_code = 400
    message_en = "Page limit exceeds tier cap."
    message_ko = "페이지 크기가 티어 상한을 초과합니다."


# --- Cursor ------------------------------------------------------------------
class CursorFilterChanged(SearchError):
    code = "ERR_CURSOR_FILTER_CHANGED"
    status_code = 400
    message_en = "The cursor was issued for a different filter. Restart from page 1."
    message_ko = "커서 이후 필터가 변경되었습니다. 1페이지부터 다시 요청하세요."


class CursorVersion(SearchError):
    code = "ERR_CURSOR_VERSION"
    status_code = 400
    message_en = "Unsupported cursor version."
    message_ko = "지원하지 않는 커서 버전입니다."


# --- Cost / perf -------------------------------------------------------------
class QueryTooBroad(SearchError):
    code = "ERR_QUERY_TOO_BROAD"
    status_code = 422
    message_en = "Query is too broad. Narrow modality or date range."
    message_ko = "쿼리가 너무 광범위합니다. 모달리티 또는 날짜 범위를 좁혀주세요."


class QueryTimeout(SearchError):
    code = "ERR_QUERY_TIMEOUT"
    status_code = 504
    message_en = "Query timed out."
    message_ko = "쿼리가 시간을 초과했습니다."


# --- Rate / quota ------------------------------------------------------------
class BuyerQuota(SearchError):
    code = "ERR_BUYER_QUOTA"
    status_code = 429
    message_en = "Daily quota exhausted."
    message_ko = "일일 쿼터를 모두 사용했습니다."
    retry_after = 3600


class BuyerConcurrency(SearchError):
    code = "ERR_BUYER_CONCURRENCY"
    status_code = 429
    message_en = "Concurrent request cap exceeded."
    message_ko = "동시 요청 수 한도를 초과했습니다."
    retry_after = 10


# --- Data --------------------------------------------------------------------
class StudyNotFound(SearchError):
    code = "ERR_STUDY_NOT_FOUND"
    status_code = 404
    message_en = "Study not found."
    message_ko = "스터디를 찾을 수 없습니다."


# --- Preview / sample download (dev-spec-buyer-browse-preview FR-API-1) -----
class PreviewNotVerified(SearchError):
    code = "ERR_PREVIEW_NOT_VERIFIED"
    status_code = 403
    message_en = "This study has not passed PHI verification."
    message_ko = "이 스터디는 PHI 검증을 통과하지 않았습니다."


class FrameNotFound(SearchError):
    code = "ERR_FRAME_NOT_FOUND"
    status_code = 404
    message_en = "Requested preview frame not found."
    message_ko = "요청한 프리뷰 프레임을 찾을 수 없습니다."


class SampleInstanceMissing(SearchError):
    code = "ERR_SAMPLE_INSTANCE_MISSING"
    status_code = 409
    message_en = "Sample instance is not configured for this study."
    message_ko = "이 스터디에는 샘플 인스턴스가 구성되지 않았습니다."


class QuotaExceededError(SearchError):
    code = "ERR_QUOTA_EXCEEDED"
    status_code = 429
    message_en = "Daily sample download limit reached."
    message_ko = "일일 샘플 다운로드 한도에 도달했습니다."


class PresignFailed(SearchError):
    code = "ERR_PRESIGN_FAILED"
    status_code = 500
    message_en = "Sample download could not be prepared."
    message_ko = "샘플 다운로드를 준비하지 못했습니다."


# ---------------------------------------------------------------------------
# Handler installation — envelope shaping identical to central-ingest.
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Attach SearchError/CentralError handlers + map validation errors."""

    @app.exception_handler(CentralError)
    async def _search(request: Request, exc: CentralError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        envelope = exc.to_envelope(request_id=request_id)
        # Rewrite doc_url to search namespace for the central-inherited codes
        # that fire from this service (AuthMissing, AuthExpired, RateLimited,
        # IdempUnavailable, DbUnavailable).
        if not isinstance(exc, SearchError):
            envelope["doc_url"] = f"{DOC_BASE}/{exc.code}"
        headers: dict[str, str] = {"X-Request-Id": request_id}
        if exc.retry_after is not None:
            headers["Retry-After"] = str(exc.retry_after)
        if exc.code == "ERR_AUTH_MISSING":
            headers["WWW-Authenticate"] = 'Bearer realm="radivault-search"'
        log.warning(
            "search_error",
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
        return await _search(request, wrapped)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            wrapped: CentralError = _NotFound(detail=str(exc.detail))
        elif exc.status_code == 405:
            wrapped = _MethodNotAllowed(detail=str(exc.detail))
        elif exc.status_code == 415:
            wrapped = _UnsupportedMedia(detail=str(exc.detail))
        else:
            wrapped = _Generic(status=exc.status_code, detail=str(exc.detail))
        return await _search(request, wrapped)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception", extra={"path": request.url.path})
        wrapped = SearchError(detail="unexpected server error")
        return await _search(request, wrapped)


def _first_error(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return "validation error"
    err = errors[0]
    loc = ".".join(str(x) for x in err.get("loc", [])) or "?"
    return f"{loc}: {err.get('msg', 'invalid')}"


class _NotFound(SearchError):
    code = "ERR_NOT_FOUND"
    status_code = 404
    message_en = "Resource not found."
    message_ko = "리소스를 찾을 수 없습니다."


class _MethodNotAllowed(SearchError):
    code = "ERR_METHOD_NOT_ALLOWED"
    status_code = 405
    message_en = "HTTP method not allowed for this path."
    message_ko = "허용되지 않은 HTTP 메서드입니다."


class _UnsupportedMedia(SearchError):
    code = "ERR_UNSUPPORTED_MEDIA"
    status_code = 415
    message_en = "Content-Type not supported by this endpoint."
    message_ko = "지원되지 않는 Content-Type 입니다."


class _Generic(SearchError):
    def __init__(self, *, status: int, detail: str) -> None:
        super().__init__(detail=detail)
        self.status_code = status
        self.code = f"ERR_HTTP_{status}"


# Re-export the central-inherited codes that fire from routers.
__all__ = [
    "AuthExpired",
    "AuthFormat",
    "AuthMissing",
    "BuyerConcurrency",
    "BuyerQuota",
    "CursorFilterChanged",
    "CursorVersion",
    "DbUnavailable",
    "FilterTooMany",
    "FrameNotFound",
    "IdempUnavailable",
    "PageLimit",
    "PresignFailed",
    "PreviewNotVerified",
    "QueryTimeout",
    "QueryTooBroad",
    "QuotaExceededError",
    "RateLimited",
    "RequestSchema",
    "SampleInstanceMissing",
    "ScopeForbidden",
    "SearchError",
    "StudyNotFound",
    "register_exception_handlers",
]
