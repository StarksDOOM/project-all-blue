"""
Phase 5 — multi-party digital execution and tamper-evident PDF verification.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, status
from sqlmodel import Session

from models import LegalContract, SignatureRole, TransactionSession, TransactionSessionStatus
from services.pdf_renderer import sha256_file
from services.transaction_service import get_latest_legal_contract

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _assert_pdf_integrity(contract: LegalContract) -> str:
    if not contract.pdf_file_path or not contract.document_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Secure PDF has not been generated for this transaction",
        )
    pdf_path = Path(contract.pdf_file_path)
    if not pdf_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Secure PDF file missing on disk; regenerate PDF before signing",
        )
    live_hash = sha256_file(pdf_path)
    if live_hash != contract.document_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PDF tamper-evidence check failed: document_hash mismatch",
        )
    return live_hash


def _build_signing_hash(
    *,
    role: SignatureRole,
    transaction_id: str,
    document_hash: str,
    signed_at: datetime,
    client_ip: str,
    user_agent: str,
) -> str:
    payload = (
        f"{role.value}|{transaction_id}|{document_hash}|"
        f"{signed_at.isoformat()}|{client_ip}|{user_agent}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_secure_pdf(
    session: Session,
    transaction_id: str,
) -> tuple[TransactionSession, LegalContract, Any]:
    """Render PDF from latest markdown contract and persist tamper hash."""
    from services.transaction_service import get_latest_legal_contract

    transaction, contract, property_listing = get_latest_legal_contract(session, transaction_id)

    if transaction.status not in (
        TransactionSessionStatus.GENERATED,
        TransactionSessionStatus.EXECUTED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Markdown contract must be generated before PDF compilation",
        )

    try:
        from services.pdf_renderer import write_secure_pdf

        pdf_path, document_hash = write_secure_pdf(transaction.id, contract.document_body)
    except ValueError as exc:
        logger.warning("PDF generation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("PDF generation failed transaction_id=%s", transaction_id)
        raise HTTPException(status_code=500, detail="Secure PDF compilation failed") from exc

    contract.pdf_file_path = str(pdf_path)
    contract.document_hash = document_hash
    transaction.updated_at = _utcnow()

    session.add(contract)
    session.add(transaction)
    session.commit()
    session.refresh(contract)
    session.refresh(transaction)

    return transaction, contract, property_listing


def execute_signature(
    session: Session,
    transaction_id: str,
    role: SignatureRole,
    request: Request,
) -> tuple[TransactionSession, LegalContract, Any]:
    """Record buyer/seller signature; transition to EXECUTED when both parties signed."""
    transaction, contract, property_listing = get_latest_legal_contract(session, transaction_id)

    if transaction.status == TransactionSessionStatus.EXECUTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction is already fully executed",
        )
    if transaction.status != TransactionSessionStatus.GENERATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction must be in GENERATED state to accept signatures",
        )

    document_hash = _assert_pdf_integrity(contract)
    signed_at = _utcnow()
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    signing_hash = _build_signing_hash(
        role=role,
        transaction_id=transaction.id,
        document_hash=document_hash,
        signed_at=signed_at,
        client_ip=client_ip,
        user_agent=user_agent,
    )

    telemetry: dict[str, Any] = dict(transaction.signature_telemetry or {})
    signatures: list[dict[str, Any]] = list(telemetry.get("signatures", []))

    if role == SignatureRole.BUYER:
        if transaction.buyer_signed_at is not None:
            raise HTTPException(status_code=400, detail="Buyer has already signed")
        transaction.buyer_signed_at = signed_at
    else:
        if transaction.seller_signed_at is not None:
            raise HTTPException(status_code=400, detail="Seller has already signed")
        transaction.seller_signed_at = signed_at

    signatures.append(
        {
            "role": role.value,
            "signed_at": signed_at.isoformat(),
            "signing_hash": signing_hash,
            "document_hash": document_hash,
            "client_ip": client_ip,
            "user_agent": user_agent,
        }
    )
    telemetry["signatures"] = signatures
    telemetry["last_document_hash"] = document_hash
    transaction.signature_telemetry = telemetry
    transaction.updated_at = signed_at

    if transaction.buyer_signed_at and transaction.seller_signed_at:
        transaction.status = TransactionSessionStatus.EXECUTED

    session.add(transaction)
    session.commit()
    session.refresh(transaction)

    logger.info(
        "Signature recorded transaction_id=%s role=%s status=%s",
        transaction.id,
        role.value,
        transaction.status.value,
    )
    return transaction, contract, property_listing