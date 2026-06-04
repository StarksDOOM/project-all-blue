"""Phase 5 secure PDF, tamper hash, and multi-party signatures."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from models import TransactionSessionStatus
from services.pdf_renderer import sha256_file
from tests.db_cleanup import delete_transaction_cascade


def test_generate_pdf_and_dual_signatures(
    api_client: TestClient,
    seeded_property,
    db_session: Session,
) -> None:
    create = api_client.post(
        "/api/v1/transactions",
        json={
            "property_id": seeded_property.remote_id,
            "buyer_name": "Comprador QA",
            "buyer_id_doc": "402-0000000-1",
            "seller_name": "Vendedor QA",
            "seller_id_doc": "001-0000000-2",
            "agreed_price": 200000.0,
            "currency": "USD",
        },
    )
    assert create.status_code == 201
    transaction_id = create.json()["id"]

    gen_md = api_client.post(f"/api/v1/transactions/{transaction_id}/generate")
    assert gen_md.status_code == 201

    gen_pdf = api_client.post(f"/api/v1/transactions/{transaction_id}/generate-pdf")
    assert gen_pdf.status_code == 200
    body = gen_pdf.json()
    assert body["has_secure_pdf"] is True
    assert body["document_hash"]
    pdf_path = Path(body["pdf_file_path"])
    assert pdf_path.is_file()
    assert sha256_file(pdf_path) == body["document_hash"]

    buyer_sign = api_client.post(
        f"/api/v1/transactions/{transaction_id}/execute-signature",
        json={"role": "BUYER"},
        headers={"User-Agent": "pytest-buyer"},
    )
    assert buyer_sign.status_code == 200
    assert buyer_sign.json()["transaction"]["buyer_signed_at"]
    assert buyer_sign.json()["transaction"]["status"] == "GENERATED"

    seller_sign = api_client.post(
        f"/api/v1/transactions/{transaction_id}/execute-signature",
        json={"role": "SELLER"},
        headers={"User-Agent": "pytest-seller"},
    )
    assert seller_sign.status_code == 200
    txn = seller_sign.json()["transaction"]
    assert txn["seller_signed_at"]
    assert txn["status"] == TransactionSessionStatus.EXECUTED.value
    assert len(txn["signature_telemetry"].get("signatures", [])) == 2

    pdf_dl = api_client.get(f"/api/v1/transactions/{transaction_id}/contract/pdf")
    assert pdf_dl.status_code == 200
    assert pdf_dl.headers["content-type"].startswith("application/pdf")

    from database import engine

    with Session(engine) as cleanup:
        delete_transaction_cascade(cleanup, transaction_id)