"""
DocuSign Connect Webhook Signature Validator for Stream 6 Phase 1.1.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class DocuSignWebhookValidator:
    """
    Stateless security validator responsible for authenticating DocuSign Connect webhook payloads.

    Purpose:
        Ingest the raw request body bytes and the 'X-DocuSign-Signature-1' header,
        compute the Base64-encoded SHA-256 HMAC signature using the configured secret key,
        and perform a constant-time string comparison to authenticate the caller.

    Lifecycle:
        Stateless and request-scoped. Instantiated on-demand during webhook delivery
        routing to validate request payloads.

    Thread-safety:
        Fully thread-safe as it maintains no mutable instance-level state.

    Collaborators:
        - os (for retrieving environment secret key)
        - hmac / hashlib / base64 (for cryptographic validation)

    Invariants:
        - If the HMAC secret is not configured in the environment, signature validation
          is skipped (for developer environment convenience), but a warning is logged.
        - Validation failures must always raise an HTTP 401 Unauthorized exception.
    """

    def __init__(self, hmac_secret: str | None = None) -> None:
        """
        Purpose:
            Initialize the validator with an optional explicit secret or load from environment.

        Lifecycle:
            Called upon dependency resolution inside webhook route handlers.

        Thread-safety:
            Safe.

        Collaborators:
            - os.getenv (fallback secret lookup).

        Invariants:
            - Secret is loaded from 'DOCUSIGN_HMAC_SECRET' or falls back to 'DOCUSIGN_WEBHOOK_SECRET'.

        Parameters:
            hmac_secret (str | None): Explicit webhook HMAC secret key.

        Returns:
            None.

        Raises:
            None.

        Side Effects:
            Reads environment variables (idempotent).
        """
        self._hmac_secret = (
            hmac_secret
            or os.getenv("DOCUSIGN_HMAC_SECRET")
            or os.getenv("DOCUSIGN_WEBHOOK_SECRET")
        )

    def verify(self, raw_body: bytes, signature_header: str | None) -> None:
        """
        Purpose:
            Compute the expected HMAC signature and perform constant-time validation.

        Lifecycle:
            Invoked inside the webhook endpoint before processing payload content.

        Thread-safety:
            Safe for concurrent executions.

        Collaborators:
            - hmac.compare_digest (constant-time verification)
            - base64 (Base64 encoding/decoding)

        Invariants:
            - Raises HTTP 401 if the signature header is missing or mismatch.
            - Relies on constant-time string comparison to mitigate timing attacks.

        Parameters:
            raw_body (bytes): The raw request body bytes.
            signature_header (str | None): The signature string from the request headers.

        Returns:
            None.

        Raises:
            HTTPException: 401 status code if signature verification fails.

        Side Effects:
            - Logs warning message if the validation secret is missing.
        """
        secret = self._hmac_secret
        if not secret:
            logger.warning(
                "DOCUSIGN_HMAC_SECRET is not configured in the environment. "
                "Webhook signature validation is skipped (unsafe for production)."
            )
            return

        if not signature_header:
            logger.warning("DocuSign Webhook authentication failed: missing signature header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing DocuSign signature header",
            )

        # DocuSign Connect sign-1 header might contain the Base64 digest of the HMAC.
        # Compute the Base64 HMAC-SHA256 hash.
        hmac_obj = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256)
        expected_bytes = hmac_obj.digest()
        expected_base64 = base64.b64encode(expected_bytes).decode("utf-8")
        expected_hex = expected_bytes.hex()

        provided = signature_header.strip()

        # Support both Base64-encoded (requested) and Hex-encoded (backward compatibility/standard) signatures
        is_valid_base64 = hmac.compare_digest(expected_base64, provided)
        is_valid_hex = hmac.compare_digest(expected_hex, provided.lower())

        if not (is_valid_base64 or is_valid_hex):
            logger.warning("DocuSign Webhook authentication failed: signature mismatch")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid DocuSign signature",
            )

        logger.info("DocuSign Connect webhook HMAC validation succeeded")
