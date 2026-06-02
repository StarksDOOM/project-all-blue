import asyncio
import traceback
from typing import Any, Dict

from database import init_db
from scrapers.drivers.remaxrd import RemaxRDScraper

SUPPORTED_PORTALS = {"remaxrd"}


async def run_portal_sync(source_portal: str) -> Dict[str, Any]:
    init_db()

    if source_portal not in SUPPORTED_PORTALS:
        raise ValueError(f"Unsupported portal sync driver: {source_portal}")

    if source_portal == "remaxrd":
        scraper = RemaxRDScraper()
        return await scraper.run_full_sync()

    raise ValueError(f"No sync implementation registered for '{source_portal}'.")


def execute_portal_sync_background(source_portal: str) -> None:
    """Entry point for FastAPI BackgroundTasks (sync wrapper)."""
    try:
        print(f"[Sync Engine] Background job started for portal '{source_portal}'.")
        result = asyncio.run(run_portal_sync(source_portal))
        print(f"[Sync Engine] Background job completed: {result}")
    except Exception as exc:
        print(f"[Sync Engine] Background job failed for '{source_portal}': {exc}")
        traceback.print_exc()