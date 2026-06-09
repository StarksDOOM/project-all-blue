"""
Lead Magnet capture routes.

STREAM 6 PHASE 1.7  — Multi-Source Lead Magnet Engine (POST /capture).
STREAM 6 PHASE 1.7.1 — Internal Leads CRM Feed (GET /leads).
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session, func, select

from database import get_db_session
from models import LeadCapture
from schemas.lead import (
    LeadCaptureCreate,
    LeadCaptureListResponse,
    LeadCaptureOut,
    LeadCaptureRow,
)
from services.lead_distribution_service import LeadDistributionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.post(
    "/capture",
    response_model=LeadCaptureOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a public investor lead captured from the ROI calculator",
)
def capture_lead(
    payload: LeadCaptureCreate,
    session: Session = Depends(get_db_session),
) -> LeadCaptureOut:
    """
    Statelessly capture and persist lead parameters from a public landing page.

    Delegates persistence and outbound distribution to LeadDistributionService.
    """
    # Instantiate service
    distributor = LeadDistributionService(session)

    # Translate schema payload to LeadCapture model
    lead = LeadCapture(
        email=payload.email,
        location_slug=payload.location_slug,
        traffic_source=payload.traffic_source,
        simulated_purchase_price=payload.simulated_purchase_price,
        simulated_nightly_rate=payload.simulated_nightly_rate,
        simulated_occupancy=payload.simulated_occupancy,
        simulated_maintenance=payload.simulated_maintenance,
    )

    # Persist and distribute
    saved_lead = distributor.capture_lead(lead)

    return LeadCaptureOut(id=saved_lead.id)


@router.get(
    "",
    response_model=LeadCaptureListResponse,
    status_code=status.HTTP_200_OK,
    summary="List captured investor leads sorted newest first (internal CRM feed)",
)
def list_leads(
    session: Session = Depends(get_db_session),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum records to return"),
) -> LeadCaptureListResponse:
    """
    Return a paginated list of LeadCapture records sorted by created_at DESC.

    Intended for the internal agent dashboard CRM feed. No auth guard at this
    stage — consistent with GET /api/v1/contracts (RBAC deferred to Phase 5.0).
    """
    total: int = session.exec(select(func.count()).select_from(LeadCapture)).one()

    rows = session.exec(
        select(LeadCapture)
        .order_by(LeadCapture.created_at.desc())  # type: ignore[attr-defined]
        .offset(skip)
        .limit(limit)
    ).all()

    data = [
        LeadCaptureRow(
            id=row.id,
            email=row.email,
            location_slug=row.location_slug,
            traffic_source=row.traffic_source,
            simulated_purchase_price=row.simulated_purchase_price,
            simulated_nightly_rate=row.simulated_nightly_rate,
            simulated_occupancy=row.simulated_occupancy,
            simulated_maintenance=row.simulated_maintenance,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]

    return LeadCaptureListResponse(data=data, total=total, skip=skip, limit=limit)
