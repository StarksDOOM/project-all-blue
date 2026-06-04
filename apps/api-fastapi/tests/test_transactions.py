"""Phase 4 transaction session and legal contract generation."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import LegalContract, PropertyListing, TransactionSession


def test_create_transaction_and_generate_contract(
    api_client: TestClient,
    seeded_property: PropertyListing,
    db_session: Session,
) -> None:
    create_resp = api_client.post(
        "/api/v1/transactions",
        json={
            "property_id": seeded_property.remote_id,
            "buyer_name": "Comprador Test",
            "buyer_id_doc": "402-0000000-0",
            "seller_name": "Vendedor Test",
            "seller_id_doc": "001-0000000-0",
            "agreed_price": 250000.0,
            "currency": "USD",
        },
    )
    assert create_resp.status_code == 201
    transaction_id = create_resp.json()["id"]

    gen_resp = api_client.post(f"/api/v1/transactions/{transaction_id}/generate")
    assert gen_resp.status_code == 201
    body = gen_resp.json()
    assert "PROMESA DE VENTA" in body["document_body"]
    assert str(seeded_property.remote_id) in body["document_body"]
    assert "Comprador Test" in body["document_body"]
    assert body["transaction"]["status"] == "GENERATED"

    fetch_resp = api_client.get(f"/api/v1/transactions/{transaction_id}/contract")
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["version_hash"] == body["version_hash"]

    row = db_session.exec(
        select(TransactionSession).where(TransactionSession.id == transaction_id)
    ).first()
    assert row is not None
    contracts = db_session.exec(
        select(LegalContract).where(
            LegalContract.transaction_session_id == transaction_id
        )
    ).all()
    assert len(contracts) >= 1


def test_fetch_contract_before_generate_returns_404(
    api_client: TestClient,
    seeded_property: PropertyListing,
) -> None:
    create_resp = api_client.post(
        "/api/v1/transactions",
        json={
            "property_id": seeded_property.id,
            "buyer_name": "Ana Compradora",
            "buyer_id_doc": "402-1111111-1",
            "seller_name": "Ben Vendedor",
            "seller_id_doc": "001-2222222-2",
            "agreed_price": 1000.0,
            "currency": "USD",
        },
    )
    transaction_id = create_resp.json()["id"]
    missing = api_client.get(f"/api/v1/transactions/{transaction_id}/contract")
    assert missing.status_code == 404