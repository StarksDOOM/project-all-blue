"""
DocuSeal Webhook Signature Validator.

Verifies payload authenticity using DocuSeal signing secret and HMAC-SHA256.
"""

from __future__ import annotations

import hmac
import hashlib
import logging
from fastapi import HTTPException, status

from config.docuseal_settings import DocuSealSettings, get_docuseal_settings

logger = logging.getLogger(__name__)


class DocuSealWebhookValidator:
    """
    Stateless security validator responsible for authenticating DocuSeal webhook payloads.

    Purpose:
        Verify the raw request body bytes and the 'X-Docuseal-Signature' header,
        computing the expected HMAC-SHA256 hex digest, and comparing in constant time.

    Lifecycle:
        Stateless and request-scoped. Instantiated on-demand during webhook delivery.

    Thread-safety:
        Fully thread-safe as it maintains no mutable instance-level state.

    Collaborators:
        - DocuSealSettings (configuration settings provider)
        - hmac / hashlib (for cryptographic verification)

    Invariants:
        - If the HMAC secret is not configured in settings, signature validation is
          skipped (unsafe warning logged), allowing ease of developer environment testing.
        - Validation failures must always raise an HTTP 401 Unauthorized exception.
    """

    def __init__(self, settings: DocuSealSettings | None = None) -> None:
        """
        Initialize the DocuSealWebhookValidator.

        Parameters:
            settings (DocuSealSettings | None): Configuration properties. Defaults to global loader.
        """
        self.settings = settings or get_docuseal_settings()

    def verify(self, raw_body: bytes, signature_header: str | None) -> None:
        """
        Verify the signature of the DocuSeal webhook request.

        Parameters:
            raw_body (bytes): The raw request body bytes.
            signature_header (str | None): The value of the X-Docuseal-Signature header.

        Returns:
            None.

        Raises:
            HTTPException: 401 status code if validation fails or signature is invalid.
        """
        secret = self.settings.webhook_secret
        if not secret:
            logger.warning(
                "DOCUSEAL_WEBHOOK_SECRET is not configured in the environment. "
                "Webhook signature validation is skipped (unsafe for production)."
            )
            return

        if not signature_header:
            logger.warning("DocuSeal Webhook authentication failed: missing signature header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing DocuSeal signature header",
            )

        try:
            # Format: [timestamp].[signature]
            parts = signature_header.strip().split(".")
            if len(parts) != 2:
                raise ValueError("Signature header does not contain timestamp and signature parts")
            timestamp, signature = parts

            # Signed content: [timestamp].[raw_body]
            message = f"{timestamp}.".encode("utf-8") + raw_body

            # Compute HMAC-SHA256 hex digest
            hmac_obj = hmac.new(secret.encode("utf-8"), message, hashlib.sha256)
            expected_signature = hmac_obj.hexdigest()

        except Exception as exc:
            logger.warning("DocuSeal Webhook signature parsing/computation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid DocuSeal signature format",
            )

        # Constant-time comparison to mitigate timing attacks
        if not hmac.compare_digest(expected_signature, signature):
            logger.warning("DocuSeal Webhook authentication failed: signature mismatch")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid DocuSeal signature",
            )

        logger.info("DocuSeal webhook signature validation succeeded")
