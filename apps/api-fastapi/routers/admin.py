"""
Admin telemetry routes (not part of public storefront contracts).

GET /api/admin/scraper-errors — unresolved RE/MAX scraper failures for ops UI.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from database import get_db_session
from models import ScraperErrorLog

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ScraperErrorLogRead(BaseModel):
    """API shape for storefront scraper error matrix."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    remote_id: Optional[str] = None
    url: Optional[str] = None
    scraper_method: str
    error_type: str
    stack_trace: str
    resolved: bool
    created_at: datetime


class ScraperErrorListResponse(BaseModel):
    data: list[ScraperErrorLogRead]
    total: int


@router.get("/scraper-errors", response_model=ScraperErrorListResponse)
def list_scraper_errors(
    session: Session = Depends(get_db_session),
    resolved: bool = Query(
        False,
        description="When false (default), return only unresolved rows for the ops dashboard",
    ),
    limit: int = Query(50, ge=1, le=200),
) -> ScraperErrorListResponse:
    """Fetch scraper error rows for the admin telemetry table."""
    query = select(ScraperErrorLog).where(ScraperErrorLog.resolved == resolved)
    query = query.order_by(ScraperErrorLog.created_at.desc()).limit(limit)
    rows = session.exec(query).all()
    payload = [ScraperErrorLogRead.model_validate(row) for row in rows]
    return ScraperErrorListResponse(data=payload, total=len(payload))