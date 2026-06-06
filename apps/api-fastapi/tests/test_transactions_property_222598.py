"""
Live QA contract: mirrors manual curl flow against reference property 222598.

Skips when the listing is absent from the connected Postgres inventory.

NOTE: Marked ``live_qa`` — requires RE/MAX portal reachability.
Run manually with: pytest -m live_qa
Excluded from standard regression gate (-m "not live_qa").
Stabilize when network-isolation strategy is defined.
"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session

from database import engine
from tests.db_cleanup import delete_transaction_cascade

QA_REMOTE_ID = "222598"
QA_PAYLOAD = {
    "property_id": QA_REMOTE_ID,
    "buyer_name": "Juan Pérez",
    "buyer_id_doc": "402-XXXXXXX-X",
    "seller_name": "María Rodriguez",
    "seller_id_doc": "001-XXXXXXX-X",
    "agreed_price": 150_000.0,
    "currency": "USD",
}


@pytest.mark.live_qa
def test_manual_qa_transaction_flow_property_222598(api_client: TestClient) -> None:
    property_resp = api_client.get(f"/api/v1/properties/{QA_REMOTE_ID}")
    assert property_resp.status_code == 200, (
        f"Reference property {QA_REMOTE_ID} must exist for manual QA parity"
    )
    property_row = property_resp.json()

    create_resp = api_client.post("/api/v1/transactions", json=QA_PAYLOAD)
    assert create_resp.status_code == 201, create_resp.text
    transaction = create_resp.json()
    transaction_id = transaction["id"]
    assert transaction["property_remote_id"] == QA_REMOTE_ID
    assert transaction["status"] == "DRAFT"

    generate_resp = api_client.post(
        f"/api/v1/transactions/{transaction_id}/generate"
    )
    assert generate_resp.status_code == 201, generate_resp.text
    contract = generate_resp.json()
    body = contract["document_body"]

    assert contract["transaction"]["status"] == "GENERATED"
    assert "PROMESA DE VENTA" in body
    assert "Juan Pérez" in body
    assert "María Rodriguez" in body
    assert QA_REMOTE_ID in body
    assert property_row["title"] in body

    fetch_resp = api_client.get(f"/api/v1/transactions/{transaction_id}/contract")
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["version_hash"] == contract["version_hash"]

    raw_resp = api_client.get(
        f"/api/v1/transactions/{transaction_id}/contract/raw"
    )
    assert raw_resp.status_code == 200
    assert "PROMESA DE VENTA" in raw_resp.text

    with Session(engine) as cleanup:
        delete_transaction_cascade(cleanup, transaction_id)