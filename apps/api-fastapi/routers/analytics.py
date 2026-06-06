"""
Analytics router — wholesale deal pricing endpoints.

Module Purpose:
    Exposes ``GET /api/v1/analytics/wholesale/{property_id}`` for computing
    automated wholesale deal metrics using ``WholesalePricingEngine``.

    All routes in this module are protected by ``RoleChecker`` and require the
    caller to hold the ``AGENT`` or ``ADMIN`` role.  ``CLIENT`` tokens receive
    a ``403 Forbidden`` response without reaching the engine.

Thread Safety:
    The ``WholesalePricingEngine`` singleton is stateless and safe for concurrent
    use across all request handlers in this module.

Collaborators:
    - ``services.wholesale_pricing_engine.WholesalePricingEngine`` — engine.
    - ``services.auth.RoleChecker`` — RBAC enforcement dependency.
    - ``database.get_session`` — SQLModel session factory.
    - ``schemas.contracts.WholesaleDealMetrics`` — response model.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from database import get_db_session
from schemas.contracts import WholesaleDealMetrics
from services.auth import RoleChecker, UserCredentials, UserRole
from services.wholesale_pricing_engine import WholesalePricingEngine

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# ---------------------------------------------------------------------------
# RBAC guard — shared across all analytics routes
# ---------------------------------------------------------------------------
_analytics_checker = RoleChecker(allowed_roles=[UserRole.AGENT, UserRole.ADMIN])

# ---------------------------------------------------------------------------
# Engine singleton — stateless, safe to share
# ---------------------------------------------------------------------------
_engine = WholesalePricingEngine()


@router.get(
    "/wholesale/{property_id}",
    response_model=WholesaleDealMetrics,
    summary="Compute wholesale deal metrics for a property",
    description=(
        "Returns ARV, MAO, assignment fee, and pitch price derived from live "
        "sector data and fixed heuristics.  Requires AGENT or ADMIN role."
    ),
)
async def get_wholesale_analytics(
    property_id: str,
    session: Session = Depends(get_db_session),
    _current_user: UserCredentials = Depends(_analytics_checker),
) -> WholesaleDealMetrics:
    """
    Retrieve wholesale deal metrics for a single active property listing.

    Purpose:
        Delegates computation to ``WholesalePricingEngine.calculate_deal_metrics``
        and returns the fully serialised ``WholesaleDealMetrics`` response.

    Parameters:
        property_id : str
            BLU database ID of the target ``PropertyListing`` (path parameter).
        session : Session
            Request-scoped SQLModel session injected by ``get_session``.
        _current_user : UserCredentials
            Validated JWT credentials — used only for RBAC enforcement via
            ``_analytics_checker``; not consumed by the route body.

    Returns:
        WholesaleDealMetrics
            JSON payload containing all computed wholesale metrics.

    Raises:
        HTTPException(403)
            Raised by ``_analytics_checker`` when the caller holds the CLIENT role
            or presents an invalid / expired token.
        HTTPException(404)
            Raised by the engine when ``property_id`` does not exist or is inactive.
        HTTPException(422)
            Raised by the engine when the property's sector has no active peers.

    Side Effects:
        None.  All database operations are read-only.
    """
    return _engine.calculate_deal_metrics(property_id=property_id, session=session)
