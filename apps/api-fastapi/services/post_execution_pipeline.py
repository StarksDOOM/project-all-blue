"""
Phase 6 — post-EXECUTED automation (DocuSign PDF ingest, audit certificate, notifications).

Invoked from FastAPI ``BackgroundTasks`` after Connect webhook settlement.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session

from config.docusign_settings import get_docusign_settings
from database import engine
from models import TransactionSessionStatus
from services.audit_certificate_generator import AuditCertificateInput, write_audit_certificate
from services.docusign.document_download import download_completed_envelope_pdf
from services.docusign.webhook import extract_signer_metadata_from_event
from services.notification_service import dispatch_post_execution_notifications
from services.pdf_renderer import sha256_bytes
from services.transaction_service import get_latest_legal_contract

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ingest_docusign_completed_pdf(
    *,
    envelope_id: str,
    transaction_id: str,
    existing_path: str | None,
) -> tuple[Path, str]:
    """Download certified PDF and overwrite local secure storage."""
    pdf_bytes = download_completed_envelope_pdf(envelope_id)
    document_hash = sha256_bytes(pdf_bytes)

    base_dir = Path(__file__).resolve().parents[1] / "storage" / "secure_pdfs"
    base_dir.mkdir(parents=True, exist_ok=True)

    if existing_path:
        target = Path(existing_path)
    else:
        target = base_dir / f"{transaction_id}_{document_hash[:12]}_signed.pdf"

    target.write_bytes(pdf_bytes)
    logger.info(
        "Ingested DocuSign signed PDF transaction_id=%s path=%s",
        transaction_id,
        target.name,
    )
    return target, document_hash


def run_post_execution_pipeline(
    transaction_id: str,
    connect_event: dict[str, Any] | None = None,
) -> None:
    """
    Background worker: certified PDF ingest, audit certificate, notifications.

    Uses a dedicated DB session (safe outside request lifecycle).
    """
    try:
        with Session(engine) as session:
            transaction, contract, property_listing = get_latest_legal_contract(
                session,
                transaction_id,
            )

            if transaction.status != TransactionSessionStatus.EXECUTED:
                logger.warning(
                    "Post-execution skipped — not EXECUTED transaction_id=%s status=%s",
                    transaction_id,
                    transaction.status.value,
                )
                return

            signer_meta: dict[str, dict[str, str]] = {}
            telemetry = dict(transaction.signature_telemetry or {})
            docusign_meta = dict(telemetry.get("docusign", {}))

            if connect_event:
                signer_meta = extract_signer_metadata_from_event(connect_event)
                docusign_meta["signers"] = signer_meta
                telemetry["docusign"] = docusign_meta
                transaction.signature_telemetry = telemetry

            if contract.docusign_envelope_id and get_docusign_settings().is_enabled:
                try:
                    pdf_path, document_hash = _ingest_docusign_completed_pdf(
                        envelope_id=contract.docusign_envelope_id,
                        transaction_id=transaction.id,
                        existing_path=contract.pdf_file_path,
                    )
                    contract.pdf_file_path = str(pdf_path)
                    contract.document_hash = document_hash
                except Exception:
                    logger.exception(
                        "DocuSign PDF ingest failed transaction_id=%s",
                        transaction_id,
                    )

            if not signer_meta:
                stored = docusign_meta.get("signers")
                if isinstance(stored, dict):
                    signer_meta = stored

            if not signer_meta:
                signer_meta = {
                    "buyer": {
                        "role": "Buyer",
                        "name": transaction.buyer_name,
                        "email": "—",
                        "signed_at": (
                            transaction.buyer_signed_at.isoformat()
                            if transaction.buyer_signed_at
                            else "—"
                        ),
                    },
                    "seller": {
                        "role": "Seller",
                        "name": transaction.seller_name,
                        "email": "—",
                        "signed_at": (
                            transaction.seller_signed_at.isoformat()
                            if transaction.seller_signed_at
                            else "—"
                        ),
                    },
                }

            executed_at = (
                transaction.buyer_signed_at or transaction.seller_signed_at or _utcnow()
            ).isoformat()

            cert_input = AuditCertificateInput(
                transaction_id=transaction.id,
                property_id=transaction.property_id,
                property_title=property_listing.title,
                esign_envelope_id=contract.docusign_envelope_id or "—",
                esign_status=contract.docusign_status or "completed",
                document_hash=contract.document_hash or "—",
                buyer=signer_meta.get("buyer", {}),
                seller=signer_meta.get("seller", {}),
                executed_at=executed_at,
            )
            cert_path = write_audit_certificate(cert_input)
            contract.audit_certificate_path = str(cert_path)

            session.add(contract)
            session.add(transaction)
            session.commit()

            dispatch_post_execution_notifications(
                transaction=transaction,
                contract=contract,
                property_listing=property_listing,
                audit_certificate_path=str(cert_path),
            )
    except Exception:
        logger.exception("Post-execution pipeline failed transaction_id=%s", transaction_id)