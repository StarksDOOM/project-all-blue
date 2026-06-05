"""Pydantic schemas for Saved Search Alerts (STREAM 5 PHASE 3.0)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.property_filters import PropertyFilterParams


class SavedSearchCreate(BaseModel):
    """Client payload to persist a filter matrix as an alert.
    user_id is optional and ignored; the server derives the authenticated user from the JWT token (Phase 5.0+).
    """

    user_id: Optional[str] = Field(default=None, description="Ignored; derived from auth token")
    title: str = Field(min_length=1, max_length=80)
    filters: PropertyFilterParams = Field(
        description="Subset of PropertyFilterParams; page/limit omitted by client"
    )


class SavedSearchUpdate(BaseModel):
    """Partial update (primarily mute/unmute)."""

    is_active: Optional[bool] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=80)


class SavedSearchAlertOut(BaseModel):
    """Response shape for list/create."""

    id: str
    user_id: str
    title: str
    filters_json: dict[str, Any]
    is_active: bool
    created_at: datetime
    last_matched_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SavedSearchListResponse(BaseModel):
    data: list[SavedSearchAlertOut]
