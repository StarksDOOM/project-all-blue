"""
Create DocuSign envelopes from the tamper-sealed ReportLab PDF.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from docusign_esign import (
    Document,
    EnvelopeDefinition,
    EnvelopesApi,
    Recipients,
    Signer,
    SignHere,
    Tabs,
)

from config.docusign_settings import get_docusign_settings
from services.docusign.client import DocusignClient

logger = logging.getLogger(__name__)


def _signer(
    *,
    role_name: str,
    name: str,
    email: str,
    recipient_id: str,
    routing_order: str,
    client_user_id: str,
    y_position: str,
) -> Signer:
    sign_here = SignHere(
        document_id="1",
        page_number="1",
        x_position="72",
        y_position=y_position,
    )
    return Signer(
        email=email,
        name=name,
        recipient_id=recipient_id,
        routing_order=routing_order,
        role_name=role_name,
        client_user_id=client_user_id,
        tabs=Tabs(sign_here_tabs=[sign_here]),
    )


def create_envelope_from_pdf(
    *,
    pdf_path: Path,
    email_subject: str,
    buyer_name: str,
    buyer_email: str,
    seller_name: str,
    seller_email: str,
    transaction_id: str,
) -> str:
    """
    Upload PDF document and create a sent envelope with buyer + seller signers.

    Returns envelope ID (GUID).
    """
    settings = get_docusign_settings()
    client = DocusignClient(settings)
    api_client = client.authorized_api_client()
    envelopes_api = EnvelopesApi(api_client)

    document_bytes = pdf_path.read_bytes()
    b64 = base64.b64encode(document_bytes).decode("ascii")

    document = Document(
        document_base64=b64,
        name=pdf_path.name,
        file_extension="pdf",
        document_id="1",
    )

    buyer_signer = _signer(
        role_name="Buyer",
        name=buyer_name,
        email=buyer_email,
        recipient_id="1",
        routing_order="1",
        client_user_id=f"{transaction_id}-buyer",
        y_position="520",
    )
    seller_signer = _signer(
        role_name="Seller",
        name=seller_name,
        email=seller_email,
        recipient_id="2",
        routing_order="2",
        client_user_id=f"{transaction_id}-seller",
        y_position="620",
    )

    envelope_definition = EnvelopeDefinition(
        email_subject=email_subject,
        documents=[document],
        recipients=Recipients(signers=[buyer_signer, seller_signer]),
        status="sent",
    )

    summary = envelopes_api.create_envelope(
        settings.api_account_id,
        envelope_definition=envelope_definition,
    )
    envelope_id = summary.envelope_id
    if not envelope_id:
        raise RuntimeError("DocuSign create_envelope returned no envelope_id")
    logger.info("DocuSign envelope created envelope_id=%s transaction_id=%s", envelope_id, transaction_id)
    return envelope_id