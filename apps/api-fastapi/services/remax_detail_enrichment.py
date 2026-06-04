"""
Apply RE/MAX storefront URL detail scrape results to PropertyListing rows.

List ingestion (RemaxRdDriver) only uses the paginated API — titles, descriptions,
and prices can diverge from the live listing page. This module re-scrapes each row's
``url`` via ``scrape_remax_property_detail`` and merges portal-ground-truth fields
before the storefront reads them.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlmodel import Session, select

from models import PropertyListing
from observability.scraper_errors import report_scraper_error, scraper_error_scope
from scrapers.remax_detail_scraper import (
    RemaxDetailScrapeError,
    _fetch_api_detail,
    build_remax_portal_url,
    is_canonical_remax_url,
    remax_portal_detail_url,
    scrape_remax_property_detail,
)

REMAX_WEB_BASE = "https://www.remaxrd.com"
from scrapers.utils.normalization import (
    hydrate_listing_bathrooms,
    resolve_bathroom_count_from_specs,
    resolve_prices_usd_dop,
    safe_float,
    safe_int,
    title_case_label,
)

logger = logging.getLogger(__name__)

REMAX_PORTAL = "remaxrd"
ENRICH_SLEEP_SECONDS = 0.35


def apply_detail_payload_to_listing(
    listing: PropertyListing,
    detail: dict[str, Any],
) -> PropertyListing:
    """Merge scraper output into an in-memory PropertyListing (mutates listing)."""
    with scraper_error_scope(
        "enrichment",
        remote_id=str(listing.remote_id),
        url=str(listing.url or ""),
        swallow=False,
    ):
        return _apply_detail_payload_inner(listing, detail)
    return listing


def _apply_detail_payload_inner(
    listing: PropertyListing,
    detail: dict[str, Any],
) -> PropertyListing:
    specs = detail.get("specs") or {}
    # Portal list price/currency exactly as returned by RE/MAX API / __NEXT_DATA__ (no inference).
    currency_iso = str(detail.get("currency") or "USD").upper()
    portal_price_raw = detail.get("price")
    list_amount = safe_float(portal_price_raw, default=0.0)
    price_usd, price_dop = resolve_prices_usd_dop(portal_price_raw, currency_iso)

    portal_title = (detail.get("title") or "").strip()
    if portal_title:
        listing.title = portal_title

    scraped_id = str(detail.get("property_id") or listing.remote_id).strip()
    city_label = (detail.get("specs") or {}).get("city") or listing.province
    listing.url = remax_portal_detail_url(scraped_id, str(city_label or ""))

    listing.listing_currency = currency_iso
    if list_amount > 0:
        listing.list_price = list_amount
    if price_usd > 0 or price_dop:
        listing.price_usd = price_usd
        listing.price_dop = price_dop

    image_list = detail.get("image_list")
    if isinstance(image_list, list) and image_list:
        urls = [str(url).strip() for url in image_list if url]
        if urls:
            listing.image_urls = urls[:32]

    agent_name = (detail.get("agent_name") or "").strip()
    if agent_name:
        listing.agent_name = agent_name
    agent_phone = (detail.get("agent_phone") or "").strip()
    if agent_phone:
        listing.agent_phone = agent_phone
    agent_email = (detail.get("agent_email") or "").strip()
    if agent_email:
        listing.agent_email = agent_email
    whatsapp = (detail.get("whatsapp_link") or "").strip()
    if whatsapp:
        listing.agent_whatsapp = whatsapp
    agency = (detail.get("agent_agency") or "").strip()
    if agency:
        listing.agent_agency = agency

    sector = specs.get("sector")
    if sector:
        listing.sector = title_case_label(sector, listing.sector)

    city = specs.get("city")
    if city:
        listing.province = title_case_label(city, listing.province)

    bedrooms = specs.get("bedrooms")
    if bedrooms is not None:
        listing.bedrooms = safe_int(bedrooms, default=listing.bedrooms)

    description = (detail.get("description_text") or "").strip()

    sqm_construction = safe_float(specs.get("sqm_construction"), default=0.0)
    sqm_land = safe_float(specs.get("sqm_land"), default=0.0)
    if sqm_land > 0:
        listing.sqm_land = sqm_land
    square_meters = sqm_construction if sqm_construction > 0 else sqm_land
    if square_meters > 0:
        listing.square_meters = square_meters

    business_type = str(specs.get("business_type") or "").strip()
    realstate_type = str(specs.get("realstate_type") or "").strip()
    status = str(specs.get("status") or "").strip()

    if status:
        listing.is_active = status.lower() == "disponible"

    business_slug = business_type.lower() if business_type else ""
    meta_parts = [
        realstate_type or "Property",
        f"business_type={business_slug}" if business_slug else business_type,
        f"{listing.sector}, {listing.province}",
        f"currency={currency_iso}",
    ]
    if status:
        meta_parts.append(f"status={status}")
    meta_header = " | ".join(part for part in meta_parts if part)

    if description:
        listing.raw_description = f"{meta_header}\n\n{description}"[:12000]
    elif meta_header:
        listing.raw_description = meta_header

    listing.bathrooms = resolve_bathroom_count_from_specs(
        specs,
        description_text=description or None,
        raw_description=listing.raw_description,
    )

    return listing


def enrich_remax_listing_from_url(
    listing: PropertyListing,
    *,
    city_slug: str | None = None,
) -> PropertyListing:
    """
    Scrape ``listing.url`` and merge portal detail into the listing object.

    Raises:
        RemaxDetailScrapeError: When scrape yields no usable property node.
    """
    if not listing.url:
        raise RemaxDetailScrapeError(f"Listing {listing.remote_id} has no url")

    detail = scrape_remax_property_detail(str(listing.url), city_slug=city_slug)
    scraped_id = str(detail.get("property_id") or "").strip()
    if scraped_id and scraped_id != str(listing.remote_id):
        logger.warning(
            "Detail scrape id mismatch remote_id=%s scraped_id=%s url=%s",
            listing.remote_id,
            scraped_id,
            listing.url,
        )

    return apply_detail_payload_to_listing(listing, detail)


def _load_db_listing(session: Session, listing: PropertyListing) -> PropertyListing:
    """Resolve the persisted row — upserted listings may have a different Blu ``id`` in memory."""
    db_row = session.exec(
        select(PropertyListing).where(
            PropertyListing.source_portal == listing.source_portal,
            PropertyListing.remote_id == listing.remote_id,
            PropertyListing.deleted_at == None,
        )
    ).first()
    if db_row is None:
        raise RemaxDetailScrapeError(
            f"No DB row for {listing.source_portal}/{listing.remote_id} to enrich"
        )
    return db_row


def resolve_remax_portal_url(remote_id: str, portal_url: str | None = None) -> str:
    """Build a Spanish storefront URL with ``?city=`` when only ``remote_id`` is known."""
    if portal_url and portal_url.strip():
        return portal_url.strip()
    record = _fetch_api_detail(remote_id)
    if not record:
        raise RemaxDetailScrapeError(f"No RE/MAX API record for remote_id={remote_id}")
    slug = str(record.get("slug") or f"property-{remote_id}").strip("/")
    return build_remax_portal_url(slug, str(record.get("city") or ""), remote_id=remote_id)


def import_remax_listing_from_portal(
    session: Session,
    remote_id: str,
    *,
    portal_url: str | None = None,
) -> PropertyListing:
    """
    Upsert a RE/MAX listing from live URL scrape (for rows missing from list sync).

    Uses ``portal_url`` when provided; otherwise resolves slug/city via public API.
    """
    remote_key = str(remote_id).strip()
    existing = session.exec(
        select(PropertyListing).where(
            PropertyListing.source_portal == REMAX_PORTAL,
            PropertyListing.remote_id == remote_key,
            PropertyListing.deleted_at == None,
        )
    ).first()

    scrape_target = resolve_remax_portal_url(remote_key, portal_url)
    detail = scrape_remax_property_detail(scrape_target)

    if existing is None:
        existing = PropertyListing(
            remote_id=remote_key,
            source_portal=REMAX_PORTAL,
            url=scrape_target,
            title="",
            price_usd=0.0,
            price_dop=None,
            province="Unknown",
            sector="Unknown",
            bedrooms=0,
            bathrooms=0.0,
            square_meters=0.0,
            raw_description="",
            is_active=True,
        )

    apply_detail_payload_to_listing(existing, detail)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def enrich_remax_listing(
    session: Session,
    listing: PropertyListing,
    *,
    persist: bool = True,
    portal_url: str | None = None,
) -> PropertyListing:
    """Scrape URL detail and optionally persist to Postgres."""
    scrape_target = (portal_url or "").strip()
    if not scrape_target:
        stored_url = str(listing.url or "").strip()
        if is_canonical_remax_url(stored_url):
            scrape_target = stored_url
        else:
            scrape_target = resolve_remax_portal_url(str(listing.remote_id), portal_url)

    detail = scrape_remax_property_detail(scrape_target)
    scraped_id = str(detail.get("property_id") or "").strip()
    if scraped_id and scraped_id != str(listing.remote_id):
        logger.warning(
            "Detail scrape id mismatch remote_id=%s scraped_id=%s url=%s",
            listing.remote_id,
            scraped_id,
            listing.url,
        )

    if not persist:
        return apply_detail_payload_to_listing(listing, detail)

    db_row = _load_db_listing(session, listing)
    apply_detail_payload_to_listing(db_row, detail)
    session.add(db_row)
    session.commit()
    session.refresh(db_row)
    return db_row


def enrich_remax_listings_batch(
    session: Session,
    listings: list[PropertyListing],
    *,
    sleep_seconds: float = ENRICH_SLEEP_SECONDS,
) -> dict[str, int]:
    """
    Enrich many rows after list sync. Failures are logged; sync still completes.

    Returns:
        Counts: attempted, enriched, failed.
    """
    attempted = 0
    enriched = 0
    failed = 0

    for listing in listings:
        if listing.source_portal != REMAX_PORTAL:
            continue
        attempted += 1
        try:
            enrich_remax_listing(session, listing, persist=True)
            enriched += 1
        except Exception as exc:
            failed += 1
            session.rollback()
            report_scraper_error(
                exc,
                scraper_method="enrichment",
                remote_id=str(listing.remote_id),
                url=str(listing.url or ""),
            )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return {"attempted": attempted, "enriched": enriched, "failed": failed}