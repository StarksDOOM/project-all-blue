"""
Unit and integration tests for DocuSign Connect webhook ingestion and contract lifecycle updates.

STREAM 6 PHASE 1.1.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlmodel import Session

from models import LegalContract, PropertyListing
from services.contract_lifecycle_manager import ContractLifecycleManager
from services.docusign_webhook_validator import DocuSignWebhookValidator
from services.notification_dispatcher import NotificationDispatcher

TEST_HMAC_SECRET = "test-hmac-webhook-secret-key-12345"


@pytest.fixture(autouse=True)
def _setup_webhook_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Setup webhook environment variables for isolated testing.

    Purpose:
        Inject a static mock HMAC secret key into the environment so validation behaves predictably.
    """
    monkeypatch.setenv("DOCUSIGN_HMAC_SECRET", TEST_HMAC_SECRET)


def _generate_hmac_signature(payload_bytes: bytes, secret: str = TEST_HMAC_SECRET) -> str:
    """
    Generate mathematically valid Base64-encoded HMAC signature for a payload.
    """
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_webhook_validator_success() -> None:
    """
    Verify DocuSignWebhookValidator successfully validates valid Base64 and hex signatures.
    """
    payload = b'{"envelopeId":"env-123","status":"completed"}'
    valid_sig = _generate_hmac_signature(payload)

    validator = DocuSignWebhookValidator()
    # Should run without raising any exceptions
    validator.verify(payload, valid_sig)


def test_webhook_validator_missing_header() -> None:
    """
    Verify DocuSignWebhookValidator raises HTTP 401 when signature header is missing.
    """
    payload = b'{"envelopeId":"env-123"}'
    validator = DocuSignWebhookValidator()

    with pytest.raises(Exception) as exc_info:
        validator.verify(payload, None)

    assert getattr(exc_info.value, "status_code", None) == 401
    assert "missing" in getattr(exc_info.value, "detail", "").lower()


def test_webhook_validator_signature_mismatch() -> None:
    """
    Verify DocuSignWebhookValidator raises HTTP 401 when signature does not match.
    """
    payload = b'{"envelopeId":"env-123","status":"completed"}'
    bad_sig = "invalid-sig-base64-encoding="

    validator = DocuSignWebhookValidator()

    with pytest.raises(Exception) as exc_info:
        validator.verify(payload, bad_sig)

    assert getattr(exc_info.value, "status_code", None) == 401
    assert "invalid" in getattr(exc_info.value, "detail", "").lower()


def test_webhook_validator_no_secret_skips() -> None:
    """
    Verify DocuSignWebhookValidator skips check and does not raise error if secret is unset.
    """
    with patch("os.getenv", return_value=None):
        validator = DocuSignWebhookValidator(hmac_secret=None)
        # Should not raise even with missing signature
        validator.verify(b"{}", None)


def test_lifecycle_manager_updates_completed_to_executed(
    db_session: Session,
    seeded_property: PropertyListing,
) -> None:
    """
    Verify ContractLifecycleManager updates a contract status to 'executed' on completion.
    """
    # Arrange: Create a contract in 'sent' state
    contract = LegalContract(
        property_id=seeded_property.id,
        user_id="agent-123",
        docusign_envelope_id="env-completed-test",
        docusign_status="sent",
        version_hash="vhash123",
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)

    # Act: Process completed event
    payload = {"envelopeId": "env-completed-test", "status": "completed"}
    manager = ContractLifecycleManager()
    mock_dispatcher = MagicMock(spec=NotificationDispatcher)

    manager.process_webhook_event(
        session=db_session,
        background_tasks=BackgroundTasks(),
        event_payload=payload,
        dispatcher=mock_dispatcher,
    )

    # Assert
    db_session.expire_all()
    updated_contract = db_session.get(LegalContract, contract.id)
    assert updated_contract is not None
    assert updated_contract.docusign_status == "executed"


