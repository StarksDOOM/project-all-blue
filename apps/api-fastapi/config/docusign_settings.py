"""
DocuSign JWT Grant settings loaded from environment.

Private key must exist at ``DOCUSIGN_PRIVATE_KEY_PATH`` (never commit the key file).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DocusignSettings:
    provider: str
    user_id: str
    api_account_id: str
    integration_key: str
    base_url: str
    oauth_host: str
    private_key_path: Path
    webhook_secret: str

    @property
    def is_enabled(self) -> bool:
        return (
            self.provider.strip().lower() == "docusign"
            and bool(self.user_id)
            and bool(self.api_account_id)
            and bool(self.integration_key)
        )

    def private_key_bytes(self) -> bytes:
        path = self.private_key_path
        if not path.is_file():
            raise FileNotFoundError(
                f"DocuSign RSA private key not found at {path}. "
                "Download from DocuSign Admin → Apps and Keys → Generate RSA."
            )
        return path.read_bytes()


@lru_cache
def get_docusign_settings() -> DocusignSettings:
    root = _repo_root()
    key_path = os.getenv("DOCUSIGN_PRIVATE_KEY_PATH", "storage/certs/docusign_private.key")
    resolved_key = Path(key_path)
    if not resolved_key.is_absolute():
        resolved_key = root / resolved_key

    base_url = os.getenv(
        "DOCUSIGN_BASE_URL",
        "https://demo.docusign.net/restapi",
    ).rstrip("/")

    return DocusignSettings(
        provider=os.getenv("DOCUSIGN_PROVIDER", "").strip(),
        user_id=os.getenv("DOCUSIGN_USER_ID", "").strip(),
        api_account_id=os.getenv("DOCUSIGN_API_ACCOUNT_ID", "").strip(),
        integration_key=os.getenv("DOCUSIGN_INTEGRATION_KEY", "").strip(),
        base_url=base_url,
        oauth_host=os.getenv("DOCUSIGN_OAUTH_HOST", "account-d.docusign.com").strip(),
        private_key_path=resolved_key,
        webhook_secret=os.getenv("DOCUSIGN_WEBHOOK_SECRET", "").strip(),
    )