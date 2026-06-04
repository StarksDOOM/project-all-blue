"""Phase 6 audit certificate, post-execution pipeline, and audit download endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import LegalContract, TransactionSession, TransactionSessionStatus
from services.audit_certificate_generator import AuditCertificateInput, write_audit_certificate
from services.post_execution_pipeline import run_post_execution_pipeline
from tests.db_cleanup import delete_transaction_cascade


def test_audit_certificate_generator_writes_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import services.audit_certificate_generator as cert_mod

    monkeypatch.setattr(cert_mod, "AUDIT_RECEIPTS_DIR", tmp_path)
    data = AuditCertificateInput(
        transaction_id="txn-test-001",
        property_id="#BLU-TEST",
        property_title="Test Property",
        esign_envelope_id="env-abc",
        esign_status="completed",
        document_hash="a" * 64,
        buyer={
            "role": "Buyer",
            "name": "Comprador",
            "email": "buyer@test.local",
            "signed_at": "2026-06-04T12:00:00Z",
        },
        seller={
            "role": "Seller",
            "name": "Vendedor",
            "email": "seller@test.local",
            "signed_at": "2026-06-04T12:05:00Z",
        },
        executed_at="2026-06-04T12:05:00Z",
    )
    path = write_audit_certificate(data)
    assert path.is_file()
    assert path.suffix == ".pdf"
    assert path.stat().st_size > 500


@patch("services.post_execution_pipeline.download_completed_envelope_pdf")
def test_post_execution_pipeline_generates_certificate(
    _mock_download: object,
    api_client: TestClient,
    seeded_property,
    db_session: Session,
) -> None:
    transaction_id = _create_executed_transaction(api_client, seeded_property.remote_id)

    connect_event = {
        "envelopeId": "env-phase6",
        "status": "completed",
        "envelopeSummary": {
            "recipients": {
                "signers": [
                    {
                        "roleName": "Buyer",
                        "name": "Comprador QA",
                        "email": "buyer@allblue.local",
                        "signedDateTime": "2026-06-04T10:00:00Z",
                    },
                    {
                        "roleName": "Seller",
                        "name": "Vendedor QA",
                        "email": "seller@allblue.local",
                        "signedDateTime": "2026-06-04T10:01:00Z",
                    },
                ]
            }
        },
    }

    contract = db_session.exec(
        select(LegalContract).where(LegalContract.transaction_session_id == transaction_id)
    ).first()
    assert contract is not None
    contract.docusign_envelope_id = "env-phase6"
    contract.docusign_status = "completed"
    db_session.add(contract)
    db_session.commit()

    run_post_execution_pipeline(transaction_id, connect_event)

    db_session.expire_all()
    contract = db_session.exec(
        select(LegalContract).where(LegalContract.transaction_session_id == transaction_id)
    ).first()
    assert contract is not None
    assert contract.audit_certificate_path
    assert Path(contract.audit_certificate_path).is_file()

    cert_dl = api_client.get(f"/api/v1/transactions/{transaction_id}/audit-certificate")
    assert cert_dl.status_code == 200
    assert cert_dl.headers["content-type"].startswith("application/pdf")

    from database import engine

    with Session(engine) as cleanup:
        delete_transaction_cascade(cleanup, transaction_id)


def test_audit_certificate_404_when_not_executed(
    api_client: TestClient,
    seeded_property,
) -> None:
    create = api_client.post(
        "/api/v1/transactions",
        json={
            "property_id": seeded_property.remote_id,
            "buyer_name": "Comprador",
            "buyer_id_doc": "402-0000000-1",
            "seller_name": "Vendedor",
            "seller_id_doc": "001-0000000-2",
            "agreed_price": 100000.0,
            "currency": "USD",
        },
    )
    transaction_id = create.json()["id"]
    response = api_client.get(f"/api/v1/transactions/{transaction_id}/audit-certificate")
    assert response.status_code == 404

    from database import engine

    with Session(engine) as cleanup:
        delete_transaction_cascade(cleanup, transaction_id)


@patch("routers.docusign.run_post_execution_pipeline")
def test_webhook_schedules_post_execution(
    mock_pipeline: object,
    api_client: TestClient,
    seeded_property,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib
    import hmac

    from config.docusign_settings import get_docusign_settings

    monkeypatch.setenv("DOCUSIGN_WEBHOOK_SECRET", "test-connect-secret")
    get_docusign_settings.cache_clear()

    transaction_id = _create_and_pdf(api_client, seeded_property.remote_id)
    contract = db_session.exec(
        select(LegalContract).where(LegalContract.transaction_session_id == transaction_id)
    ).first()
    assert contract is not None
    contract.docusign_envelope_id = "env-bg-task"
    db_session.add(contract)
    db_session.commit()

    payload = json.dumps(
        {
            "envelopeId": "env-bg-task",
            "status": "completed",
            "envelopeSummary": {
                "recipients": {
                    "signers": [
                        {"roleName": "Buyer", "name": "B", "email": "b@t.com"},
                        {"roleName": "Seller", "name": "S", "email": "s@t.com"},
                    ]
                }
            },
        }
    ).encode()
    sig = hmac.new(b"test-connect-secret", payload, hashlib.sha256).hexdigest()

    response = api_client.post(
        "/api/v1/docusign/connect/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-DocuSign-Signature-1": sig,
        },
    )
    assert response.status_code == 200
    assert mock_pipeline.called

    from database import engine

    with Session(engine) as cleanup:
        delete_transaction_cascade(cleanup, transaction_id)


def _create_and_pdf(api_client: TestClient, property_id: str) -> str:
    create = api_client.post(
        "/api/v1/transactions",
        json={
            "property_id": property_id,
            "buyer_name": "Comprador QA",
            "buyer_id_doc": "402-1111111-1",
            "seller_name": "Vendedor QA",
            "seller_id_doc": "001-2222222-2",
            "agreed_price": 200000.0,
            "currency": "USD",
        },
    )
    transaction_id = create.json()["id"]
    api_client.post(f"/api/v1/transactions/{transaction_id}/generate")
    api_client.post(f"/api/v1/transactions/{transaction_id}/generate-pdf")
    return transaction_id


def _create_executed_transaction(api_client: TestClient, property_id: str) -> str:
    transaction_id = _create_and_pdf(api_client, property_id)
    from config.docusign_settings import get_docusign_settings

    if get_docusign_settings().is_enabled:
        pytest.skip("Internal signature path disabled when DocuSign provider active")

    api_client.post(
        f"/api/v1/transactions/{transaction_id}/execute-signature",
        json={"role": "BUYER"},
    )
    api_client.post(
        f"/api/v1/transactions/{transaction_id}/execute-signature",
        json={"role": "SELLER"},
    )
    return transaction_id