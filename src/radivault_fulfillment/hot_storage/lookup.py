"""Partition a cohort into hot-hit vs cold subsets (FR-34).

Reads ``study.central_object_present`` (contract delta C-1). The validator
already does this inline as part of FR-11; this module provides a stand-alone
entrypoint for tests, admin scripts, and future Flow-C automation.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from radivault_central.db.models import Study


@dataclass
class HotColdPartition:
    hot_hit: set[str]
    cold: set[str]

    @property
    def path_type(self) -> str:
        if not self.cold:
            return "hot"
        if not self.hot_hit:
            return "cold"
        return "mixed"


def partition(
    session: Session, *, pseudo_study_uids: list[str]
) -> HotColdPartition:
    rows = (
        session.execute(
            select(Study.pseudo_study_uid, Study.central_object_present).where(
                Study.pseudo_study_uid.in_(pseudo_study_uids)
            )
        )
        .all()
    )
    hot: set[str] = set()
    for uid, present in rows:
        if bool(present):
            hot.add(uid)
    cold = {u for u in pseudo_study_uids if u not in hot}
    return HotColdPartition(hot_hit=hot, cold=cold)


__all__ = ["HotColdPartition", "partition"]
