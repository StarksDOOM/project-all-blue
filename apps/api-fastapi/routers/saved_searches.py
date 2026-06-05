"""
Saved Search Alerts router — STREAM 5 PHASE 5.0 (RBAC + tenant isolation) + 5.1 (tier limits).

All routes now require valid Supabase JWT (local verification only).
Queries and mutations are strictly scoped to credentials.user_id for tenant isolation.
RoleChecker used for protected operations (e.g. mutations).
Phase 5.1: POST create now additionally runs TierLimitEvaluator (after auth, before persist).

See rbac-auth-infrastructure.spec.md and tier-limits-admin-overrides.spec.md for full contracts.
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
from services.auth import RoleChecker, UserCredentials, UserRole, get_current_user
from services.tier_limit_evaluator import TierLimitEvaluator

router = APIRouter(prefix="/api/v1/saved-searches", tags=["saved-searches"])


# Phase 5.0: protected; any authenticated user can create their own alert
create_alert_checker = RoleChecker(
    allowed_roles=[UserRole.CLIENT, UserRole.AGENT, UserRole.ADMIN]
)


@router.post(
    "",
    response_model=SavedSearchAlertOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(create_alert_checker)],
)
def create_saved_search(
    payload: SavedSearchCreate,
    credentials: UserCredentials = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> SavedSearchAlertOut:
    """
    Persist a bookmarkable filter matrix as an active alert.

    Phase 5.1: after RBAC (create_alert_checker + get_current_user) and filter validation,
    but before any DB write, TierLimitEvaluator.assert_can_create_search is invoked.
    This enforces role-based capacity (client=3, agent=25, admin=unlimited) via an
    isolated COUNT query on active alerts for the authenticated user_id only.

    - Re-validates `filters` through PropertyFilterParams (sanitization + range checks).
    - Stores the canonical dict in filters_json (page omitted).
    - user_id is taken from validated JWT claims (tenant isolation); payload.user_id ignored.
    - Returns the persisted row (filters_json echo).
    - Raises HTTP 400 (via evaluator) if the user's role limit would be exceeded.
    """
    # Force re-validation + normalization (strips, price order, etc.)
    try:
        validated = PropertyFilterParams.model_validate(payload.filters.model_dump())
    except Exception as exc:  # pragma: no cover - pydantic already did
        raise HTTPException(status_code=400, detail=f"Invalid filters: {exc}") from exc

    # Drop page if client sent it; keep everything else
    filters_dict = validated.model_dump(exclude_none=True)
    filters_dict.pop("page", None)

    # Phase 5.1: enforce per-role tier limit (stateless evaluator, session-scoped query)
    evaluator = TierLimitEvaluator(session)
    evaluator.assert_can_create_search(credentials.user_id, credentials.role)

    alert = SavedSearchAlert(
        user_id=credentials.user_id,  # Phase 5.0: from validated token, not client payload
        title=payload.title.strip(),
        filters_json=filters_dict,
        is_active=True,
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)

    return SavedSearchAlertOut.model_validate(alert)


# Phase 5.0: list own alerts only (any authenticated role)
list_alerts_checker = RoleChecker(
    allowed_roles=[UserRole.CLIENT, UserRole.AGENT, UserRole.ADMIN]
)


@router.get("", response_model=SavedSearchListResponse, dependencies=[Depends(list_alerts_checker)])
def list_saved_searches(
    credentials: UserCredentials = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> SavedSearchListResponse:
    """Return all alerts (active + inactive) owned by the authenticated user, newest first."""
    stmt = (
        select(SavedSearchAlert)
        .where(SavedSearchAlert.user_id == credentials.user_id)  # Phase 5.0: strict tenant filter
        .order_by(SavedSearchAlert.created_at.desc())  # type: ignore[attr-defined]
    )
    rows = session.exec(stmt).all()
    return SavedSearchListResponse(
        data=[SavedSearchAlertOut.model_validate(r) for r in rows]
    )


update_delete_checker = RoleChecker(
    allowed_roles=[UserRole.CLIENT, UserRole.AGENT, UserRole.ADMIN]
)


@router.patch("/{alert_id}", response_model=SavedSearchAlertOut, dependencies=[Depends(update_delete_checker)])
def update_saved_search(
    alert_id: str,
    payload: SavedSearchUpdate,
    credentials: UserCredentials = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> SavedSearchAlertOut:
    """Update mutable fields (title, is_active for mute/unmute). Tenant scoped."""
    # Phase 5.0: fetch and scope check
    stmt = select(SavedSearchAlert).where(
        SavedSearchAlert.id == alert_id,
        SavedSearchAlert.user_id == credentials.user_id,  # strict tenant filter
    )
    alert = session.exec(stmt).first()
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


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(update_delete_checker)])
def delete_saved_search(
    alert_id: str,
    credentials: UserCredentials = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> None:
    """Hard delete an alert (and leave historical matches for audit). Tenant scoped."""
    stmt = select(SavedSearchAlert).where(
        SavedSearchAlert.id == alert_id,
        SavedSearchAlert.user_id == credentials.user_id,
    )
    alert = session.exec(stmt).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Saved search not found")
    session.delete(alert)
    session.commit()


matches_checker = RoleChecker(
    allowed_roles=[UserRole.CLIENT, UserRole.AGENT, UserRole.ADMIN]
)


@router.get("/{alert_id}/matches", dependencies=[Depends(matches_checker)])
def list_matches_for_alert(
    alert_id: str,
    credentials: UserCredentials = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> dict:
    """
    Return matches for a saved search alert, including delivery status.
    Phase 5.0: strictly scoped to the authenticated user's alerts (tenant isolation).
    Used by the dashboard match history ledger.
    """
    # Verify ownership via scoped query (no leak of existence)
    alert_stmt = select(SavedSearchAlert).where(
        SavedSearchAlert.id == alert_id,
        SavedSearchAlert.user_id == credentials.user_id,
    )
    alert = session.exec(alert_stmt).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Saved search not found")

    stmt = (
        select(SavedSearchMatch)
        .where(
            SavedSearchMatch.saved_search_alert_id == alert_id,
            # Additional direct filter for defense in depth (user_id on match)
            SavedSearchMatch.user_id == credentials.user_id,
        )
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
