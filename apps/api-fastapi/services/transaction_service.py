"""
Phase 4 — transaction session orchestration (boundary layer for legal generation).

Delegates document text compilation to ``contract_generator``; persists ``LegalContract`` rows.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from models import LegalContract, PropertyListing, TransactionSession, TransactionSessionStatus
from services.contract_generator import compile_promesa_de_venta
from services.contract_service import resolve_property

logger = logging.getLogger(__name__)

CONTRACT_STORAGE_DIR = Path(__file__).resolve().parents[1] / "storage" / "legal_contracts"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_document(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def create_transaction_session(
    session: Session,
    *,
    property_id: str,
    buyer_name: str,
    buyer_id_doc: str,
    seller_name: str,
    seller_id_doc: str,
    agreed_price: float,
    currency: str = "USD",
) -> TransactionSession:
    """Initialize a DRAFT transaction for a resolved property."""
    try:
        property_listing = resolve_property(session, property_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Property resolution failed for transaction: %s", property_id)
        raise HTTPException(status_code=500, detail="Property resolution failed") from exc

    if agreed_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="agreed_price must be greater than zero",
        )

    transaction = TransactionSession(
        property_id=property_listing.id,
        buyer_name=buyer_name.strip(),
        buyer_id_doc=buyer_id_doc.strip(),
        seller_name=seller_name.strip(),
        seller_id_doc=seller_id_doc.strip(),
        agreed_price=round(float(agreed_price), 2),
        currency=(currency or "USD").upper(),
        status=TransactionSessionStatus.DRAFT,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    logger.info(
        "Transaction session created id=%s property_id=%s",
        transaction.id,
        property_listing.id,
    )
    return transaction


def get_transaction_session(
    session: Session,
    transaction_id: str,
) -> TransactionSession:
    row = session.get(TransactionSession, transaction_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found",
        )
    return row


def generate_legal_contract(
    session: Session,
    transaction_id: str,
) -> tuple[TransactionSession, LegalContract, PropertyListing]:
    """Run interpolation and persist a new ``LegalContract`` version."""
    transaction = get_transaction_session(session, transaction_id)
    property_listing = resolve_property(session, transaction.property_id)

    try:
        document_body = compile_promesa_de_venta(property_listing, transaction)
    except ValueError as exc:
        logger.warning("Contract generation validation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Contract generation failed transaction_id=%s", transaction_id)
        raise HTTPException(
            status_code=500,
            detail="Legal contract compilation failed",
        ) from exc

    version_hash = _hash_document(document_body)
    CONTRACT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{transaction_id}_{version_hash[:12]}.md"
    file_path = CONTRACT_STORAGE_DIR / file_name
    try:
        file_path.write_text(document_body, encoding="utf-8")
    except OSError as exc:
        logger.exception("Unable to write contract file: %s", file_path)
        raise HTTPException(status_code=500, detail="Contract file write failed") from exc

    contract = LegalContract(
        transaction_session_id=transaction.id,
        property_id=transaction.property_id,
        file_path=str(file_path),
        storage_url=None,
        document_body=document_body,
        generated_at=_utcnow(),
        version_hash=version_hash,
    )
    transaction.status = TransactionSessionStatus.GENERATED
    transaction.updated_at = _utcnow()

    session.add(contract)
    session.add(transaction)
    session.commit()
    session.refresh(contract)
    session.refresh(transaction)

    logger.info(
        "Legal contract generated id=%s transaction_id=%s hash=%s",
        contract.id,
        transaction.id,
        version_hash[:12],
    )
    return transaction, contract, property_listing


def get_latest_legal_contract(
    session: Session,
    transaction_id: str,
) -> tuple[TransactionSession, LegalContract, PropertyListing]:
    """Return the most recent legal contract for a transaction session."""
    transaction = get_transaction_session(session, transaction_id)
    property_listing = resolve_property(session, transaction.property_id)

    contract = session.exec(
        select(LegalContract)
        .where(LegalContract.transaction_session_id == transaction_id)
        .order_by(LegalContract.generated_at.desc())
    ).first()

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No legal contract generated for this transaction yet",
        )
    return transaction, contract, property_listing


def transaction_to_dict(
    transaction: TransactionSession,
    property_listing: PropertyListing | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": transaction.id,
        "property_id": transaction.property_id,
        "buyer_name": transaction.buyer_name,
        "buyer_id_doc": transaction.buyer_id_doc,
        "seller_name": transaction.seller_name,
        "seller_id_doc": transaction.seller_id_doc,
        "agreed_price": transaction.agreed_price,
        "currency": transaction.currency,
        "status": transaction.status.value,
        "created_at": transaction.created_at.isoformat(),
        "updated_at": transaction.updated_at.isoformat(),
        "buyer_signed_at": (
            transaction.buyer_signed_at.isoformat()
            if transaction.buyer_signed_at
            else None
        ),
        "seller_signed_at": (
            transaction.seller_signed_at.isoformat()
            if transaction.seller_signed_at
            else None
        ),
        "signature_telemetry": transaction.signature_telemetry or {},
        "is_locked": transaction.status.value in ("GENERATED", "EXECUTED"),
    }
    if property_listing is not None:
        payload["property_remote_id"] = property_listing.remote_id
        payload["property_title"] = property_listing.title
    return payload


def contract_to_dict(
    contract: LegalContract,
    transaction: TransactionSession | None,
    property_listing: PropertyListing,
) -> dict[str, Any]:
    return {
        "id": contract.id,
        "transaction_session_id": contract.transaction_session_id,
        "file_path": contract.file_path,
        "storage_url": contract.storage_url,
        "document_body": contract.document_body,
        "generated_at": contract.generated_at.isoformat(),
        "version_hash": contract.version_hash,
        "document_hash": contract.document_hash,
        "pdf_file_path": contract.pdf_file_path,
        "has_secure_pdf": bool(contract.document_hash and contract.pdf_file_path),
        "docusign_envelope_id": contract.docusign_envelope_id,
        "docusign_status": contract.docusign_status,
        "has_audit_certificate": bool(contract.audit_certificate_path),
        "audit_certificate_path": contract.audit_certificate_path,
        "transaction": transaction_to_dict(transaction, property_listing) if transaction is not None else None,
        "property": {
            "id": property_listing.id,
            "remote_id": property_listing.remote_id,
            "title": property_listing.title,
            "sector": property_listing.sector,
            "province": property_listing.province,
            "bathrooms": property_listing.bathrooms,
            "bedrooms": property_listing.bedrooms,
            "square_meters": property_listing.square_meters,
            "sqm_land": property_listing.sqm_land,
        },
        "signing_url": contract.signing_url,
    }