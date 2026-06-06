"""
DocuSign JWT M2M Authenticator for Stream 6 Phase 1.0.
"""

from __future__ import annotations

import logging
from docusign_esign import ApiClient
from config.docusign_settings import DocusignSettings, get_docusign_settings

logger = logging.getLogger(__name__)

JWT_SCOPES = ["signature", "impersonation"]


class DocuSignJWTAuthenticator:
    """
    Stateless authenticator responsible for exchanging DocuSign credentials and
    an RSA Private Key for a short-lived OAuth access token.

    Purpose:
        Perform Machine-to-Machine JWT Grant token acquisition with the DocuSign
        OAuth server using the official docusign_esign SDK.

    Lifecycle:
        Stateless and request-scoped. Created dynamically when authenticating a
        client API request. The instantiated class performs the M2M handshake
        and yields an authorized ApiClient instance.

    Thread-safety:
        Fully thread-safe. Instances do not maintain long-lived mutable state or
        shared database connections.

    Collaborators:
        - DocusignSettings (configuration provider)
        - docusign_esign.ApiClient (authenticating client wrapper)

    Invariants:
        - Never stores or caches the returned access token inside the class
          instance (the client wrapper manages its default headers).
        - Always requests 'signature' and 'impersonation' scopes for JWT grant.

    Parameters:
        None.
    """

    def __init__(self, settings: DocusignSettings | None = None) -> None:
        """
        Purpose:
            Initialize the authenticator instance with custom or default settings.

        Lifecycle:
            Called upon dependency resolution inside route handlers.

        Thread-safety:
            Safe.

        Collaborators:
            - DocusignSettings

        Invariants:
            - If settings is not provided, falls back to get_docusign_settings().

        Parameters:
            settings (DocusignSettings | None): The configuration properties.

        Returns:
            None.

        Raises:
            None.

        Side Effects:
            None.
        """
        self.settings = settings or get_docusign_settings()

    def authenticate(self) -> ApiClient:
        """
        Purpose:
            Execute the OAuth JWT Grant token exchange and return a fully
            authorized docusign_esign.ApiClient.

        Lifecycle:
            Invoked before making any API request to DocuSign envelope endpoints.

        Thread-safety:
            Safe.

        Collaborators:
            - ApiClient (exchanges token and carries authentication header)

        Invariants:
            - Expiration is set to 3600 seconds.
            - Relies on settings integration key, user ID, host name, and private key bytes.

        Parameters:
            None.

        Returns:
            ApiClient: Authorized API client ready for calling API routers.

        Raises:
            FileNotFoundError: If the RSA private key file cannot be loaded.
            RuntimeError: If the token exchange returns an empty access token.

        Side Effects:
            - Reads private key bytes from the local disk path.
            - Makes an outbound HTTPS request to the DocuSign OAuth host.
        """
        settings = self.settings
        client = ApiClient()
        client.set_base_path(settings.base_url)
        client.set_oauth_host_name(settings.oauth_host)

        private_key = settings.private_key_bytes()
        token = client.request_jwt_user_token(
            client_id=settings.integration_key,
            user_id=settings.user_id,
            oauth_host_name=settings.oauth_host,
            private_key_bytes=private_key,
            expires_in=3600,
            scopes=JWT_SCOPES,
        )
        access = token.access_token
        if not access:
            raise RuntimeError("DocuSign JWT Grant returned empty access_token")

        client.set_default_header("Authorization", f"Bearer {access}")
        logger.info("DocuSign JWT authentication succeeded")
        return client
