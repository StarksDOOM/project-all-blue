"""
Property listing HTTP routes.

GET  /api/v1/properties              — paginated inventory for storefront
GET  /api/v1/properties/{property_id}  — single property (id or remote_id)
POST /api/v1/properties/trigger-crawl — queue OOP ingestion (202 Accepted)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlmodel import Session, select

from database import get_db_session
from models import PropertyListing
from schemas.property_detail import PropertyDetailResponse
from schemas.property_filters import PropertyFilterParams, PropertyTypeFilter
from services.property_list_service import list_properties_paginated
from scrapers.driver_factory import DriverFactory
from scrapers.drivers.realtor import RealtorDriver
from scrapers.utils.normalization import hydrate_listing_bathrooms
from services.remax_detail_enrichment import (
    REMAX_PORTAL,
    enrich_remax_listing,
    import_remax_listing_from_portal,
)
from services.sync_service import IngestionOrchestrator

router = APIRouter(prefix="/api/v1/properties", tags=["properties"])


def _build_list_filters(
    source_portal: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, alias="q"),
    price_min: Optional[float] = Query(None, ge=0),
    price_max: Optional[float] = Query(None, ge=0),
    bedrooms_min: Optional[int] = Query(None, ge=0, le=20, alias="beds"),
    bathrooms_min: Optional[float] = Query(None, ge=0, le=20, alias="baths"),
    property_type: Optional[PropertyTypeFilter] = Query(None, alias="type"),
    agency: Optional[str] = Query(None),
) -> PropertyFilterParams:
    try:
        return PropertyFilterParams(
            source_portal=source_portal,
            sector=sector,
            keyword=keyword,
            price_min=price_min,
            price_max=price_max,
            bedrooms_min=bedrooms_min,
            bathrooms_min=bathrooms_min,
            property_type=property_type,
            agency=agency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_property_asset(session: Session, property_id: str) -> PropertyListing:
    """
    Resolve a property by internal primary key or portal remote_id.

    Lookup order (non-deleted rows only):
      1. ``id`` — Blu string PK (e.g. ``#BLU-A1B2C3D4``)
      2. ``remote_id`` — portal-native id (e.g. ``222574``); numeric path segments use this
    """
    key = str(property_id).strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property asset not found",
        )

    listing = session.exec(
        select(PropertyListing).where(
            PropertyListing.deleted_at == None,
            or_(PropertyListing.id == key, PropertyListing.remote_id == key),
        )
    ).first()

    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property asset not found",
        )

    return listing


@router.get("/{property_id}")
def get_property_detail(
    property_id: str,
    session: Session = Depends(get_db_session),
    refresh_from_portal: bool = Query(
        True,
        description="Re-scrape listing.url for RE/MAX rows before returning (portal ground truth)",
    ),
    portal_url: Optional[str] = Query(
        None,
        description="Canonical RE/MAX listing URL (e.g. Spanish slug + ?city=) when DB row is missing or stale",
    ),
) -> PropertyDetailResponse:
    """
    Return one non-deleted PropertyListing row with full field payload (no truncation).

    Accepts internal ``id`` (Blu string PK, e.g. #BLU-…) or portal ``remote_id`` (e.g. 222574).

    For ``remaxrd``, when ``refresh_from_portal=true`` (default), the handler re-scrapes
    the portal URL and persists enriched fields. If the row is missing but ``remote_id`` is
    numeric, it is imported live from RE/MAX (optional ``portal_url`` overrides discovery).
    """
    key = str(property_id).strip()
    listing: PropertyListing | None = None

    try:
        listing = _resolve_property_asset(session, property_id)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND or not key.isdigit():
            raise
        listing = import_remax_listing_from_portal(
            session,
            key,
            portal_url=portal_url,
        )
        return PropertyDetailResponse.from_listing(hydrate_listing_bathrooms(listing))

    portal_refresh_failed = False
    portal_refresh_message: str | None = None

    if refresh_from_portal and listing.source_portal == REMAX_PORTAL:
        try:
            listing = enrich_remax_listing(
                session,
                listing,
                persist=True,
                portal_url=portal_url,
            )
        except Exception as exc:
            portal_refresh_failed = True
            portal_refresh_message = (
                "Live portal sync failed; displaying last known data."
            )
            session.refresh(listing)

    listing = hydrate_listing_bathrooms(listing)

    return PropertyDetailResponse.from_listing(
        listing,
        portal_refresh_failed=portal_refresh_failed,
        portal_refresh_message=portal_refresh_message,
    )


@router.get("")
def list_properties(
    session: Session = Depends(get_db_session),
    page: int = Query(1, ge=1, description="1-based page index"),
    page_size: int = Query(20, ge=1, le=100, alias="limit", description="Rows per page"),
    include_total: bool = Query(
        True,
        description="When false, skip COUNT(*) and set has_next via limit+1 (fast pagination)",
    ),
    filters: PropertyFilterParams = Depends(_build_list_filters),
):
    """
    Return paginated PropertyListing rows for the Next.js storefront.

    Excludes soft-deleted rows (deleted_at IS NULL). Facets via PropertyFilterParams.
    """
    result = list_properties_paginated(
        session,
        filters=filters,
        page=page,
        page_size=page_size,
        include_total=include_total,
    )
    return {
        "metadata": {
            "total": result.total,
            "page": result.page,
            "limit": result.limit,
            "pages": result.pages,
            "has_next": result.has_next,
        },
        "data": result.rows,
    }


@router.post("/trigger-crawl", status_code=status.HTTP_202_ACCEPTED)
async def trigger_crawl(
    background_tasks: BackgroundTasks,
    source_portal: str = Query(..., description="Portal driver key (e.g. remaxrd)"),
    session: Session = Depends(get_db_session),
):
    """
    Validate portal synchronously, then schedule ingestion in the background.

    Status codes:
        202 — remaxrd queued
        400 — unknown portal (DriverFactory ValueError)
        501 — realtor stub (not implemented)
    """
    factory = DriverFactory()
    try:
        # Uses request session only for validation — not for the long-running sync.
        driver = factory.create_driver(source_portal, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if isinstance(driver, RealtorDriver):
        raise HTTPException(
            status_code=501,
            detail="Driver 'realtor' pending implementation",
        )

    portal_key = source_portal.strip().lower()
    # Dedicated Session(engine) opened inside run_sync_for_portal after response is sent.
    background_tasks.add_task(IngestionOrchestrator.run_sync_for_portal, portal_key)
    return JSONResponse(
        status_code=202,
        content={"message": "Sync job initialized successfully"},
    )