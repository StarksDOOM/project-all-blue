"""Integration tests for the Inkless Signature URL Bridge (STREAM 6 PHASE 1.8.2)."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session

from models import LegalContract, PropertyListing
from schemas.transactions import LegalContractResponse


def _make_listing(
    *,
    db_session: Session,
    sector: str = "TestSector",
    price_usd: float = 150000.0,
    square_meters: float = 120.0,
) -> PropertyListing:
    """Helper to insert a test property listing."""
    suffix = secrets.token_hex(4)
    listing = PropertyListing(
        id=f"#BLU-INK-{suffix.upper()}",
        remote_id=f"ink-{suffix}",
        source_portal="remaxrd",
        url=f"https://example.test/ink/{suffix}",
        title=f"Inkless Test Listing {suffix}",
        price_usd=price_usd,
        province="Santo Domingo",
        sector=sector,
        bedrooms=3,
        bathrooms=2.0,
        square_meters=square_meters,
        raw_description="pytest inkless bridge fixture",
        is_active=True,
    )
    db_session.add(listing)
    db_session.flush()
    db_session.refresh(listing)
    return listing


def test_legal_contract_signing_url_field(db_session: Session) -> None:
    """Verify that LegalContract can store and retrieve the signing_url field."""
    listing = _make_listing(db_session=db_session)
    contract = LegalContract(
        property_id=listing.id,
        user_id="agent-user-id",
        version_hash="abcdef123456",
        generated_at=datetime.now(timezone.utc),
        signing_url="https://inkless.io/sign/env_1234",
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)

    assert contract.signing_url == "https://inkless.io/sign/env_1234"
    assert contract.property_id == listing.id


def test_get_contract_by_property_not_found(api_client: TestClient) -> None:
    """Verify that querying a non-existent property contract returns null."""
    response = api_client.get("/api/v1/contracts/property/non-existent-prop-id")
    assert response.status_code == 200
    assert response.json() is None


def test_get_contract_by_property_found(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Verify we can retrieve the latest LegalContract by property_id via HTTP GET."""
    listing = _make_listing(db_session=db_session)

    # 1. Create a contract without signing_url
    contract_old = LegalContract(
        property_id=listing.id,
        user_id="agent-1",
        version_hash="hash-old-1111",
        generated_at=datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(contract_old)

    # 2. Create the latest contract with a signing_url
    contract_new = LegalContract(
        property_id=listing.id,
        user_id="agent-1",
        version_hash="hash-new-2222",
        generated_at=datetime(2026, 6, 9, 14, 0, 0, tzinfo=timezone.utc),
        signing_url="https://inkless.io/sign/env_latest",
    )
    db_session.add(contract_new)
    db_session.commit()

    # 3. Request the latest contract via the API endpoint
    from urllib.parse import quote
    encoded_id = quote(listing.id, safe="")
    response = api_client.get(f"/api/v1/contracts/property/{encoded_id}")
    assert response.status_code == 200
    data = response.json()

    assert data is not None
    assert data["id"] == contract_new.id
    assert data["version_hash"] == "hash-new-2222"
    assert data["signing_url"] == "https://inkless.io/sign/env_latest"
    assert data["transaction"] is None  # Direct contract (no transaction session)
    assert data["property"]["id"] == listing.id


def test_optional_transaction_field_serialization(db_session: Session) -> None:
    """Verify Pydantic serialization of LegalContractResponse with a null transaction."""
    listing = _make_listing(db_session=db_session)
    contract = LegalContract(
        property_id=listing.id,
        user_id="agent-1",
        version_hash="hash-3333",
        generated_at=datetime.now(timezone.utc),
        signing_url="https://inkless.io/sign/env_direct",
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)

    # Manual serialization mapping
    from services.transaction_service import contract_to_dict
    res_dict = contract_to_dict(contract, None, listing)

    # Validate using Pydantic model
    validated = LegalContractResponse(**res_dict)
    assert validated.id == contract.id
    assert validated.transaction_session_id is None
    assert validated.transaction is None
    assert validated.signing_url == "https://inkless.io/sign/env_direct"