def test_lifecycle_manager_updates_declined(
    db_session: Session,
    seeded_property: PropertyListing,
) -> None:
    """
    Verify ContractLifecycleManager updates a contract status to 'declined' when declined.
    """
    contract = LegalContract(
        property_id=seeded_property.id,
        user_id="agent-123",
        docusign_envelope_id="env-declined-test",
        docusign_status="sent",
        version_hash="vhash123",
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)

    payload = {"envelopeId": "env-declined-test", "status": "declined"}
    manager = ContractLifecycleManager()
    mock_dispatcher = MagicMock(spec=NotificationDispatcher)

    manager.process_webhook_event(
        session=db_session,
        background_tasks=BackgroundTasks(),
        event_payload=payload,
        dispatcher=mock_dispatcher,
    )

    db_session.expire_all()
    updated_contract = db_session.get(LegalContract, contract.id)
    assert updated_contract is not None
    assert updated_contract.docusign_status == "declined"


def test_lifecycle_manager_triggers_notification_on_executed(
    db_session: Session,
    seeded_property: PropertyListing,
) -> None:
    """
    Verify ContractLifecycleManager schedules notifications on contract completion.
    """
    contract = LegalContract(
        property_id=seeded_property.id,
        user_id="agent-123",
        docusign_envelope_id="env-notify-test",
        docusign_status="sent",
        version_hash="vhash123",
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)

    payload = {"envelopeId": "env-notify-test", "status": "completed"}
    manager = ContractLifecycleManager()
    mock_dispatcher = MagicMock(spec=NotificationDispatcher)
    background_tasks = BackgroundTasks()

    manager.process_webhook_event(
        session=db_session,
        background_tasks=background_tasks,
        event_payload=payload,
        dispatcher=mock_dispatcher,
    )

    # Check that dispatcher notification calls were scheduled
    assert mock_dispatcher.dispatch_contract_executed.call_count == 2
    # Verify it notified the agent and the buyer
    calls = mock_dispatcher.dispatch_contract_executed.call_args_list
    assert calls[0][1]["recipient"] == seeded_property.agent_email or "agent@example.com"
    assert calls[1][1]["recipient"] == "cliente.comprador@example.com"


def test_webhook_endpoint_success(
    api_client: TestClient,
    db_session: Session,
    seeded_property: PropertyListing,
) -> None:
    """
    Verify POST /api/v1/contracts/webhooks/docusign validates signature and updates contract status.
    """
    contract = LegalContract(
        property_id=seeded_property.id,
        user_id="agent-123",
        docusign_envelope_id="env-endpoint-success",
        docusign_status="sent",
        version_hash="vhash123",
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)

    payload = {"envelopeId": "env-endpoint-success", "status": "completed"}
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = _generate_hmac_signature(payload_bytes)

    headers = {
        "Content-Type": "application/json",
        "X-DocuSign-Signature-1": sig,
    }

    response = api_client.post(
        "/api/v1/contracts/webhooks/docusign",
        content=payload_bytes,
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify database update occurred
    db_session.expire_all()
    updated = db_session.get(LegalContract, contract.id)
    assert updated is not None
    assert updated.docusign_status == "executed"


def test_webhook_endpoint_invalid_signature(
    api_client: TestClient,
    db_session: Session,
    seeded_property: PropertyListing,
) -> None:
    """
    Verify POST /api/v1/contracts/webhooks/docusign blocks request if HMAC signature is invalid.
    """
    contract = LegalContract(
        property_id=seeded_property.id,
        user_id="agent-123",
        docusign_envelope_id="env-endpoint-fail",
        docusign_status="sent",
        version_hash="vhash123",
    )
    db_session.add(contract)
    db_session.commit()

    payload = {"envelopeId": "env-endpoint-fail", "status": "completed"}
    payload_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-DocuSign-Signature-1": "invalid-HMAC-sig-value",
    }

    response = api_client.post(
        "/api/v1/contracts/webhooks/docusign",
        content=payload_bytes,
        headers=headers,
    )

    assert response.status_code == 401


def test_webhook_endpoint_invalid_json(api_client: TestClient) -> None:
    """
    Verify POST /api/v1/contracts/webhooks/docusign returns 400 Bad Request on malformed JSON payload.
    """
    bad_payload = b"not-a-valid-json-string"
    sig = _generate_hmac_signature(bad_payload)

    headers = {
        "Content-Type": "application/json",
        "X-DocuSign-Signature-1": sig,
    }

    response = api_client.post(
        "/api/v1/contracts/webhooks/docusign",
        content=bad_payload,
        headers=headers,
    )

    assert response.status_code == 400
    assert "malformed" in response.json()["detail"].lower()
