"""
Tenant capacity limit enforcement for SavedSearch creation based on RBAC tier.

This module provides the 'TierLimitEvaluator' as a stateless (per-instance) validation
container. It is initialized with a database session solely for performing an isolated
aggregate count query against active SavedSearchAlert records for a given user.

All logic follows strict OOP principles and the mandatory PEP 257 documentation
standards: every module, class, and method has exhaustive docstrings covering
Purpose, Lifecycle, Thread-safety, Collaborators, Invariants, Parameters,
Returns, Raises, and Side Effects.

This is the 12th core single-responsibility abstraction (expanding from 11 post-5.0).
It introduces no new state, no network calls, and no coupling beyond the provided
Session and existing models/enums.

Capacity matrices (enforced only on creation of new active searches):
- client: maximum 3
- agent: maximum 25
- admin: unlimited (sys.maxsize)

Usage: Instantiate with the request-scoped Session, then call assert_can_create_search
before persisting a new SavedSearchAlert. Raises HTTP 400 on breach (after auth/role
checks have already passed).
"""

from __future__ import annotations

import logging
import sys
from typing import Final

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from models import SavedSearchAlert, UserRole

logger = logging.getLogger(__name__)

# Role-based capacity thresholds (immutable constants for this phase).
# These are the single source of truth for enforcement logic.
TIER_LIMITS: Final[dict[UserRole, int]] = {
    UserRole.CLIENT: 3,
    UserRole.AGENT: 25,
    UserRole.ADMIN: sys.maxsize,
}


class TierLimitEvaluator:
    """
    Stateless validation container that enforces per-user, per-role capacity limits
    on active SavedSearchAlert records at creation time.

    Purpose:
        Prevent resource abuse and excessive load on the matching/ingestion
        pipeline by capping the number of active saved searches a user can
        maintain, differentiated by their RBAC tier. The check is performed
        as a lightweight aggregate count query scoped strictly to the
        authenticated user's ID (leveraging Phase 5.0 tenant isolation).

    Lifecycle:
        - Created per protected request (e.g., inside the POST /api/v1/saved-searches
          handler) by passing the already-depended-upon Session.
        - The instance performs a single read-only count query and then
          becomes eligible for garbage collection; no long-lived state or
          caching is maintained.
        - Re-instantiation is cheap and encouraged for isolation.

    Thread-safety:
        Fully thread-safe for concurrent use. The class holds only a reference
        to the provided Session (which is request-scoped and not shared across
        threads in normal FastAPI usage). The count query itself is a read-only
        database operation with no side effects on shared mutable state.

    Collaborators:
        - Session (injected; used only for the count query).
        - SavedSearchAlert (model; queried for user_id + is_active filters).
        - UserRole (enum; used to look up the applicable limit).
        - FastAPI HTTPException (for standardized 400 error on limit breach).
        - The saved_searches router (consumer of assert_can_create_search).

    Invariants:
        - Only counts records where is_active=True (soft-deleted or inactive
          searches do not consume quota).
        - The query is always filtered by the exact user_id from credentials
          (never trusts client-supplied IDs; preserves tenant isolation).
        - Limits are looked up from the immutable TIER_LIMITS dict; unknown
          roles fall back to the most restrictive (client) limit as a safety.
        - No writes, no transactions started by this class, no network I/O
          beyond the provided DB session.
        - Raises only for business-rule violations (over-limit); authentication
          and authorization are assumed to have already succeeded upstream.

    Parameters:
        (See __init__ and assert_can_create_search.)

    Returns:
        (See assert_can_create_search.)

    Raises:
        (See assert_can_create_search.)

    Side Effects:
        - Performs a single SELECT COUNT(*) query against the database
          (read-only; does not modify any rows or session state).
        - May log at INFO/WARNING level on limit breaches (for audit/ops).
        - Raises HTTPException (converted to 400 response by FastAPI); does
          not commit/rollback anything itself.
    """

    def __init__(self, session: Session) -> None:
        """
        Purpose:
            Bind the evaluator to a database session for the duration of one
            limit check. The session is used exclusively for an isolated
            aggregate query.

        Lifecycle:
            Called from route handlers or dependency factories after the
            Session has been obtained via Depends(get_db_session) and after
            the user has been authenticated/authorized.

        Thread-safety:
            Safe (see class docstring).

        Collaborators:
            - Session (stored for the query in assert_can_create_search).

        Invariants:
            - The session reference is held only for the life of the instance.
            - No assumptions are made about the session's transaction state
              (the count is a simple query that works inside or outside an
              explicit transaction).

        Parameters:
            session (Session): An active SQLModel session scoped to the
                current request. Must support select() and scalar() for
                aggregate counts.

        Returns:
            None.

        Raises:
            None at construction time (validation of the session happens
            on first use).

        Side Effects:
            None (pure reference capture).
        """
        self._session = session

    def assert_can_create_search(self, user_id: str, role: UserRole) -> None:
        """
        Purpose:
            Determine whether creating one more active SavedSearchAlert for
            the given user would violate their role-based capacity limit.
            If it would, raise immediately with a clear client-facing error.

        Lifecycle:
            Called from the POST /api/v1/saved-searches handler (after
            RoleChecker but before constructing/persisting the new alert).
            The check must succeed for the create to proceed.

        Thread-safety:
            Safe (see class docstring).

        Collaborators:
            - self._session (for the count query).
            - SavedSearchAlert (for the model and is_active/user_id columns).
            - TIER_LIMITS (for the numeric threshold lookup).
            - HTTPException (for the 400 response on violation).

        Invariants:
            - The count only includes currently active records (is_active=True).
            - The count is strictly per-user (user_id filter from validated
              credentials).
            - Admin role is treated as unlimited via sys.maxsize.
            - Breach always produces HTTP 400 (not 403, because the user is
              already authorized; this is a capacity business rule).

        Parameters:
            user_id (str): The authenticated user's ID (from JWT claims / credentials).
            role (UserRole): The user's RBAC tier (from JWT claims / credentials).

        Returns:
            None (on success; the caller may proceed with creation).

        Raises:
            HTTPException: status_code=400, detail= a message indicating the
                user's current role and the exact limit they have reached
                (e.g., "User has reached the maximum of 3 active searches
                for role client").

        Side Effects:
            - Executes one aggregate COUNT query against the database.
            - On breach: raises exception (FastAPI turns it into a 400 JSON
              response) and logs a warning for operational visibility.
        """
        limit: int = TIER_LIMITS.get(role, TIER_LIMITS[UserRole.CLIENT])

        # Isolated aggregate count query (no joins, no loading full rows).
        count_stmt = (
            select(func.count(SavedSearchAlert.id))
            .where(
                SavedSearchAlert.user_id == user_id,
                SavedSearchAlert.is_active == True,
            )
        )
        current_count: int = self._session.exec(count_stmt).one()

        if current_count >= limit:
            detail = (
                f"User has reached the maximum of {limit} active searches "
                f"for role {role.value}"
            )
            logger.warning(
                "Tier limit breach prevented: user_id=%s role=%s count=%s limit=%s",
                user_id,
                role.value,
                current_count,
                limit,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

        logger.debug(
            "Tier limit check passed: user_id=%s role=%s count=%s limit=%s",
            user_id,
            role.value,
            current_count,
            limit,
        )
