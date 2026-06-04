"""DocuSign JWT, envelope, embedded signing, and Connect webhook tests."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from config.docusign_settings import get_docusign_settings
from models import LegalContract, TransactionSessionStatus
from services.docusign.webhook import (
    envelope_id_from_event,
    envelope_status_from_event,
    verify_connect_hmac,
)
from tests.db_cleanup import delete_transaction_cascade


@pytest.fixture(autouse=True)
def _docusign_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUSIGN_PROVIDER", "docusign")
    monkeypatch.setenv("DOCUSIGN_USER_ID", "6da28b5f-7e26-4249-b95e-9124c25ee4f8")
    monkeypatch.setenv("DOCUSIGN_API_ACCOUNT_ID", "e1fca701-58e9-4190-ac60-2e1d9843cc10")
    monkeypatch.setenv("DOCUSIGN_INTEGRATION_KEY", "ea0f68ac-a0e6-4100-9dfb-baa9916143a2")
    monkeypatch.setenv("DOCUSIGN_BASE_URL", "https://demo.docusign.net/restapi")
    monkeypatch.setenv("DOCUSIGN_WEBHOOK_SECRET", "test-connect-secret")
    get_docusign_settings.cache_clear()


@pytest.fixture(autouse=True)
def mock_docusign_client():
    """Provides an isolated, fully mocked representation of the DocuSign API SDK layer.
    Matches the strict test-isolation pattern from Phase 4.1 (e.g. email mocks).
    This prevents any live network calls to DocuSign even if a high-level patch is missed.
    """
    with patch("services.docusign.client.DocusignClient") as mock_class:
        instance = mock_class.return_value
        # Mock the authorized client to prevent any real network / JWT calls
        mock_api_client = MagicMock()
        instance.authorized_api_client.return_value = mock_api_client
        yield instance


def test_signing_config_reports_docusign(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/signing/config")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "docusign"
    assert body["docusign_configured"] is True


def test_webhook_hmac_verification() -> None:
    secret = "test-connect-secret"
    payload = b'{"envelopeId":"env-1","status":"completed"}'
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_connect_hmac(payload, digest) is True
    assert verify_connect_hmac(payload, "bad") is False


def test_parse_connect_envelope_fields() -> None:
    event = {"envelopeId": "abc-123", "status": "completed"}
    assert envelope_id_from_event(event) == "abc-123"
    assert envelope_status_from_event(event) == "completed"


@patch("services.docusign_orchestrator.create_envelope_from_pdf", return_value="env-mock-001")
def test_create_docusign_envelope_persists_id(
    _mock_create: MagicMock,
    mock_docusign_client,
    api_client: TestClient,
    seeded_property,
    db_session: Session,
) -> None:
    transaction_id = _create_and_pdf(api_client, seeded_property.remote_id)

    response = api_client.post(f"/api/v1/transactions/{transaction_id}/docusign/envelope")
    assert response.status_code == 201
    body = response.json()
    assert body["envelope_id"] == "env-mock-001"
    assert body["docusign_status"] == "sent"

    contract = db_session.exec(
        select(LegalContract).where(LegalContract.transaction_session_id == transaction_id)
    ).first()
    assert contract is not None
    assert contract.docusign_envelope_id == "env-mock-001"

    duplicate = api_client.post(f"/api/v1/transactions/{transaction_id}/docusign/envelope")
    assert duplicate.status_code == 409

    from database import engine

    with Session(engine) as cleanup:
        delete_transaction_cascade(cleanup, transaction_id)


@patch(
    "services.docusign_orchestrator.create_embedded_signing_url",
    return_value="https://demo.docusign.net/Mocking/SigningCeremony",
)
@patch("services.docusign_orchestrator.create_envelope_from_pdf", return_value="env-mock-002")
def test_embedded_signing_url_endpoint(
    _mock_env: MagicMock,
    _mock_url: MagicMock,
    mock_docusign_client,
    api_client: TestClient,
    seeded_property,
) -> None:
    transaction_id = _create_and_pdf(api_client, seeded_property.remote_id)
    api_client.post(f"/api/v1/transactions/{transaction_id}/docusign/envelope")

    response = api_client.post(
        f"/api/v1/transactions/{transaction_id}/docusign/signing-url",
        json={
            "role": "BUYER",
            "return_url": "http://localhost:3000/dashboard/transactions/return",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "demo.docusign.net" in body["signing_url"]
    assert body["role"] == "BUYER"

    from database import engine

    with Session(engine) as cleanup:
        delete_transaction_cascade(cleanup, transaction_id)


def test_legacy_execute_signature_blocked_when_docusign_enabled(
    api_client: TestClient,
    seeded_property,
) -> None:
    transaction_id = _create_and_pdf(api_client, seeded_property.remote_id)
    response = api_client.post(
        f"/api/v1/transactions/{transaction_id}/execute-signature",
        json={"role": "BUYER"},
    )
    assert response.status_code == 409

    from database import engine

    with Session(engine) as cleanup:
        delete_transaction_cascade(cleanup, transaction_id)


def test_connect_webhook_marks_executed(
    api_client: TestClient,
    seeded_property,
    db_session: Session,
) -> None:
    transaction_id = _create_and_pdf(api_client, seeded_property.remote_id)
    contract = db_session.exec(
        select(LegalContract).where(LegalContract.transaction_session_id == transaction_id)
    ).first()
    assert contract is not None
    contract.docusign_envelope_id = "env-webhook-test"
    contract.docusign_status = "sent"
    db_session.add(contract)
    db_session.commit()

    payload = json.dumps({"envelopeId": "env-webhook-test", "status": "completed"}).encode()
    secret = "test-connect-secret"
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    response = api_client.post(
        "/api/v1/docusign/connect/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-DocuSign-Signature-1": sig,
        },
    )
    assert response.status_code == 200

    db_session.expire_all()
    from models import TransactionSession

    txn = db_session.get(TransactionSession, transaction_id)
    assert txn is not None
    assert txn.status == TransactionSessionStatus.EXECUTED
    assert txn.buyer_signed_at is not None
    assert txn.seller_signed_at is not None

    from database import engine

    with Session(engine) as cleanup:
        delete_transaction_cascade(cleanup, transaction_id)


def _create_and_pdf(api_client: TestClient, property_id: str) -> str:
    create = api_client.post(
        "/api/v1/transactions",
        json={
            "property_id": property_id,
            "buyer_name": "Comprador DocuSign",
            "buyer_id_doc": "402-1111111-1",
            "seller_name": "Vendedor DocuSign",
            "seller_id_doc": "001-2222222-2",
            "agreed_price": 250000.0,
            "currency": "USD",
        },
    )
    assert create.status_code == 201
    transaction_id = create.json()["id"]
    assert api_client.post(f"/api/v1/transactions/{transaction_id}/generate").status_code == 201
    assert api_client.post(f"/api/v1/transactions/{transaction_id}/generate-pdf").status_code == 200
    return transaction_id