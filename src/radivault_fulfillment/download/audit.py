"""Download audit — append to ``download_event`` on every url_minted (FR-65/69)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from radivault_fulfillment.db.models import DownloadEvent


def record_url_minted(
    session: Session,
    *,
    order_pk: int,
    order_item_pk: int | None,
    buyer_pk: int,
    kid: str,
    src_ip: str | None,
    user_agent: str | None,
    request_id: str,
    object_key: str,
    signature_hash: str,
    ttl_seconds: int,
) -> DownloadEvent:
    event = DownloadEvent(
        order_pk=order_pk,
        order_item_pk=order_item_pk,
        buyer_pk=buyer_pk,
        kid=kid,
        event_type="url_minted",
        src_ip=src_ip,
        user_agent=user_agent,
        request_id=request_id,
        object_key=object_key,
        signature_hash=signature_hash,
        ttl_seconds=ttl_seconds,
    )
    session.add(event)
    return event


__all__ = ["record_url_minted"]
