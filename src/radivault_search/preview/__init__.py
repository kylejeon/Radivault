"""Buyer browse → preview → sample download (dev-spec-buyer-browse-preview).

This sub-package owns the buyer-facing preview surface:

  * ``preview.storage`` — MinIO/local FS adapter for thumbnail/frames/
    sample DICOM objects (Q-5 default ``radivault-preview`` bucket).
  * ``preview.quota`` — Redis ``quota:{buyer_pk}:{YYYYMMDD}`` counters
    (Q-6 default).
  * ``preview.router`` — three FastAPI endpoints (thumbnail / frames /
    sample-download) plus the ``preview_router`` export.

The sub-package is imported from ``radivault_search.app`` and wired
behind the existing ``BuyerAuthMiddleware`` + ``RateLimitMiddleware``
(see ``router.PROTECTED_PREFIXES``).
"""

from radivault_search.preview.router import router as preview_router

__all__ = ["preview_router"]
