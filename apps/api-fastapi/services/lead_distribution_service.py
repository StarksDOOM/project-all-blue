"""
Lead Distribution Service for persisting captured leads and orchestrating delivery.

STREAM 6 PHASE 1.7 — Multi-Source Lead Magnet Engine.
"""

from __future__ import annotations

import logging
from sqlmodel import Session
from models import LeadCapture

logger = logging.getLogger(__name__)


class LeadDistributionService:
    """
    Handles persistence of LeadCapture entities and coordinates outbound syndication.

    This service encapsulates database insertion and hooks for future external CRM,
    webhooks (e.g., Loops, Hubspot), or email notification platforms.
    """

    def __init__(self, session: Session) -> None:
        """
        Initialize the LeadDistributionService.

        Parameters:
            session : Session
                The database session for transaction scope.
        """
        self.session = session

    def capture_lead(self, lead: LeadCapture) -> LeadCapture:
        """
        Persist a LeadCapture record to Postgres and trigger distribution integrations.

        Parameters:
            lead : LeadCapture
                The lead capture transient model instance to persist.

        Returns:
            LeadCapture
                The saved LeadCapture entity populated with ID and timestamp.
        """
        logger.info(
            "Capturing lead for email=%s location=%s source=%s",
            lead.email,
            lead.location_slug,
            lead.traffic_source,
        )

        self.session.add(lead)
        self.session.commit()
        self.session.refresh(lead)

        # Trigger future integrations asynchronously
        self._dispatch_integrations(lead)

        return lead

    def _dispatch_integrations(self, lead: LeadCapture) -> None:
        """
        Stub method for outbound syndication (e.g. CRM webhooks, Resend dispatch).

        Parameters:
            lead : LeadCapture
                The persisted LeadCapture record.
        """
        logger.info(
            "Stub dispatching lead_id=%s to external CRM/delivery integrations",
            lead.id,
        )
        # Future integrations (e.g. Loops, Resend, or Webhooks) will be placed here.
        pass
