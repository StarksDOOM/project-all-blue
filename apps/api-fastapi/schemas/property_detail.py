"""HTTP response schemas for property detail (extends SQLModel row with sync metadata)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PropertyDetailResponse(BaseModel):
    """Full listing payload plus optional portal refresh telemetry for the storefront."""

    model_config = ConfigDict(extra="allow")

    portal_refresh_failed: bool = False
    portal_refresh_message: Optional[str] = None

    @classmethod
    def from_listing(
        cls,
        listing: Any,
        *,
        portal_refresh_failed: bool = False,
        portal_refresh_message: str | None = None,
    ) -> "PropertyDetailResponse":
        data = listing.model_dump() if hasattr(listing, "model_dump") else dict(listing)
        return cls(
            **data,
            portal_refresh_failed=portal_refresh_failed,
            portal_refresh_message=portal_refresh_message,
        )