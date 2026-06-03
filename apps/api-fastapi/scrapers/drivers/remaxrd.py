"""
RE/MAX República Dominicana driver (Single Responsibility).

Phases per sync job:
  1. initialize() — RemaxCredentialHarvester (AdsPower, one browser session)
  2. run_sync()   — curl_cffi concurrent fetch + normalize to PropertyListing

Spec: .spec-kit/specs/api/ingestion-oop.spec.md §4
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from curl_cffi.requests import AsyncSession
from sqlmodel import Session

from models import PropertyListing
from scrapers.credential_harvester import HarvestedCredentials, RemaxCredentialHarvester
from scrapers.drivers.base_driver import BaseDriver
from scrapers.remax_detail_scraper import build_remax_portal_url
from scrapers.utils.normalization import (
    CHROME_USER_AGENT,
    combine_bathrooms,
    resolve_prices_usd_dop,
    safe_float,
    safe_int,
    title_case_label,
)

logger = logging.getLogger(__name__)

# Public RE/MAX JSON API (city=1 is Santo Domingo catalog in legacy scraper).
REMAX_API_URL = "https://api.remaxrd.com/v2/realestates"
# Canonical storefront URLs stored on PropertyListing.url.
REMAX_WEB_BASE = "https://www.remaxrd.com/en/propiedad"
# Max in-flight page requests; raising increases 429 risk from RE/MAX edge.
CONCURRENCY_LIMIT = 20
# Per-page retry budget when rate-limited or transiently failing.
MAX_FETCH_RETRIES = 4
# curl_cffi TLS fingerprint; must match browser used during credential harvest.
IMPERSONATE = "chrome120"


class RemaxRdDriver(BaseDriver):
    """
    Production driver for remaxrd portal token.

    Does not write to Postgres — returns PropertyListing list for orchestrator upsert.
    """

    source_portal = "remaxrd"

    def __init__(self, db_session: Session) -> None:
        """Wire harvester and empty credential cache."""
        super().__init__(db_session)
        self._harvester = RemaxCredentialHarvester()
        self._credentials: HarvestedCredentials | None = None

    async def initialize(self) -> None:
        """
        Harvest live api.remaxrd.com headers/cookies via AdsPower.

        Browser session is closed inside RemaxCredentialHarvester before return.
        """
        logger.info("RemaxRdDriver: harvesting credentials via AdsPower")
        self._credentials = await self._harvester.harvest()
        logger.info("RemaxRdDriver: credentials ready (browser session closed)")

    async def run_sync(self) -> list[PropertyListing]:
        """
        Fetch all RE/MAX pages and return deduplicated PropertyListing rows.

        Flow:
            - Ensure credentials
            - Page 1 → read meta.last_page
            - Pages 2..N concurrent under semaphore
            - Normalize each item in data[]
        """
        if self._credentials is None:
            await self.initialize()

        # Merge harvested auth headers; cookies included via as_curl_headers().
        headers = self._credentials.as_curl_headers()
        headers.setdefault("User-Agent", CHROME_USER_AGENT)

        listings: list[PropertyListing] = []
        seen_remote_ids: set[str] = set()

        async with AsyncSession(impersonate=IMPERSONATE) as session:
            # Sequential page 1: required to learn dynamic page ceiling.
            first_payload = await self._fetch_json_page(session, headers, 1)
            # API ground truth is meta.last_page — NOT meta.pagination.total_pages.
            last_page = int(first_payload.get("meta", {}).get("last_page", 1))
            logger.info(
                "RemaxRdDriver: page 1 ok meta.last_page=%s meta.total=%s",
                last_page,
                first_payload.get("meta", {}).get("total"),
            )

            self._collect_page_items(first_payload, listings, seen_remote_ids)

            if last_page > 1:
                # Bound parallelism to avoid tripping WAF/rate limits.
                semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
                page_numbers = list(range(2, last_page + 1))
                tasks = [
                    self._fetch_json_page(session, headers, page_num, semaphore)
                    for page_num in page_numbers
                ]
                # return_exceptions=True keeps one bad page from killing entire sync.
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for page_num, result in zip(page_numbers, results):
                    if isinstance(result, Exception):
                        logger.error("RemaxRdDriver: page %s failed: %s", page_num, result)
                        continue
                    self._collect_page_items(result, listings, seen_remote_ids)

        logger.info("RemaxRdDriver: normalized %s unique listings", len(listings))
        return listings

    def _collect_page_items(
        self,
        payload: dict[str, Any],
        listings: list[PropertyListing],
        seen_remote_ids: set[str],
    ) -> None:
        """
        Append normalized items from one API page response.

        Args:
            payload: Parsed JSON with data[] array.
            listings: Accumulator mutated in place.
            seen_remote_ids: Cross-page dedupe set (remote_id strings).
        """
        for item in payload.get("data", []):
            listing = self._normalize_item(item)
            if listing is None:
                continue
            # Skip duplicates when API returns overlapping rows across pages.
            if listing.remote_id in seen_remote_ids:
                continue
            seen_remote_ids.add(listing.remote_id)
            listings.append(listing)

    async def _fetch_json_page(
        self,
        session: AsyncSession,
        headers: dict[str, str],
        page_num: int,
        semaphore: asyncio.Semaphore | None = None,
    ) -> dict[str, Any]:
        """
        GET one RE/MAX API page with optional concurrency gate and 429 backoff.

        Args:
            session: Shared curl_cffi session for connection reuse.
            headers: Harvested auth + UA.
            page_num: 1-based page index.
            semaphore: When set, limits concurrent workers (pages 2+).

        Returns:
            Parsed JSON dict (meta + data).

        Raises:
            RuntimeError: On non-recoverable HTTP errors or exhausted 429 retries.
        """
        # Acquire slot, then recurse without semaphore to avoid nested lock deadlock.
        if semaphore is not None:
            async with semaphore:
                return await self._fetch_json_page(session, headers, page_num, None)

        url = f"{REMAX_API_URL}?city=1&page={page_num}"
        for attempt in range(1, MAX_FETCH_RETRIES + 1):
            response = await session.get(url, headers=headers, timeout=60)
            if response.status_code == 429:
                # Exponential backoff capped at 30s (legacy RemaxRDScraper policy).
                backoff = min(2**attempt, 30)
                logger.warning(
                    "RemaxRdDriver: 429 page=%s attempt=%s backoff=%ss",
                    page_num,
                    attempt,
                    backoff,
                )
                await asyncio.sleep(backoff)
                continue
            if response.status_code >= 400:
                raise RuntimeError(
                    f"RE/MAX API page {page_num} failed with status {response.status_code}: "
                    f"{response.text[:300]}"
                )
            return response.json()

        raise RuntimeError(
            f"RE/MAX API page {page_num} exhausted retries after repeated 429 responses."
        )

    def _normalize_item(self, item: dict[str, Any]) -> PropertyListing | None:
        """
        Map one RE/MAX API record to PropertyListing (develop / spec-kit parity).

        Args:
            item: Single element from response data[].

        Returns:
            PropertyListing or None when id is missing.
        """
        remote_id = item.get("id")
        if remote_id is None:
            return None

        slug = item.get("slug") or str(remote_id)
        property_url = build_remax_portal_url(
            str(slug),
            str(item.get("city") or ""),
            remote_id=str(remote_id),
        )

        currency_block = item.get("currency") or {}
        currency_iso = str(currency_block.get("iso", "USD")).upper()
        portal_price = safe_float(item.get("price"), default=0.0)
        price_usd, price_dop = resolve_prices_usd_dop(item.get("price"), currency_iso)

        city = title_case_label(item.get("city"), "Santo Domingo")
        sector = title_case_label(item.get("sector"), "Unknown")
        realstate_type = str(item.get("realstate_type") or "Property")
        business_type = str(item.get("business_type") or "")
        status = str(item.get("status") or "")

        bedrooms = safe_int(item.get("bedrooms"), default=0)
        bathrooms = combine_bathrooms(item.get("bathrooms"), item.get("half_bathrooms"))

        sqm_construction = safe_float(item.get("sqm_construction"), default=0.0)
        sqm_land = safe_float(item.get("sqm_land"), default=0.0)
        # Prefer construction sqm; use land when built area is zero.
        square_meters = sqm_construction if sqm_construction > 0 else sqm_land

        portal_name = str(item.get("name") or item.get("property_title") or "").strip()
        if portal_name:
            title = portal_name
        else:
            title = f"{realstate_type} en {sector}"
            if business_type:
                title = f"{realstate_type} ({business_type}) en {sector}"

        return PropertyListing(
            remote_id=str(remote_id),
            source_portal=self.source_portal,
            url=property_url,
            title=title,
            list_price=portal_price if portal_price > 0 else None,
            listing_currency=currency_iso,
            price_usd=price_usd,
            price_dop=price_dop,
            province=city,
            sector=sector,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            square_meters=square_meters,
            raw_description=(
                f"{realstate_type} | {business_type} | {sector}, {city} | "
                f"currency={currency_iso} | status={status}"
            ),
            # Spanish listing status; storefront treats "disponible" as active inventory.
            is_active=status.lower() == "disponible",
        )