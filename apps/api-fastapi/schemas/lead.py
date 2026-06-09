"""Pydantic validation schemas for Lead Capture.

STREAM 6 PHASE 1.7 — Multi-Source Lead Magnet Engine.
"""

from __future__ import annotations

import re
from pydantic import BaseModel, Field, field_validator


class LeadCaptureCreate(BaseModel):
    """Payload to capture a new investor lead with simulated parameters."""

    email: str = Field(
        ...,
        description="Investor email address",
        examples=["investor@example.com"],
    )
    location_slug: str = Field(
        ...,
        description="Location slug of the dynamic lead magnet route",
        examples=["punta-cana"],
    )
    traffic_source: str = Field(
        default="organic",
        description="Traffic attribution parameter (e.g. fb-ad, newsletter)",
        examples=["fb-ad"],
    )

    # Simulated run parameters
    simulated_purchase_price: float = Field(
        ...,
        ge=0,
        description="Interactive purchase price slider state",
    )
    simulated_nightly_rate: float = Field(
        ...,
        ge=0,
        description="Interactive nightly rate slider state",
    )
    simulated_occupancy: float = Field(
        ...,
        ge=0,
        le=1.0,
        description="Interactive occupancy slider state (0.0 - 1.0)",
    )
    simulated_maintenance: float = Field(
        ...,
        ge=0,
        description="Interactive monthly maintenance slider state",
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        """Enforce standard email format validation."""
        email_clean = value.strip().lower()
        # Simple RFC-like regex pattern for email format verification
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(pattern, email_clean):
            raise ValueError("Invalid email format")
        return email_clean


class LeadCaptureOut(BaseModel):
    """Response returned upon successful lead capture registration."""

    id: str = Field(..., description="UUID of the captured lead")


class LeadCaptureRow(BaseModel):
    """Full serialized representation of a LeadCapture record for the CRM feed.

    Used by GET /api/v1/leads to expose individual lead rows to the
    internal sales team dashboard.
    """

    id: str
    email: str
    location_slug: str
    traffic_source: str
    simulated_purchase_price: float
    simulated_nightly_rate: float
    simulated_occupancy: float
    simulated_maintenance: float
    created_at: str = Field(description="ISO-8601 UTC timestamp")

    model_config = {"from_attributes": True}


class LeadCaptureListResponse(BaseModel):
    """Paginated list response for the internal CRM leads feed.

    Wraps a list of LeadCaptureRow records with pagination metadata.
    """

    data: list[LeadCaptureRow]
    total: int
    skip: int
    limit: int
