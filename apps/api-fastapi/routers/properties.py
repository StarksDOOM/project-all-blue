"""
Property listing HTTP routes.

GET  /api/v1/properties        — paginated inventory for storefront
POST /api/v1/properties/trigger-crawl — queue OOP ingestion (202 Accepted)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlmodel import Session, func, select

from database import get_db_session
from models import PropertyListing
from scrapers.driver_factory import DriverFactory
from scrapers.drivers.realtor import RealtorDriver
from services.sync_service import IngestionOrchestrator

router = APIRouter(prefix="/api/v1/properties", tags=["properties"])


@router.get("")
def list_properties(
    session: Session = Depends(get_db_session),
    page: int = Query(1, ge=1, description="1-based page index"),
    page_size: int = Query(20, ge=1, le=100, alias="limit", description="Rows per page"),
    source_portal: Optional[str] = Query(None, description="Filter by portal key e.g. remaxrd"),
    sector: Optional[str] = Query(None, description="Exact sector match"),
):
    """
    Return paginated PropertyListing rows for the Next.js storefront.

    Excludes soft-deleted rows (deleted_at IS NULL).
    """
    query = select(PropertyListing).where(PropertyListing.deleted_at == None)

    if source_portal:
        query = query.where(PropertyListing.source_portal == source_portal.strip().lower())
    if sector:
        query = query.where(PropertyListing.sector == sector)

    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()
    offset = (page - 1) * page_size
    rows = session.exec(query.offset(offset).limit(page_size)).all()

    return {
        "metadata": {
            "total": total,
            "page": page,
            "limit": page_size,
            "pages": (total + page_size - 1) // page_size if page_size else 0,
        },
        "data": rows,
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