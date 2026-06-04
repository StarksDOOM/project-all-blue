"""
DocuSign Connect webhook verification and envelope status normalization.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from config.docusign_settings import get_docusign_settings

logger = logging.getLogger(__name__)


def verify_connect_hmac(raw_body: bytes, signature_header: str | None) -> bool:
    """
    Validate ``X-DocuSign-Signature-1`` (HMAC-SHA256 over raw body).

    When ``DOCUSIGN_WEBHOOK_SECRET`` is unset, verification is skipped (dev only).
    """
    secret = get_docusign_settings().webhook_secret
    if not secret:
        logger.warning("DOCUSIGN_WEBHOOK_SECRET unset — webhook HMAC verification skipped")
        return True
    if not signature_header:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = digest.hex()
    provided = signature_header.strip().lower()
    return hmac.compare_digest(expected, provided)


def parse_connect_payload(raw_body: bytes) -> list[dict[str, Any]]:
    """Extract envelope status events from Connect JSON (array or single object)."""
    data = json.loads(raw_body.decode("utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], dict):
            return [data["data"]]
        return [data]
    return []


def envelope_status_from_event(event: dict[str, Any]) -> str | None:
    """Map Connect payload to a normalized status string."""
    for key in ("status", "envelopeStatus"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value.lower()
    summary = event.get("envelopeSummary") or event.get("EnvelopeStatus")
    if isinstance(summary, dict):
        status = summary.get("status")
        if isinstance(status, str):
            return status.lower()
    return None


def envelope_id_from_event(event: dict[str, Any]) -> str | None:
    for key in ("envelopeId", "envelope_id"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    summary = event.get("envelopeSummary")
    if isinstance(summary, dict):
        eid = summary.get("envelopeId")
        if isinstance(eid, str):
            return eid
    return None


def _normalize_signer_block(raw: dict[str, Any], *, fallback_role: str) -> dict[str, str]:
    name = str(raw.get("name") or raw.get("userName") or "—")
    email = str(raw.get("email") or raw.get("emailAddress") or "—")
    signed_at = (
        raw.get("signedDateTime")
        or raw.get("signed_at")
        or raw.get("completedDateTime")
        or "—"
    )
    role = str(raw.get("roleName") or raw.get("role") or fallback_role)
    return {
        "role": role,
        "name": name,
        "email": email,
        "signed_at": str(signed_at),
    }


def extract_signer_metadata_from_event(event: dict[str, Any]) -> dict[str, dict[str, str]]:
    """
    Parse buyer/seller signing metadata from Connect JSON for audit certificate layout.
    """
    summary = event.get("envelopeSummary")
    if not isinstance(summary, dict):
        summary = event

    recipients = summary.get("recipients") if isinstance(summary.get("recipients"), dict) else {}
    signers = recipients.get("signers") if isinstance(recipients.get("signers"), list) else []

    buyer: dict[str, str] | None = None
    seller: dict[str, str] | None = None

    for index, signer in enumerate(signers):
        if not isinstance(signer, dict):
            continue
        role_label = str(signer.get("roleName") or "").lower()
        block = _normalize_signer_block(
            signer,
            fallback_role="Buyer" if index == 0 else "Seller",
        )
        if "buyer" in role_label or index == 0:
            buyer = block
        elif "seller" in role_label or index == 1:
            seller = block

    if buyer is None:
        buyer = {"role": "Buyer", "name": "—", "email": "—", "signed_at": "—"}
    if seller is None:
        seller = {"role": "Seller", "name": "—", "email": "—", "signed_at": "—"}

    return {"buyer": buyer, "seller": seller}