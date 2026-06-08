"""
DocuSeal Settings.

Loads configuration parameters for the DocuSeal service from the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class DocuSealSettings:
    """
    Configuration settings for DocuSeal client and webhook validator.

    Attributes:
        api_key (str): Authentication token for DocuSeal API requests.
        template_id (str): Default DocuSeal template ID used for contract generation.
        base_url (str): Target DocuSeal host (API base URL).
        webhook_secret (str): Secret key used to verify incoming webhook signatures.
    """

    api_key: str
    template_id: str
    base_url: str
    webhook_secret: str

    @property
    def is_enabled(self) -> bool:
        """
        Check if DocuSeal configuration is active.

        Returns:
            bool: True if key and template are set, False otherwise.
        """
        return bool(self.api_key) and bool(self.template_id)


@lru_cache
def get_docuseal_settings() -> DocuSealSettings:
    """
    Retrieve or initialize the cached DocuSeal settings instance.

    Returns:
        DocuSealSettings: Configuration instance loaded from environment variables.
    """
    api_key = os.getenv("DOCUSEAL_API_KEY", "").strip()
    template_id = os.getenv("DOCUSEAL_TEMPLATE_ID", "").strip()
    base_url = os.getenv("DOCUSEAL_BASE_URL", "https://api.docuseal.com").strip().rstrip("/")
    webhook_secret = os.getenv("DOCUSEAL_WEBHOOK_SECRET", "").strip()

    return DocuSealSettings(
        api_key=api_key,
        template_id=template_id,
        base_url=base_url,
        webhook_secret=webhook_secret,
    )
