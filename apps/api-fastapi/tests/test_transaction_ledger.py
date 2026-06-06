"""
Unit and integration tests for Transaction Ledger Dashboard queries and routing.

STREAM 6 PHASE 1.2.
"""

from __future__ import annotations

import secrets
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models import LegalContract, PropertyListing

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


def test_list_contracts_endpoint_agent_scoped(
    api_client: TestClient,
    db_session: Session,
    seeded_property: PropertyListing,
) -> None:
    """
    Verify that an AGENT successfully fetches only their own contracts.
    """
    agent1_id = "agent-uid-100"
    agent2_id = "agent-uid-200"

    # Contract 1: initiated by agent 1
    contract1 = LegalContract(
        property_id=seeded_property.id,
        user_id=agent1_id,
        docusign_envelope_id=f"env-ledger-1-{secrets.token_hex(4)}",
        docusign_status="sent",
        version_hash="vhash-1",
    )
    # Contract 2: initiated by agent 2
    contract2 = LegalContract(
        property_id=seeded_property.id,
        user_id=agent2_id,
        docusign_envelope_id=f"env-ledger-2-{secrets.token_hex(4)}",
        docusign_status="executed",
        version_hash="vhash-2",
    )

    db_session.add(contract1)
    db_session.add(contract2)
    db_session.commit()

    # Act: Request as agent 1
    token1 = _mint_jwt(user_id=agent1_id, role="agent", email="agent1@example.com")
    headers1 = {"Authorization": f"Bearer {token1}"}
    response1 = api_client.get("/api/v1/contracts", headers=headers1)

    assert response1.status_code == 200
    contracts_list1 = response1.json()

    # Assert agent 1 only sees their own contract
    assert len(contracts_list1) >= 1
    agent1_contracts = [c for c in contracts_list1 if c["id"] == contract1.id]
    agent2_contracts = [c for c in contracts_list1 if c["id"] == contract2.id]

    assert len(agent1_contracts) == 1
    assert len(agent2_contracts) == 0

    # Verify joined property data is serialized properly
    c_item = agent1_contracts[0]
    assert c_item["status"] == "sent"
    assert c_item["property"] is not None
    assert c_item["property"]["title"] == seeded_property.title
    assert c_item["property"]["price_usd"] == seeded_property.price_usd


def test_list_contracts_endpoint_admin_all(
    api_client: TestClient,
    db_session: Session,
    seeded_property: PropertyListing,
) -> None:
    """
    Verify that an ADMIN successfully fetches all contracts across agents.
    """
    agent_id = "agent-uid-300"
    admin_id = "admin-uid-100"

    # Contract: initiated by agent
    contract = LegalContract(
        property_id=seeded_property.id,
        user_id=agent_id,
        docusign_envelope_id=f"env-ledger-3-{secrets.token_hex(4)}",
        docusign_status="sent",
        version_hash="vhash-3",
    )
    db_session.add(contract)
    db_session.commit()

    # Act: Request as admin
    token = _mint_jwt(user_id=admin_id, role="admin", email="admin@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    response = api_client.get("/api/v1/contracts", headers=headers)

    assert response.status_code == 200
    contracts_list = response.json()

    # Admin should see the contract initiated by the agent
    matched = [c for c in contracts_list if c["id"] == contract.id]
    assert len(matched) == 1
    assert matched[0]["property"]["title"] == seeded_property.title


def test_list_contracts_endpoint_client_denied(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """
    Verify that a CLIENT is denied access (returns 403 Forbidden).
    """
    token = _mint_jwt(user_id="client-uid-100", role="client", email="client@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    response = api_client.get("/api/v1/contracts", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
