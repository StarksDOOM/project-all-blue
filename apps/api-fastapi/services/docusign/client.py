"""
DocuSign ApiClient with JWT Grant token caching (machine-to-machine).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from docusign_esign import ApiClient

from config.docusign_settings import DocusignSettings, get_docusign_settings

logger = logging.getLogger(__name__)

JWT_SCOPES = ["signature", "impersonation"]

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


class DocusignClient:
    """Thin wrapper around ``docusign_esign.ApiClient`` with JWT lifecycle."""

    def __init__(self, settings: DocusignSettings | None = None) -> None:
        self.settings = settings or get_docusign_settings()

    def _api_client(self) -> ApiClient:
        settings = self.settings
        client = ApiClient()
        client.set_base_path(settings.base_url)
        client.set_oauth_host_name(settings.oauth_host)
        return client

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        now = time.time()
        if (
            not force_refresh
            and _token_cache["access_token"]
            and now < float(_token_cache["expires_at"]) - 120
        ):
            return str(_token_cache["access_token"])

        settings = self.settings
        api_client = self._api_client()
        private_key = settings.private_key_bytes()
        token = api_client.request_jwt_user_token(
            client_id=settings.integration_key,
            user_id=settings.user_id,
            oauth_host_name=settings.oauth_host,
            private_key_bytes=private_key,
            expires_in=3600,
            scopes=JWT_SCOPES,
        )
        access = token.access_token
        if not access:
            raise RuntimeError("DocuSign JWT grant returned empty access_token")

        _token_cache["access_token"] = access
        _token_cache["expires_at"] = now + 3500
        logger.info("DocuSign JWT access token acquired (cached ~58m)")
        return access

    def authorized_api_client(self) -> ApiClient:
        client = self._api_client()
        token = self.get_access_token()
        client.set_default_header("Authorization", f"Bearer {token}")
        return client