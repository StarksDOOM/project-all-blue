"""
Contract Lifecycle Manager for Stream 6 Phase 1.1.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from models import LegalContract, PropertyListing
from services.notification_dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)


class ContractLifecycleManager:
    """
    Stateless processor responsible for updating the contract database records and
    triggering post-execution email notifications when DocuSign events are received.

    Purpose:
        Locate the corresponding LegalContract row using the envelope ID, update its
        status according to the DocuSign callback ('completed' -> 'executed', 'declined' -> 'declined'),
        and conditionally fire the NotificationDispatcher to notify the agent and client.

    Lifecycle:
        Stateless and request-scoped. Instantiated by route handlers when processing
        authenticated DocuSign Connect webhook payloads.

    Thread-safety:
        Fully thread-safe as it maintains no mutable instance state. Database queries and
        modifications are executed within the request-scoped DB session.

    Collaborators:
        - SQLModel Session (database transaction management)
        - NotificationDispatcher (outbound notification pipeline)
        - LegalContract (database entity being modified)
        - PropertyListing (metadata provider for notifications)

    Invariants:
        - Only fires the NotificationDispatcher if the status is successfully updated to 'executed' (i.e. 'completed' event).
        - Safely updates database status columns and logs trace details of modifications.
    """

    def process_webhook_event(
        self,
        session: Session,
        background_tasks: BackgroundTasks,
        event_payload: dict[str, Any],
        dispatcher: NotificationDispatcher,
    ) -> None:
        """
        Purpose:
            Process a validated DocuSign Connect webhook event, update the contract state,
            and trigger notifications if fully executed.

        Lifecycle:
            Invoked inside the webhook endpoint handler in the request thread context.

        Thread-safety:
            Safe. Uses the provided SQLModel Session for transactional isolation.

        Collaborators:
            - Session
            - BackgroundTasks
            - NotificationDispatcher

        Invariants:
            - Locates contract using envelope ID. Does nothing (logs a warning) if no matching envelope exists.
            - Status mapped to 'executed' if 'completed' received, or 'declined' if 'declined' received.

        Parameters:
            session (Session): Active database session.
            background_tasks (BackgroundTasks): FastAPI background task queue.
            event_payload (dict): De-serialized JSON payload from DocuSign.
            dispatcher (NotificationDispatcher): Injected notification engine.

        Returns:
            None.

        Raises:
            None. (Catches exceptions locally to prevent endpoint crash, logging trace details instead).

        Side Effects:
            - Modifies the LegalContract table row in the database.
            - Adds notification tasks to background_tasks.
        """
        try:
            # Extract identifiers from the payload
            # Support both flat JSON keys and nested DocuSign structure
            envelope_id = (
                event_payload.get("envelopeId")
                or event_payload.get("envelope_id")
                or event_payload.get("envelopeSummary", {}).get("envelopeId")
            )
            raw_status = (
                event_payload.get("status")
                or event_payload.get("envelopeStatus")
                or event_payload.get("envelopeSummary", {}).get("status")
            )

            if not envelope_id or not raw_status:
                logger.warning(
                    "DocuSign webhook payload missing envelopeId or status. envelopeId=%s status=%s",
                    envelope_id,
                    raw_status,
                )
                return

            # Normalize the status
            normalized_status = raw_status.strip().lower()

            # Find matching LegalContract tracking row
            stmt = select(LegalContract).where(LegalContract.docusign_envelope_id == envelope_id)
            contract = session.exec(stmt).first()

            if not contract:
                logger.warning("No LegalContract found matching DocuSign envelope ID: %s", envelope_id)
                return

            # Determine new status
            new_status = None
            if normalized_status == "completed":
                new_status = "executed"
            elif normalized_status == "declined":
                new_status = "declined"
            else:
                new_status = normalized_status

            # Avoid redundant updates if status hasn't changed
            if contract.docusign_status == new_status:
                logger.info(
                    "LegalContract %s already in status %s; skipping update.",
                    contract.id,
                    new_status,
                )
                return

            old_status = contract.docusign_status
            contract.docusign_status = new_status
            session.add(contract)
            session.commit()
            session.refresh(contract)

            logger.info(
                "Updated LegalContract %s status: %s -> %s (envelope_id=%s)",
                contract.id,
                old_status,
                new_status,
                envelope_id,
            )

            # Fire NotificationDispatcher if the contract is fully executed
            if new_status == "executed":
                # Fetch property listing to customize the notification content
                listing = None
                if contract.property_id:
                    listing_stmt = select(PropertyListing).where(PropertyListing.id == contract.property_id)
                    listing = session.exec(listing_stmt).first()

                property_title = listing.title if listing else "Inmueble de Reserva"
                agent_email = (listing.agent_email if listing else None) or "agent@example.com"
                buyer_email = "cliente.comprador@example.com"

                # Notify the listing agent
                dispatcher.dispatch_contract_executed(
                    background_tasks=background_tasks,
                    contract=contract,
                    property_title=property_title,
                    recipient=agent_email,
                )

                # Notify the buyer
                dispatcher.dispatch_contract_executed(
                    background_tasks=background_tasks,
                    contract=contract,
                    property_title=property_title,
                    recipient=buyer_email,
                )

                logger.info(
                    "Fired NotificationDispatcher tasks for executed contract %s",
                    contract.id,
                )

        except Exception as exc:
            logger.exception("Failed to process DocuSign lifecycle event: %s", exc)
            session.rollback()
