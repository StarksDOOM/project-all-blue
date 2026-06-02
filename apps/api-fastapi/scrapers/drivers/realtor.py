"""
Realtor.com portal driver — placeholder (STREAM 2 PHASE 4.2).

Registered in DriverFactory so API can return 501 before scheduling work.
"""

from __future__ import annotations

from models import PropertyListing
from scrapers.drivers.base_driver import BaseDriver


class RealtorDriver(BaseDriver):
    """
    Stub driver for realtor.com ingestion (parser not built yet).

    HTTP layer rejects this with 501; run_sync exists only for factory parity.
    """

    source_portal = "realtor"

    async def initialize(self) -> None:
        """No-op until Realtor auth/harvest strategy is defined."""
        return None

    async def run_sync(self) -> list[PropertyListing]:
        """
        Guard rail when sync is invoked without router (CLI/tests).

        Production path should never reach here — properties.trigger_crawl returns 501.
        """
        raise NotImplementedError("Driver 'realtor' pending implementation")