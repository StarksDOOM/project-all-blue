"""
Download the certified combined PDF from DocuSign after envelope completion.
"""

from __future__ import annotations

import logging

from docusign_esign import EnvelopesApi

from config.docusign_settings import get_docusign_settings
from services.docusign.client import DocusignClient

logger = logging.getLogger(__name__)

COMBINED_DOCUMENT_ID = "combined"


def download_completed_envelope_pdf(envelope_id: str) -> bytes:
    """Fetch the tamper-evident combined PDF bytes for a completed envelope."""
    settings = get_docusign_settings()
    client = DocusignClient(settings)
    api_client = client.authorized_api_client()
    envelopes_api = EnvelopesApi(api_client)
    pdf_bytes = envelopes_api.get_document(
        settings.api_account_id,
        envelope_id,
        COMBINED_DOCUMENT_ID,
    )
    if not pdf_bytes:
        raise RuntimeError(f"DocuSign returned empty combined PDF for envelope {envelope_id}")
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin-1")
    logger.info(
        "Downloaded DocuSign combined PDF envelope_id=%s bytes=%s",
        envelope_id,
        len(pdf_bytes),
    )
    return pdf_bytes