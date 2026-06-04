"""
Phase 6 — extensible post-execution notification engine (audit logs + email stub).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from models import LegalContract, PropertyListing, TransactionSession

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_execution_audit_event(
    *,
    transaction: TransactionSession,
    contract: LegalContract,
    property_listing: PropertyListing,
    audit_certificate_path: str | None,
) -> None:
    """Structured JSON audit log for SIEM / log aggregation."""
    payload: dict[str, Any] = {
        "event": "transaction.executed",
        "timestamp": _utcnow_iso(),
        "transaction_id": transaction.id,
        "property_id": transaction.property_id,
        "property_remote_id": property_listing.remote_id,
        "property_title": property_listing.title,
        "status": transaction.status.value,
        "esign_envelope_id": contract.docusign_envelope_id,
        "esign_status": contract.docusign_status,
        "document_hash": contract.document_hash,
        "audit_certificate_path": audit_certificate_path,
        "buyer_signed_at": (
            transaction.buyer_signed_at.isoformat() if transaction.buyer_signed_at else None
        ),
        "seller_signed_at": (
            transaction.seller_signed_at.isoformat() if transaction.seller_signed_at else None
        ),
    }
    logger.info("AUDIT %s", json.dumps(payload, ensure_ascii=False))


def send_execution_summary_email(
    *,
    transaction: TransactionSession,
    contract: LegalContract,
    property_listing: PropertyListing,
) -> None:
    """
    Stub for Amazon SES / Resend integration.

    Reads optional ``TRANSACTION_COORDINATOR_EMAIL`` and ``AGENT_NOTIFICATION_EMAIL``.
    """
    coordinator = os.getenv("TRANSACTION_COORDINATOR_EMAIL", "").strip()
    agent_email = os.getenv("AGENT_NOTIFICATION_EMAIL", property_listing.agent_email or "").strip()

    if not coordinator and not agent_email:
        logger.info(
            "execution_summary_email_skipped transaction_id=%s reason=no_recipients_configured",
            transaction.id,
        )
        return

    subject = f"[All Blue] Transacción ejecutada — {property_listing.title[:60]}"
    body = (
        f"La Promesa de Venta fue sellada.\n\n"
        f"Transaction ID: {transaction.id}\n"
        f"Property: {property_listing.title} (#{property_listing.remote_id})\n"
        f"DocuSign envelope: {contract.docusign_envelope_id}\n"
        f"SHA-256: {contract.document_hash}\n"
    )
    logger.info(
        "execution_summary_email_stub transaction_id=%s to=%s subject=%s body_preview=%s",
        transaction.id,
        [e for e in (coordinator, agent_email) if e],
        subject,
        body[:120],
    )


def dispatch_post_execution_notifications(
    *,
    transaction: TransactionSession,
    contract: LegalContract,
    property_listing: PropertyListing,
    audit_certificate_path: str | None,
) -> None:
    """Fan-out audit log + email stub after EXECUTED settlement."""
    log_execution_audit_event(
        transaction=transaction,
        contract=contract,
        property_listing=property_listing,
        audit_certificate_path=audit_certificate_path,
    )
    send_execution_summary_email(
        transaction=transaction,
        contract=contract,
        property_listing=property_listing,
    )