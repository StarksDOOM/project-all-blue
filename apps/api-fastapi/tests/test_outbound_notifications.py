"""
Tests for Phase 4.1 external email gateway integration.

Covers:
- Successful delivery path: state transitions to SENT, sent_at set.
- Failure paths: network/timeout/gateway errors increment retry_count,
  set error_message, transition to FAILED after threshold or stay PENDING.
- Uses structural mocks only (no live network calls to Resend or any gateway).
- Verifies DI and default stub behavior.

All tests adhere to the project's Python OOP, type safety, and PEP 257
standards where applicable (test helpers documented).

Do not execute any external HTTP in this test module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlmodel import Session, select

from models import NotificationDeliveryStatus, SavedSearchMatch
from services.email_client import EmailClient, StubEmailProvider
from services.notification_dispatcher import NotificationDispatcher


# Structural mocks (Protocol-compatible, no real I/O)
class MockSuccessEmailClient:
    """
    Mock EmailClient that always succeeds.

    Purpose:
        Simulate happy-path gateway acceptance for testing state mutations
        in NotificationDispatcher without external dependencies.

    Lifecycle:
        Per-test instance; used via DI into dispatcher.

    Thread-safety:
        Trivially safe (no state).

    Collaborators:
        - NotificationDispatcher (injected as the client).

    Invariants:
        - send_email always returns True.
        - Records call count for assertions.

    Parameters / Returns / Raises / Side Effects:
        See send_email.
    """

    def __init__(self) -> None:
        self.call_count = 0

    async def send_email(self, to: str, subject: str, html_body: str) -> bool:
        """
        Purpose: Simulate successful send.
        Returns: Always True.
        Side Effects: Increments call_count.
        """
        self.call_count += 1
        return True


class MockFailureEmailClient:
    """
    Mock EmailClient that always fails (simulates timeout, network error,
    or non-2xx gateway rejection).

    Purpose:
        Drive failure paths in dispatcher: retry_count increments,
        error_message captured, status -> FAILED after threshold.

    Lifecycle:
        Per-test.

    Thread-safety:
        Safe.

    Collaborators:
        - NotificationDispatcher.

    Invariants:
        - Always returns False.
        - Records last error message passed (for test inspection).

    Parameters / Returns / Raises / Side Effects:
        See send_email.
    """

    def __init__(self) -> None:
        self.call_count = 0
        self.last_error: str | None = None

    async def send_email(self, to: str, subject: str, html_body: str) -> bool:
        """
        Purpose: Simulate gateway/network failure.
        Returns: Always False.
        Side Effects: Increments call_count; sets last_error.
        """
        self.call_count += 1
        self.last_error = "simulated gateway rejection or timeout"
        return False


@pytest.fixture
def mock_success_client() -> MockSuccessEmailClient:
    """Provide a fresh success mock per test."""
    return MockSuccessEmailClient()


@pytest.fixture
def mock_failure_client() -> MockFailureEmailClient:
    """Provide a fresh failure mock per test."""
    return MockFailureEmailClient()


def _create_pending_match(db_session: Session) -> SavedSearchMatch:
    """Helper: create a minimal pending match for testing dispatch (with valid parent alert + property to satisfy FKs)."""
    from models import PropertyListing, SavedSearchAlert

    # Create parent alert
    alert = SavedSearchAlert(
        user_id="test-user-1",
        title="Test Alert for Notifications",
        filters_json={"sector": "Test"},
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # Create minimal property to satisfy property_id FK (unique remote_id per call)
    import uuid
    unique_remote = f"test-remote-{uuid.uuid4().hex[:8]}"
    prop = PropertyListing(
        remote_id=unique_remote,
        source_portal="test",
        url="https://example.com/test",
        title="Test Prop",
        price_usd=100000.0,
        province="Test Province",
        sector="Test",
        bedrooms=2,
        bathrooms=1.0,
        square_meters=80.0,
        raw_description="Test description",
    )
    db_session.add(prop)
    db_session.commit()
    db_session.refresh(prop)

    match = SavedSearchMatch(
        saved_search_alert_id=alert.id,
        property_id=prop.id,
        match_details={"snapshot": {"title": "Test Prop"}},
        delivery_status=NotificationDeliveryStatus.PENDING,
    )
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)
    return match


async def _run_dispatch(
    db_session: Session,
    match_id: str,
    client: EmailClient,
) -> None:
    """
    Helper to exercise the dispatcher with a fresh session factory.
    Simulates background task execution. Takes only id to avoid detached instance issues.
    """
    dispatcher = NotificationDispatcher(email_client=client)

    # Simulate BackgroundTasks by calling the internal directly
    # (in real use this is scheduled; here we drive it for test isolation).
    await dispatcher._deliver_and_update(  # type: ignore[attr-defined]
        rendered_html="<html>test</html>",
        recipient="test@example.com",
        match_id=match_id,
        alert_title="Test Alert",
        session_factory=lambda: db_session,  # reuse test session for simplicity
    )


def test_successful_transit_state_mutation(db_session: Session, mock_success_client: MockSuccessEmailClient) -> None:
    """
    Purpose:
        Verify that a successful send_email updates the SavedSearchMatch
        delivery fields correctly (SENT, sent_at set, error cleared, retry=0).
    """
    match = _create_pending_match(db_session)
    assert match.delivery_status == NotificationDeliveryStatus.PENDING
    assert match.retry_count == 0

    match_id = match.id  # capture before task may detach the instance

    # Run dispatch (simulated)
    import asyncio
    asyncio.run(_run_dispatch(db_session, match_id, mock_success_client))

    # Re-fetch because task may have closed/expired the original session instance
    fresh_match = db_session.exec(
        select(SavedSearchMatch).where(SavedSearchMatch.id == match_id)
    ).one()
    assert fresh_match.delivery_status == NotificationDeliveryStatus.SENT
    assert fresh_match.sent_at is not None
    assert isinstance(fresh_match.sent_at, datetime)
    assert fresh_match.error_message is None
    assert fresh_match.retry_count == 0
    assert mock_success_client.call_count == 1


def test_failed_network_timeout_conditions(db_session: Session, mock_failure_client: MockFailureEmailClient) -> None:
    """
    Purpose:
        Verify failure handling: retry_count increments, error_message set,
        status becomes FAILED after reaching threshold (3), or PENDING below.
    """
    match = _create_pending_match(db_session)
    match_id = match.id

    # First failure -> should stay PENDING, retry=1
    import asyncio
    asyncio.run(_run_dispatch(db_session, match_id, mock_failure_client))
    fresh = db_session.exec(select(SavedSearchMatch).where(SavedSearchMatch.id == match_id)).one()
    assert fresh.delivery_status == NotificationDeliveryStatus.PENDING
    assert fresh.retry_count == 1
    assert "failure" in (fresh.error_message or "").lower()
    assert mock_failure_client.call_count == 1

    # Second failure
    asyncio.run(_run_dispatch(db_session, match_id, mock_failure_client))
    fresh = db_session.exec(select(SavedSearchMatch).where(SavedSearchMatch.id == match_id)).one()
    assert fresh.delivery_status == NotificationDeliveryStatus.PENDING
    assert fresh.retry_count == 2

    # Third failure -> should go to FAILED
    asyncio.run(_run_dispatch(db_session, match_id, mock_failure_client))
    fresh = db_session.exec(select(SavedSearchMatch).where(SavedSearchMatch.id == match_id)).one()
    assert fresh.delivery_status == NotificationDeliveryStatus.FAILED
    assert fresh.retry_count == 3
    assert mock_failure_client.call_count == 3


def test_dispatcher_defaults_to_stub() -> None:
    """
    Purpose:
        Verify that NotificationDispatcher defaults to StubEmailProvider
        when no client is supplied (backward compat + test safety).
    """
    dispatcher = NotificationDispatcher()
    assert isinstance(dispatcher._email_client, StubEmailProvider)  # type: ignore[attr-defined]


def test_resend_provider_is_email_client_protocol_compliant() -> None:
    """
    Purpose:
        Structural check that ResendEmailProvider satisfies the EmailClient
        Protocol (runtime_checkable).
    """
    from services.email_client import ResendEmailProvider

    provider = ResendEmailProvider()
    assert isinstance(provider, EmailClient)  # via runtime_checkable Protocol
