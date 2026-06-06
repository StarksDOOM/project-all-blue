"""
Unit and integration tests for contract generation and DocuSign M2M workflows.

STREAM 6 PHASE 1.0.
"""

from __future__ import annotations

import time
from typing import Generator
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from config.docusign_settings import get_docusign_settings
from models import LegalContract, PropertyListing
from services.auth import UserCredentials, UserRole
from services.contract_dispatcher import ContractDispatcher
from services.contract_envelope_builder import ContractEnvelopeBuilder
from services.docusign_jwt_authenticator import DocuSignJWTAuthenticator

TEST_JWT_SECRET = "test-secret-for-rbac-phase5-only-do-not-use-in-prod"


def _mint_jwt(
    *,
    user_id: str = "agent-user-123",
    email: str = "agent@example.com",
    role: str = "agent",
    exp_offset: int = 3600,
) -> str:
    """Local-only mint of HS256 JWT for testing (no Supabase network dependencies)."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "app_metadata": {"role": role},
        "iat": now,
        "exp": now + exp_offset,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def _docusign_test_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """
    Ensure DocuSign environment variables are populated and cache is cleared.

    Mocks private key reads to keep the test environment entirely isolated.
    """
    monkeypatch.setenv("DOCUSIGN_PROVIDER", "docusign")
    monkeypatch.setenv("DOCUSIGN_USER_ID", "6da28b5f-7e26-4249-b95e-9124c25ee4f8")
    monkeypatch.setenv("DOCUSIGN_API_ACCOUNT_ID", "e1fca701-58e9-4190-ac60-2e1d9843cc10")
    monkeypatch.setenv("DOCUSIGN_INTEGRATION_KEY", "ea0f68ac-a0e6-4100-9dfb-baa9916143a2")
    monkeypatch.setenv("DOCUSIGN_BASE_URL", "https://demo.docusign.net/restapi")
    monkeypatch.setenv("DOCUSIGN_OAUTH_HOST", "account-d.docusign.com")
    monkeypatch.setenv("DOCUSIGN_WEBHOOK_SECRET", "mock-webhook-secret")
    get_docusign_settings.cache_clear()

    with patch("config.docusign_settings.DocusignSettings.private_key_bytes", return_value=b"mock-private-key-bytes"):
        yield


def test_docusign_jwt_authenticator_success() -> None:
    """
    Verify DocuSignJWTAuthenticator exchanges private key and sets default headers.

    Uses a fully mocked ApiClient to verify call parameters without hitting external servers.
    """
    authenticator = DocuSignJWTAuthenticator()

    mock_token = MagicMock()
    mock_token.access_token = "mock-jwt-access-token"

    with patch("services.docusign_jwt_authenticator.ApiClient") as mock_api_client_cls:
        mock_client_instance = mock_api_client_cls.return_value
        mock_client_instance.request_jwt_user_token.return_value = mock_token

        client = authenticator.authenticate()

        # Check call args
        mock_client_instance.request_jwt_user_token.assert_called_once_with(
            client_id="ea0f68ac-a0e6-4100-9dfb-baa9916143a2",
            user_id="6da28b5f-7e26-4249-b95e-9124c25ee4f8",
            oauth_host_name="account-d.docusign.com",
            private_key_bytes=b"mock-private-key-bytes",
            expires_in=3600,
            scopes=["signature", "impersonation"],
        )
        mock_client_instance.set_default_header.assert_called_once_with(
            "Authorization", "Bearer mock-jwt-access-token"
        )
        assert client == mock_client_instance


def test_docusign_jwt_authenticator_empty_token_raises_error() -> None:
    """
    Verify authenticator raises RuntimeError when DocuSign API returns an empty token.
    """
    authenticator = DocuSignJWTAuthenticator()

    mock_token = MagicMock()
    mock_token.access_token = None

    with patch("services.docusign_jwt_authenticator.ApiClient") as mock_api_client_cls:
        mock_client_instance = mock_api_client_cls.return_value
        mock_client_instance.request_jwt_user_token.return_value = mock_token

        with pytest.raises(RuntimeError) as exc_info:
            authenticator.authenticate()

        assert "empty access_token" in str(exc_info.value)


def test_contract_envelope_builder(seeded_property: PropertyListing) -> None:
    """
    Verify ContractEnvelopeBuilder correctly maps a PropertyListing to a DocuSign EnvelopeDefinition.
    """
    builder = ContractEnvelopeBuilder()
    credentials = UserCredentials(
        user_id="agent-123",
        email="agent.test@example.com",
        role=UserRole.AGENT,
        raw_claims={},
    )

    envelope = builder.build_envelope(seeded_property, credentials)

    assert envelope.email_subject == f"Reserva de Propiedad - {seeded_property.title}"
    assert envelope.status == "sent"
    assert len(envelope.documents) == 1
    assert envelope.documents[0].file_extension == "html"
    assert envelope.documents[0].document_id == "1"

    recipients = envelope.recipients
    assert len(recipients.signers) == 2

    buyer = recipients.signers[0]
    assert buyer.email == "cliente.comprador@example.com"
    assert buyer.name == "Cliente Comprador Demo"
    assert buyer.recipient_id == "1"
    assert buyer.routing_order == "1"
    assert len(buyer.tabs.sign_here_tabs) == 1
    assert buyer.tabs.sign_here_tabs[0].anchor_string == "/sn1/"

    agent = recipients.signers[1]
    assert agent.email == "agent.test@example.com"
    assert agent.name == "Agente (agent)"
    assert agent.recipient_id == "2"
    assert agent.routing_order == "2"
    assert len(agent.tabs.sign_here_tabs) == 1
    assert agent.tabs.sign_here_tabs[0].anchor_string == "/sn2/"


def test_contract_dispatcher_success() -> None:
    """
    Verify ContractDispatcher sends the EnvelopeDefinition and returns the envelope ID.
    """
    mock_api_client = MagicMock()
    dispatcher = ContractDispatcher(mock_api_client)

    mock_summary = MagicMock()
    mock_summary.envelope_id = "envelope-id-guid-9999"

    mock_envelope_definition = MagicMock()

    with patch("services.contract_dispatcher.EnvelopesApi") as mock_envelopes_api_cls:
        mock_envelopes_api_instance = mock_envelopes_api_cls.return_value
        mock_envelopes_api_instance.create_envelope.return_value = mock_summary

        envelope_id = dispatcher.dispatch(mock_envelope_definition)

        mock_envelopes_api_instance.create_envelope.assert_called_once_with(
            account_id="e1fca701-58e9-4190-ac60-2e1d9843cc10",
            envelope_definition=mock_envelope_definition,
        )
        assert envelope_id == "envelope-id-guid-9999"


def test_contract_dispatcher_api_failure_raises_runtime_error() -> None:
    """
    Verify ContractDispatcher raises a RuntimeError when EnvelopesApi call throws an exception.
    """
    mock_api_client = MagicMock()
    dispatcher = ContractDispatcher(mock_api_client)
    mock_envelope_definition = MagicMock()

    with patch("services.contract_dispatcher.EnvelopesApi") as mock_envelopes_api_cls:
        mock_envelopes_api_instance = mock_envelopes_api_cls.return_value
        mock_envelopes_api_instance.create_envelope.side_effect = Exception("API connection timed out")

        with pytest.raises(RuntimeError) as exc_info:
            dispatcher.dispatch(mock_envelope_definition)

        assert "DocuSign dispatch failed" in str(exc_info.value)


@patch("services.contract_dispatcher.ContractDispatcher.dispatch", return_value="mock-envelope-id-12345")
@patch("services.docusign_jwt_authenticator.DocuSignJWTAuthenticator.authenticate")
def test_generate_contract_endpoint_success(
    _mock_auth: MagicMock,
    _mock_dispatch: MagicMock,
    api_client: TestClient,
    seeded_property: PropertyListing,
    db_session: Session,
) -> None:
    """
    Verify endpoint POST /api/v1/contracts/generate creates a contract and database record.

    Access is allowed for AGENT role. Mocks are in place to avoid outbound DocuSign network calls.
    """
    token = _mint_jwt(user_id="agent-uid-777", role="agent", email="agent@remax.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"property_id": seeded_property.id}

    response = api_client.post("/api/v1/contracts/generate", json=payload, headers=headers)
    assert response.status_code == 201

    body = response.json()
    assert body["envelope_id"] == "mock-envelope-id-12345"
    assert body["status"] == "sent"
    assert "contract_id" in body

    # Verify database persistence
    contract_id = body["contract_id"]
    db_session.expire_all()
    contract = db_session.get(LegalContract, contract_id)
    assert contract is not None
    assert contract.property_id == seeded_property.id
    assert contract.user_id == "agent-uid-777"
    assert contract.docusign_envelope_id == "mock-envelope-id-12345"
    assert contract.docusign_status == "sent"
    assert contract.version_hash is not None
    assert contract.transaction_session_id is None


def test_generate_contract_endpoint_role_denied(
    api_client: TestClient,
    seeded_property: PropertyListing,
) -> None:
    """
    Verify that CLIENT roles are denied access to the contract generation endpoint.
    """
    token = _mint_jwt(user_id="client-uid-888", role="client")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"property_id": seeded_property.id}

    response = api_client.post("/api/v1/contracts/generate", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


@patch("services.docusign_jwt_authenticator.DocuSignJWTAuthenticator.authenticate")
def test_generate_contract_endpoint_listing_not_found(
    _mock_auth: MagicMock,
    api_client: TestClient,
) -> None:
    """
    Verify that generating a contract for a non-existent property listing raises 404 (SSRF mitigation).
    """
    token = _mint_jwt(user_id="agent-uid-777", role="agent")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"property_id": "#BLU-NONEXISTENT"}

    response = api_client.post("/api/v1/contracts/generate", json=payload, headers=headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
