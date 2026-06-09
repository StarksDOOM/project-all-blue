"""
Lead Magnet capture routes.

STREAM 6 PHASE 1.7 — Multi-Source Lead Magnet Engine.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from database import get_db_session
from models import LeadCapture
from schemas.lead import LeadCaptureCreate, LeadCaptureOut
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
