"""
Unit and integration tests for contract generation and DocuSeal workflows.

STREAM 6 PHASE 1.5.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session

from config.docuseal_settings import get_docuseal_settings
from models import LegalContract, PropertyListing
from services.auth import UserCredentials, UserRole
from services.docuseal_dispatcher import DocuSealDispatcher

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
def _docuseal_test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure DocuSeal environment variables are populated and cache is cleared.
    """
    monkeypatch.setenv("DOCUSEAL_API_KEY", "mock-api-key-12345")
    monkeypatch.setenv("DOCUSEAL_TEMPLATE_ID", "1000001")
    monkeypatch.setenv("DOCUSEAL_BASE_URL", "https://api.docuseal.com")
    monkeypatch.setenv("DOCUSEAL_WEBHOOK_SECRET", "mock-webhook-secret")
    get_docuseal_settings.cache_clear()


def test_docuseal_settings_loader() -> None:
    """
    Verify DocuSealSettings loads correctly from environment.
    """
    settings = get_docuseal_settings()
    assert settings.api_key == "mock-api-key-12345"
    assert settings.template_id == "1000001"
    assert settings.base_url == "https://api.docuseal.com"
    assert settings.webhook_secret == "mock-webhook-secret"
    assert settings.is_enabled is True


def test_docuseal_dispatcher_success() -> None:
    """
    Verify DocuSealDispatcher constructs and transmits request to DocuSeal.
    """
    dispatcher = DocuSealDispatcher()

    # Mock response object from httpx.Client.post
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 12345, "status": "pending"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client.post", return_value=mock_response) as mock_post:
        submission_id = dispatcher.dispatch(
            property_id="#BLU-12345",
            buyer_email="buyer@example.com",
            agent_email="agent@example.com",
        )

        assert submission_id == "12345"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.docuseal.com/api/submissions"
        headers = kwargs["headers"]
        assert headers["X-Auth-Token"] == "mock-api-key-12345"
        payload = kwargs["json"]
        assert payload["template_id"] == 1000001
        assert payload["metadata"]["external_id"] == "#BLU-12345"


def test_docuseal_dispatcher_handles_list_response() -> None:
    """
    Verify DocuSealDispatcher handles list response formats correctly.
    """
    dispatcher = DocuSealDispatcher()

    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": 99999, "status": "pending"}]
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client.post", return_value=mock_response):
        submission_id = dispatcher.dispatch(
            property_id="#BLU-12345",
            buyer_email="buyer@example.com",
            agent_email="agent@example.com",
        )
        assert submission_id == "99999"


def test_docuseal_dispatcher_api_failure_raises_runtime_error() -> None:
    """
    Verify DocuSealDispatcher raises a RuntimeError when API call throws an exception.
    """
    dispatcher = DocuSealDispatcher()

    with patch("httpx.Client.post", side_effect=Exception("API connection timed out")):
        with pytest.raises(RuntimeError) as exc_info:
            dispatcher.dispatch(
                property_id="#BLU-12345",
                buyer_email="buyer@example.com",
                agent_email="agent@example.com",
            )
        assert "DocuSeal dispatch failed" in str(exc_info.value)


@patch("services.docuseal_dispatcher.DocuSealDispatcher.dispatch", return_value="12345")
def test_generate_contract_endpoint_success(
    _mock_dispatch: MagicMock,
    api_client: TestClient,
    seeded_property: PropertyListing,
    db_session: Session,
) -> None:
    """
    Verify endpoint POST /api/v1/contracts/generate creates a contract and database record.
    """
    token = _mint_jwt(user_id="agent-uid-777", role="agent", email="agent@remax.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"property_id": seeded_property.id}

    response = api_client.post("/api/v1/contracts/generate", json=payload, headers=headers)
    assert response.status_code == 201

    body = response.json()
    assert body["envelope_id"] == "12345"
    assert body["status"] == "sent"
    assert "contract_id" in body

    # Verify database persistence
    contract_id = body["contract_id"]
    db_session.expire_all()
    contract = db_session.get(LegalContract, contract_id)
    assert contract is not None
    assert contract.property_id == seeded_property.id
    assert contract.user_id == "agent-uid-777"
    assert contract.docusign_envelope_id == "12345"
    assert contract.docusign_status == "sent"
    assert contract.version_hash is not None


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


def test_generate_contract_endpoint_listing_not_found(
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
