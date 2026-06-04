"""
Orchestrates DocuSign envelope lifecycle with ``TransactionSession`` / ``LegalContract`` rows.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from config.docusign_settings import get_docusign_settings
from models import LegalContract, SignatureRole, TransactionSession, TransactionSessionStatus
from services.docusign.embedded import create_embedded_signing_url
from services.docusign.envelope import create_envelope_from_pdf
from services.signature_service import _assert_pdf_integrity
from services.transaction_service import get_latest_legal_contract

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_docusign_enabled() -> None:
    if not get_docusign_settings().is_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocuSign provider is not configured",
        )


def _signer_email(role: SignatureRole, transaction: TransactionSession) -> str:
    """
    Placeholder emails for sandbox embedded signing.

    Override via env ``DOCUSIGN_BUYER_EMAIL`` / ``DOCUSIGN_SELLER_EMAIL`` for real inboxes.
    """
    if role == SignatureRole.BUYER:
        return os.getenv(
            "DOCUSIGN_BUYER_EMAIL",
            f"buyer+{transaction.id[:8]}@allblue.local",
        )
    return os.getenv(
        "DOCUSIGN_SELLER_EMAIL",
        f"seller+{transaction.id[:8]}@allblue.local",
    )


def create_docusign_envelope(session: Session, transaction_id: str) -> tuple[Any, LegalContract, Any]:
    """Seal PDF integrity check, create DocuSign envelope, persist envelope id on contract."""
    _require_docusign_enabled()
    transaction, contract, property_listing = get_latest_legal_contract(session, transaction_id)

    if transaction.status not in (
        TransactionSessionStatus.GENERATED,
        TransactionSessionStatus.EXECUTED,
    ):
        raise HTTPException(
            status_code=400,
            detail="Markdown contract must be generated before DocuSign envelope",
        )

    _assert_pdf_integrity(contract)
    if contract.docusign_envelope_id:
        raise HTTPException(
            status_code=409,
            detail="DocuSign envelope already exists for this transaction",
        )

    from pathlib import Path

    pdf_path = Path(contract.pdf_file_path or "")
    envelope_id = create_envelope_from_pdf(
        pdf_path=pdf_path,
        email_subject=f"Promesa de Venta — {property_listing.title[:80]}",
        buyer_name=transaction.buyer_name,
        buyer_email=_signer_email(SignatureRole.BUYER, transaction),
        seller_name=transaction.seller_name,
        seller_email=_signer_email(SignatureRole.SELLER, transaction),
        transaction_id=transaction.id,
    )

    contract.docusign_envelope_id = envelope_id
    contract.docusign_status = "sent"
    transaction.updated_at = _utcnow()
    telemetry: dict[str, Any] = dict(transaction.signature_telemetry or {})
    telemetry["docusign"] = {
        "envelope_id": envelope_id,
        "status": "sent",
        "provider": "docusign",
        "created_at": _utcnow().isoformat(),
    }
    transaction.signature_telemetry = telemetry

    session.add(contract)
    session.add(transaction)
    session.commit()
    session.refresh(contract)
    session.refresh(transaction)
    return transaction, contract, property_listing


def get_embedded_signing_url(
    session: Session,
    transaction_id: str,
    role: SignatureRole,
    return_url: str,
) -> dict[str, str]:
    """Return one-time embedded ceremony URL for buyer or seller."""
    _require_docusign_enabled()
    transaction, contract, _ = get_latest_legal_contract(session, transaction_id)

    if not contract.docusign_envelope_id:
        raise HTTPException(status_code=400, detail="Create DocuSign envelope first")

    signer_name = (
        transaction.buyer_name if role == SignatureRole.BUYER else transaction.seller_name
    )
    url = create_embedded_signing_url(
        envelope_id=contract.docusign_envelope_id,
        transaction_id=transaction.id,
        role=role,
        signer_name=signer_name,
        signer_email=_signer_email(role, transaction),
        return_url=return_url,
    )
    return {"signing_url": url, "role": role.value, "envelope_id": contract.docusign_envelope_id}


def apply_connect_event(
    session: Session,
    *,
    envelope_id: str,
    envelope_status: str,
) -> None:
    """Update contract/transaction from DocuSign Connect webhook."""
    contract = session.exec(
        select(LegalContract).where(LegalContract.docusign_envelope_id == envelope_id)
    ).first()
    if not contract:
        logger.warning("Connect event for unknown envelope_id=%s", envelope_id)
        return

    contract.docusign_status = envelope_status
    transaction = session.get(TransactionSession, contract.transaction_session_id)
    if not transaction:
        return

    telemetry: dict[str, Any] = dict(transaction.signature_telemetry or {})
    docusign_meta = dict(telemetry.get("docusign", {}))
    docusign_meta["status"] = envelope_status
    docusign_meta["last_event_at"] = _utcnow().isoformat()
    telemetry["docusign"] = docusign_meta
    transaction.signature_telemetry = telemetry
    transaction.updated_at = _utcnow()

    if envelope_status == "completed":
        now = _utcnow()
        if transaction.buyer_signed_at is None:
            transaction.buyer_signed_at = now
        if transaction.seller_signed_at is None:
            transaction.seller_signed_at = now
        transaction.status = TransactionSessionStatus.EXECUTED
        docusign_meta["completed_at"] = now.isoformat()
        telemetry["docusign"] = docusign_meta
        transaction.signature_telemetry = telemetry

    session.add(contract)
    session.add(transaction)
    session.commit()