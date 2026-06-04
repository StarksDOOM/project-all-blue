"""
DocuSign Embedded Signing (Recipient View) URL generation.
"""

from __future__ import annotations

import logging

from docusign_esign import EnvelopesApi, RecipientViewRequest

from config.docusign_settings import get_docusign_settings
from models import SignatureRole
from services.docusign.client import DocusignClient

logger = logging.getLogger(__name__)


def _client_user_id(transaction_id: str, role: SignatureRole) -> str:
    suffix = "buyer" if role == SignatureRole.BUYER else "seller"
    return f"{transaction_id}-{suffix}"


def create_embedded_signing_url(
    *,
    envelope_id: str,
    transaction_id: str,
    role: SignatureRole,
    signer_name: str,
    signer_email: str,
    return_url: str,
    ping_url: str | None = None,
) -> str:
    """Return a one-time embedded signing ceremony URL for the given role."""
    settings = get_docusign_settings()
    client = DocusignClient(settings)
    api_client = client.authorized_api_client()
    envelopes_api = EnvelopesApi(api_client)

    view_request = RecipientViewRequest(
        authentication_method="none",
        client_user_id=_client_user_id(transaction_id, role),
        recipient_id="1" if role == SignatureRole.BUYER else "2",
        return_url=return_url,
        user_name=signer_name,
        email=signer_email,
        ping_frequency="600",
        ping_url=ping_url or return_url,
    )

    view = envelopes_api.create_recipient_view(
        settings.api_account_id,
        envelope_id,
        recipient_view_request=view_request,
    )
    url = view.url
    if not url:
        raise RuntimeError("DocuSign create_recipient_view returned empty url")
    logger.info(
        "Embedded signing URL created envelope_id=%s role=%s",
        envelope_id,
        role.value,
    )
    return url