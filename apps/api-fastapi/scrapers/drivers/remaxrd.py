import asyncio
from typing import Any, Dict, List, Optional, Tuple

from curl_cffi.requests import AsyncSession
from sqlmodel import Session, select

from database import engine, get_current_timestamp_ms
from models import PropertyListing
from scrapers.credential_harvester import HarvestedCredentials, RemaxCredentialHarvester

DOP_TO_USD_RATE = 59.50
REMAX_API_URL = "https://api.remaxrd.com/v2/realestates"
REMAX_WEB_BASE = "https://www.remaxrd.com/en/propiedad"
CONCURRENCY_LIMIT = 20
UPSERT_BATCH_SIZE = 250
MAX_FETCH_RETRIES = 4


class RemaxRDScraper:
    SOURCE_PORTAL = "remaxrd"

    def __init__(self) -> None:
        self._harvester = RemaxCredentialHarvester()

    async def harvest_credentials(self) -> HarvestedCredentials:
        return await self._harvester.harvest()

    async def fetch_all_pages(self, credentials: HarvestedCredentials) -> List[Dict[str, Any]]:
        headers = credentials.as_curl_headers()
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

        async with AsyncSession(impersonate="chrome120") as session:
            first_payload = await self._fetch_json_page(
                session, headers, 1, semaphore
            )
            last_page = int(first_payload.get("meta", {}).get("last_page", 1))
            print(
                f"[RemaxRD API] Page 1 retrieved. meta.last_page={last_page}, "
                f"meta.total={first_payload.get('meta', {}).get('total')}"
            )

            normalized: List[Dict[str, Any]] = []
            seen_remote_ids: set[str] = set()

            for item in first_payload.get("data", []):
                listing = self.normalize_item(item)
                if listing and listing["remote_id"] not in seen_remote_ids:
                    seen_remote_ids.add(listing["remote_id"])
                    normalized.append(listing)

            if last_page > 1:
                remaining_pages = list(range(2, last_page + 1))
                tasks = [
                    self._fetch_json_page(session, headers, page_num, semaphore)
                    for page_num in remaining_pages
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for page_num, result in zip(remaining_pages, results):
                    if isinstance(result, Exception):
                        print(f"[RemaxRD API] Page {page_num} failed: {result}")
                        continue
                    for item in result.get("data", []):
                        listing = self.normalize_item(item)
                        if listing and listing["remote_id"] not in seen_remote_ids:
                            seen_remote_ids.add(listing["remote_id"])
                            normalized.append(listing)

            print(f"[RemaxRD API] Normalized {len(normalized)} unique listings from {last_page} pages.")
            return normalized

    async def _fetch_json_page(
        self,
        session: AsyncSession,
        headers: Dict[str, str],
        page_num: int,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Any]:
        async with semaphore:
            url = f"{REMAX_API_URL}?city=1&page={page_num}"
            for attempt in range(1, MAX_FETCH_RETRIES + 1):
                response = await session.get(url, headers=headers, timeout=60)
                if response.status_code == 429:
                    backoff = min(2 ** attempt, 30)
                    print(
                        f"[RemaxRD API] 429 on page {page_num}; "
                        f"backing off {backoff}s (attempt {attempt}/{MAX_FETCH_RETRIES})"
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

    def normalize_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        remote_id = item.get("id")
        if remote_id is None:
            return None

        slug = item.get("slug") or str(remote_id)
        property_url = f"{REMAX_WEB_BASE}/{slug}"

        currency_block = item.get("currency") or {}
        currency_iso = str(currency_block.get("iso", "USD")).upper()
        price_usd, price_dop = self._resolve_prices(item, currency_iso)

        city = str(item.get("city") or "Santo Domingo").title()
        sector = str(item.get("sector") or "Unknown").title()
        realstate_type = str(item.get("realstate_type") or "Property")
        business_type = str(item.get("business_type") or "")
        status = str(item.get("status") or "")

        bedrooms = self._safe_int(item.get("bedrooms"), default=0)
        full_baths = self._safe_float(item.get("bathrooms"), default=0.0)
        half_baths = self._safe_float(item.get("half_bathrooms"), default=0.0)
        bathrooms = full_baths + (0.5 * half_baths)

        sqm_construction = self._safe_float(item.get("sqm_construction"), default=0.0)
        sqm_land = self._safe_float(item.get("sqm_land"), default=0.0)
        square_meters = sqm_construction if sqm_construction > 0 else sqm_land

        title = f"{realstate_type} en {sector}"
        if business_type:
            title = f"{realstate_type} ({business_type}) en {sector}"

        return {
            "remote_id": str(remote_id),
            "source_portal": self.SOURCE_PORTAL,
            "url": property_url,
            "title": title,
            "price_usd": price_usd,
            "price_dop": price_dop,
            "province": city,
            "sector": sector,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "square_meters": square_meters,
            "raw_description": (
                f"{realstate_type} | {business_type} | {sector}, {city} | "
                f"currency={currency_iso} | status={status}"
            ),
            "is_active": status.lower() == "disponible",
        }

    def _resolve_prices(
        self, item: Dict[str, Any], currency_iso: str
    ) -> Tuple[float, Optional[float]]:
        price_raw = self._safe_float(item.get("price"), default=0.0)
        if price_raw <= 0:
            return 0.0, None

        if currency_iso == "DOP":
            price_dop = round(price_raw, 2)
            price_usd = round(price_raw / DOP_TO_USD_RATE, 2)
            return price_usd, price_dop

        price_usd = round(price_raw, 2)
        price_dop = round(price_raw * DOP_TO_USD_RATE, 2)
        return price_usd, price_dop

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def bulk_upsert(self, listings_data: List[Dict[str, Any]]) -> Dict[str, int]:
        if not listings_data:
            return {"inserted": 0, "updated": 0, "total": 0}

        inserted = 0
        updated = 0
        now_ms = get_current_timestamp_ms()

        with Session(engine) as session:
            for batch_start in range(0, len(listings_data), UPSERT_BATCH_SIZE):
                batch = listings_data[batch_start : batch_start + UPSERT_BATCH_SIZE]
                remote_ids = [row["remote_id"] for row in batch]

                existing_rows = session.exec(
                    select(PropertyListing).where(
                        PropertyListing.source_portal == self.SOURCE_PORTAL,
                        PropertyListing.remote_id.in_(remote_ids),
                    )
                ).all()
                existing_by_remote = {row.remote_id: row for row in existing_rows}

                insert_rows: List[Dict[str, Any]] = []
                update_rows: List[PropertyListing] = []

                for row in batch:
                    existing = existing_by_remote.get(row["remote_id"])
                    if existing:
                        for key, value in row.items():
                            if key in ("remote_id", "source_portal"):
                                continue
                            setattr(existing, key, value)
                        existing.last_modified = now_ms
                        existing.server_version += 1
                        update_rows.append(existing)
                    else:
                        insert_rows.append(row)

                for row in insert_rows:
                    session.add(PropertyListing(**row))
                inserted += len(insert_rows)

                for existing in update_rows:
                    session.add(existing)
                updated += len(update_rows)

                session.commit()

        return {
            "inserted": inserted,
            "updated": updated,
            "total": len(listings_data),
        }

    async def run_full_sync(self) -> Dict[str, Any]:
        print("[RemaxRD Sync] Phase 1: Credential harvest via AdsPower (single browser session).")
        credentials = await self.harvest_credentials()

        print("[RemaxRD Sync] Phase 2: Concurrent API ingestion via curl_cffi.")
        listings = await self.fetch_all_pages(credentials)

        print("[RemaxRD Sync] Phase 3: Bulk upsert into real_estate.properties.")
        metrics = self.bulk_upsert(listings)
        metrics["source_portal"] = self.SOURCE_PORTAL
        return metrics