"""
Saved Search Alerts router — STREAM 5 PHASE 3.0.

POST /api/v1/saved-searches
GET  /api/v1/saved-searches?user_id=...
PATCH /api/v1/saved-searches/{alert_id}
DELETE /api/v1/saved-searches/{alert_id}

User_id is client-supplied (demo / placeholder). Full ownership checks and
JWT binding are out of scope until auth lands (see engineering-directives A07).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from database import get_db_session
from models import SavedSearchAlert, SavedSearchMatch
from schemas.property_filters import PropertyFilterParams
from schemas.saved_searches import (
    SavedSearchAlertOut,
    SavedSearchCreate,
    SavedSearchListResponse,
    SavedSearchUpdate,
)

router = APIRouter(prefix="/api/v1/saved-searches", tags=["saved-searches"])


@router.post(
    "",
    response_model=SavedSearchAlertOut,
    status_code=status.HTTP_201_CREATED,
)
def create_saved_search(
    payload: SavedSearchCreate,
    session: Session = Depends(get_db_session),
) -> SavedSearchAlertOut:
    """
    Persist a bookmarkable filter matrix as an active alert.

    - Re-validates `filters` through PropertyFilterParams (sanitization + range checks).
    - Stores the canonical dict in filters_json (page omitted).
    - Returns the persisted row (filters_json echo).
    """
    # Force re-validation + normalization (strips, price order, etc.)
    try:
        validated = PropertyFilterParams.model_validate(payload.filters.model_dump())
    except Exception as exc:  # pragma: no cover - pydantic already did
        raise HTTPException(status_code=400, detail=f"Invalid filters: {exc}") from exc

    # Drop page if client sent it; keep everything else
    filters_dict = validated.model_dump(exclude_none=True)
    filters_dict.pop("page", None)

    alert = SavedSearchAlert(
        user_id=payload.user_id,
        title=payload.title.strip(),
        filters_json=filters_dict,
        is_active=True,
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)

    return SavedSearchAlertOut.model_validate(alert)


@router.get("", response_model=SavedSearchListResponse)
def list_saved_searches(
    user_id: str = Query(..., min_length=1),
    session: Session = Depends(get_db_session),
) -> SavedSearchListResponse:
    """Return all alerts (active + inactive) for the supplied user_id, newest first."""
    stmt = (
        select(SavedSearchAlert)
        .where(SavedSearchAlert.user_id == user_id)
        .order_by(SavedSearchAlert.created_at.desc())  # type: ignore[attr-defined]
    )
    rows = session.exec(stmt).all()
    return SavedSearchListResponse(
        data=[SavedSearchAlertOut.model_validate(r) for r in rows]
    )


@router.patch("/{alert_id}", response_model=SavedSearchAlertOut)
def update_saved_search(
    alert_id: str,
    payload: SavedSearchUpdate,
    session: Session = Depends(get_db_session),
) -> SavedSearchAlertOut:
    """Update mutable fields (title, is_active for mute/unmute)."""
    alert = session.get(SavedSearchAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Saved search not found")

    if payload.title is not None:
        alert.title = payload.title.strip()
    if payload.is_active is not None:
        alert.is_active = payload.is_active

    session.add(alert)
    session.commit()
    session.refresh(alert)
    return SavedSearchAlertOut.model_validate(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(
    alert_id: str,
    session: Session = Depends(get_db_session),
) -> None:
    """Hard delete an alert (and leave historical matches for audit)."""
    alert = session.get(SavedSearchAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Saved search not found")
    session.delete(alert)
    session.commit()


@router.get("/{alert_id}/matches")
def list_matches_for_alert(
    alert_id: str,
    user_id: str = Query(..., min_length=1),
    session: Session = Depends(get_db_session),
) -> dict:
    """
    Return matches for a saved search alert, including Phase 4.0 delivery status.
    Used by the dashboard match history ledger.
    """
    alert = session.get(SavedSearchAlert, alert_id)
    if not alert or alert.user_id != user_id:
        raise HTTPException(status_code=404, detail="Saved search not found")

    stmt = (
        select(SavedSearchMatch)
        .where(SavedSearchMatch.saved_search_alert_id == alert_id)
        .order_by(SavedSearchMatch.matched_at.desc())
    )
    matches = session.exec(stmt).all()

    # Lightweight serialization (include delivery fields for UI badges)
    return {
        "alert_id": alert_id,
        "matches": [
            {
                "id": m.id,
                "property_id": m.property_id,
                "matched_at": m.matched_at.isoformat(),
                "match_details": m.match_details,
                "delivery_status": m.delivery_status.value,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                "retry_count": m.retry_count,
            }
            for m in matches
        ],
    }
