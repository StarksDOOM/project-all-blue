"""
DocuSign Connect webhook and signing configuration routes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlmodel import Session

from config.docusign_settings import get_docusign_settings
from database import get_db_session
from schemas.docusign import SigningConfigResponse
from services.docusign.webhook import (
    envelope_id_from_event,
    envelope_status_from_event,
    parse_connect_payload,
    verify_connect_hmac,
)
from services.docusign_orchestrator import apply_connect_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["docusign"])


@router.get("/signing/config", response_model=SigningConfigResponse)
def signing_config() -> dict:
    """Public signing provider flag for the Next.js dashboard."""
    settings = get_docusign_settings()
    if settings.is_enabled:
        return {"provider": "docusign", "docusign_configured": True}
    return {"provider": "internal", "docusign_configured": False}


@router.post("/docusign/connect/webhook", status_code=status.HTTP_200_OK)
async def docusign_connect_webhook(
    request: Request,
    session: Session = Depends(get_db_session),
    x_docusign_signature_1: str | None = Header(default=None, alias="X-DocuSign-Signature-1"),
) -> dict[str, str]:
    """
    DocuSign Connect callback (configure in Admin → Connect → HMAC secret).

    Marks transaction EXECUTED when envelope status is ``completed``.
    """
    raw = await request.body()
    if not verify_connect_hmac(raw, x_docusign_signature_1):
        raise HTTPException(status_code=401, detail="Invalid Connect HMAC signature")

    events = parse_connect_payload(raw)
    processed = 0
    for event in events:
        envelope_id = envelope_id_from_event(event)
        envelope_status = envelope_status_from_event(event)
        if not envelope_id or not envelope_status:
            continue
        apply_connect_event(
            session,
            envelope_id=envelope_id,
            envelope_status=envelope_status,
        )
        processed += 1
        logger.info(
            "Connect processed envelope_id=%s status=%s",
            envelope_id,
            envelope_status,
        )

    return {"status": "ok", "processed": str(processed)}