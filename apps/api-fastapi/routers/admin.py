"""
Admin telemetry routes (not part of public storefront contracts).

GET /api/admin/scraper-errors — unresolved RE/MAX scraper failures for ops UI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from database import get_db_session
from models import ScraperErrorLog
from services.auth import RoleChecker, UserRole
from services.sync_service import IngestionOrchestrator

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


# =============================================================================
# STREAM 5 PHASE 5.1: Admin-only scraper run override (POST /api/v1/scrapers/run)
# =============================================================================

# Strict RBAC: only ADMIN may trigger on-demand syncs (non-admins -> 403 via RoleChecker)
admin_scraper_checker = RoleChecker(allowed_roles=[UserRole.ADMIN])

# Dedicated router so we expose exactly /api/v1/scrapers/run while keeping the
# existing /api/admin/* routes on the original admin router instance.
scraper_admin_router = APIRouter(prefix="/api/v1/scrapers", tags=["admin", "scrapers"])


class ScraperRunReceipt(BaseModel):
    """Execution receipt returned immediately on 202 for the admin trigger."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    initiated_at: str
    task: str
    message: str


@scraper_admin_router.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(admin_scraper_checker)],
    response_model=ScraperRunReceipt,
)
def run_scraper_override(
    background_tasks: BackgroundTasks,
) -> ScraperRunReceipt:
    """
    Admin-only on-demand execution trigger for the ingestion pipeline.

    Purpose:
        Allow administrative operators to force an immediate full scrape/sync
        cycle outside the normal scheduler (e.g., for hotfixes, data refresh,
        or after config changes). Strictly guarded so only admins can invoke;
        lower roles receive 403 Forbidden via the RoleChecker dependency.

    Lifecycle:
        - Registered on scraper_admin_router (mounted in main.py).
        - FastAPI resolves BackgroundTasks and the RoleChecker (which calls
          get_current_user internally).
        - On success: schedules the work and returns 202 + receipt synchronously.
        - The actual IngestionOrchestrator work runs in the background worker
          after the response is sent to client; no request resources are held.

    Thread-safety:
        The handler itself is synchronous and stateless. BackgroundTasks
        scheduling is thread-safe in FastAPI/Starlette. The delegated
        trigger_sync_cycle uses its own DB session.

    Collaborators:
        - RoleChecker + UserRole (enforces ADMIN only).
        - BackgroundTasks (FastAPI built-in for post-response dispatch).
        - IngestionOrchestrator.trigger_sync_cycle (the named 5.1 entrypoint).
        - ScraperRunReceipt (Pydantic response model for the receipt shape).
        - main.py (includes the scraper_admin_router to bind the path).

    Invariants:
        - Never executes the sync work in the request thread (always via
          add_task).
        - Returns 202 immediately; client must not assume the sync completed.
        - Tenant/auth already handled upstream by RoleChecker (no user_id
          scoping needed for global admin op).
        - Uses the primary "remaxrd" portal (per current operational default).

    Parameters:
        background_tasks (BackgroundTasks): Injected by FastAPI; used to
            schedule the out-of-process trigger.

    Returns:
        ScraperRunReceipt: JSON with status="accepted", ISO initiated_at,
            task identifier, and human message. HTTP 202.

    Raises:
        HTTPException 403: If the caller's JWT role is not ADMIN (enforced by
            the dependencies=[Depends(admin_scraper_checker)] before handler
            body runs).

    Side Effects:
        - Registers exactly one background task (the sync cycle).
        - No DB writes in the handler path itself (the background task does
          all the ingestion writes, job rows, and alert match evaluation).
        - Structured logging occurs inside the orchestrator (not here).
    """
    initiated_at = datetime.now(timezone.utc).isoformat()

    # Fire the orchestrator using the Phase 5.1 named trigger (delegates to
    # run_sync_for_portal which owns its engine Session and full lifecycle).
    # "remaxrd" is the primary/only active driver for admin overrides in this phase.
    background_tasks.add_task(
        IngestionOrchestrator.trigger_sync_cycle, "remaxrd"
    )

    return ScraperRunReceipt(
        status="accepted",
        initiated_at=initiated_at,
        task="ingestion_sync_remaxrd",
        message="Scraper sync cycle scheduled via background task",
    )
