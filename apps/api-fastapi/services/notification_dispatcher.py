"""
Notification dispatcher for Stream 5 Phase 4.0.

Encapsulates the background delivery of compiled email alerts.

Strict OOP per mandatory Python OOP & Documentation Standards:
- Fully encapsulated class.
- Comprehensive module + class + method PEP 257 docstrings.
- No session-passing orchestrator creep (uses FastAPI BackgroundTasks for scheduling;
  the class itself is stateless after construction and performs the side-effect
  in a fire-and-forget task).

The dispatcher updates the delivery log (on the match row) on success or failure.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol

from fastapi import BackgroundTasks
from sqlmodel import Session

from models import NotificationDeliveryStatus, SavedSearchMatch


logger = logging.getLogger(__name__)


class EmailClient(Protocol):
    """
    Minimal interface for pluggable email providers (SES, Resend, SendGrid, etc.).

    Implementations must be async or wrapped to be non-blocking.
    """

    async def send_email(self, to: str, subject: str, html_body: str) -> bool:
        """Return True on success, False (or raise) on permanent failure."""
        ...


class NotificationDispatcher:
    """
    Schedules and executes delivery of match notification emails.

    Purpose:
        Bridge between the match engine (which creates SavedSearchMatch rows with
        delivery_status=pending) and an external email transport. Rendering is
        delegated to NotificationCompiler. Delivery is scheduled via FastAPI
        BackgroundTasks so the calling transaction (ingestion / match write) is
        never blocked.

    Lifecycle:
        - Construct with a concrete EmailClient implementation (stub for dev).
        - Call schedule() from request or job context that has access to BackgroundTasks.
        - The actual send is performed in a background task that also updates the
          SavedSearchMatch delivery fields (idempotent, with retry_count).

    Invariants:
        - Never holds a long-lived DB session itself.
        - All mutations to delivery state happen inside the background task after
          the original match commit has succeeded.
        - Retry logic is simple (increment on failure); production would add
          exponential backoff + DLQ.

    Side effects:
        - Calls email_client.send_email (network).
        - Updates SavedSearchMatch row (status, sent_at, retry_count, error_message).
    """

    def __init__(
        self,
        email_client: EmailClient,
        frontend_base_url: str = "http://localhost:3000",
    ) -> None:
        """
        Args:
            email_client: Concrete implementation of the EmailClient protocol.
            frontend_base_url: Used when links need to be generated inside the task
                (passed through to compiler if needed).
        """
        self._email_client = email_client
        self._frontend_base_url = frontend_base_url

    def schedule(
        self,
        background_tasks: BackgroundTasks,
        rendered_html: str,
        recipient: str,
        match_id: str,
        alert_title: str,
        session_factory: callable,  # callable that returns a fresh Session (for background tx)
    ) -> None:
        """
        Schedule the email delivery as a background task.

        This method returns immediately. The actual work (send + status update)
        runs after the current request/job has committed its transaction.

        Args:
            background_tasks: FastAPI BackgroundTasks instance from the current scope.
            rendered_html: Pre-compiled email body from NotificationCompiler.
            recipient: Email address (in real system would come from user profile).
            match_id: ID of the SavedSearchMatch to update on completion/failure.
            alert_title: For logging / future subject customization.
            session_factory: Factory returning a new SQLModel Session (e.g. lambda: Session(engine)).

        Side effects:
            Adds one task to background_tasks. The task will commit its own small tx
            to update delivery state.
        """
        background_tasks.add_task(
            self._deliver_and_update,
            rendered_html=rendered_html,
            recipient=recipient,
            match_id=match_id,
            alert_title=alert_title,
            session_factory=session_factory,
        )

    async def _deliver_and_update(
        self,
        rendered_html: str,
        recipient: str,
        match_id: str,
        alert_title: str,
        session_factory: callable,
    ) -> None:
        """
        Internal background task body. Updates match delivery state.

        Retries are currently handled by caller re-scheduling on failure (simple model).
        Production version would inspect retry_count and decide whether to re-queue.
        """
        session: Session | None = None
        try:
            session = session_factory()
            match = session.get(SavedSearchMatch, match_id)
            if not match:
                logger.warning("Match %s disappeared before notification dispatch", match_id)
                return

            # Idempotency guard
            if match.delivery_status != NotificationDeliveryStatus.PENDING:
                logger.info("Match %s already delivered (status=%s)", match_id, match.delivery_status)
                return

            # === STUBBED EMAIL SEND ===
            # Replace this block with real provider call (Amazon SES boto3 / resend SDK).
            # Keep the try/except perimeter exactly as shown for error capture.
            subject = f"New property match for your alert: {alert_title}"
            try:
                # Example real call (commented):
                # success = await self._email_client.send_email(recipient, subject, rendered_html)
                success = True  # STUB: always succeed in dev

                if success:
                    match.delivery_status = NotificationDeliveryStatus.SENT
                    match.sent_at = datetime.now(timezone.utc)
                    match.error_message = None
                    logger.info("Notification sent for match %s to %s", match_id, recipient)
                else:
                    raise RuntimeError("Email provider returned failure")

            except Exception as exc:  # transport, rate limit, auth, etc.
                match.retry_count += 1
                match.error_message = str(exc)[:500]  # truncate for safety
                match.delivery_status = (
                    NotificationDeliveryStatus.FAILED
                    if match.retry_count >= 3
                    else NotificationDeliveryStatus.PENDING
                )
                logger.exception(
                    "Notification delivery failed for match %s (retry=%s): %s",
                    match_id,
                    match.retry_count,
                    exc,
                )
                # In a real system you might re-add to background with delay here,
                # or let a periodic worker pick up PENDING rows with retry < N.

            session.add(match)
            session.commit()

        except Exception as exc:
            logger.exception("Fatal error in notification background task for match %s: %s", match_id, exc)
            if session:
                session.rollback()
        finally:
            if session:
                session.close()
