"""
Lead capture database entity.

STREAM 6 PHASE 1.7 — Multi-Source Lead Magnet Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from sqlmodel import SQLModel, Field


class LeadCapture(SQLModel, table=True):
    """
    LeadCapture entity mapping to real_estate.lead_captures table.

    Records contact details, traffic sources, and the exact simulation run parameters
    used by users on the public Airbnb ROI calculator lead magnet.
    """

    __tablename__ = "lead_captures"
    __table_args__ = {"schema": "real_estate"}

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        primary_key=True,
        index=True,
    )
    email: str = Field(index=True, nullable=False)
    location_slug: str = Field(nullable=False)
    traffic_source: str = Field(default="organic", nullable=False)

    # Financial Snapshot Fields (exact run parameters)
    simulated_purchase_price: float = Field(nullable=False)
    simulated_nightly_rate: float = Field(nullable=False)
    simulated_occupancy: float = Field(nullable=False)
    simulated_maintenance: float = Field(nullable=False)

    # Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
