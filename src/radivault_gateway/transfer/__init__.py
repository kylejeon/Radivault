"""Gateway transfer-job consumer subsystem (dev-spec §14 G-1).

Disabled by default; enabled via the ``transfer.enabled`` config flag.
Operates as a parallel asyncio loop alongside Flow A (continuous PACS
poll); the two share PACS concurrency.
"""

from __future__ import annotations

from radivault_gateway.transfer.claim import ClaimClient
from radivault_gateway.transfer.config import TransferConfig
from radivault_gateway.transfer.consumer import TransferConsumer
from radivault_gateway.transfer.progress import ProgressReporter

__all__ = [
    "ClaimClient",
    "ProgressReporter",
    "TransferConfig",
    "TransferConsumer",
]
