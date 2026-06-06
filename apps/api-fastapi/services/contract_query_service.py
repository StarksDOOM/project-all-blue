"""
Contract Query Service - STREAM 6 PHASE 1.2.

Provides class-based database queries to retrieve structured legal contracts
with associated property metadata, filtered by role-based scopes.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlmodel import Session, select

from models import LegalContract, PropertyListing
from services.auth import UserCredentials, UserRole

logger = logging.getLogger(__name__)


class ContractQueryService:
    """
    Stateless domain service class responsible for fetching contract records.

    Purpose:
        Fetch LegalContract rows with outer-joined PropertyListing metadata,
        applying agent role filters (only matching self-initiated contracts)
        or admin scope (fetching all contracts).

    Lifecycle:
        Stateless and request-scoped. Instantiated by route handlers when
        retrieving ledger records for the transaction dashboard.

    Thread-safety:
        Fully thread-safe as it maintains no mutable instance state. Database
        concurrency guidelines from SQLAlchemy / SQLModel apply.

    Collaborators:
        - Session (database transactions)
        - LegalContract (primary query table)
        - PropertyListing (associated query metadata)
        - UserCredentials (agent/admin credentials provider)

    Invariants:
        - Never returns records initiated by other agents if caller role is UserRole.AGENT.
        - Gracefully handles missing property references (uses outer join).
    """

    def get_ledger_contracts(
        self, session: Session, credentials: UserCredentials
    ) -> list[tuple[LegalContract, Optional[PropertyListing]]]:
        """
        Retrieve a list of contracts joined with property details.

        Purpose:
            Perform the database join query for legal contracts, filtering by the
            authenticated user's ID if they are an AGENT.

        Lifecycle:
            Invoked in the router handler thread per request.

        Thread-safety:
            Safe. Uses the provided database session for scoping.

        Collaborators:
            - Session
            - LegalContract
            - PropertyListing
            - UserCredentials

        Invariants:
            - If credentials.role is UserRole.AGENT, filters by user_id == credentials.user_id.
            - If credentials.role is UserRole.ADMIN, returns all records.

        Parameters:
            session (Session): The active database session.
            credentials (UserCredentials): Credentials of the authenticated user.

        Returns:
            list[tuple[LegalContract, Optional[PropertyListing]]]: List of matched tuples.

        Raises:
            None.

        Side Effects:
            Reads from database.
        """
        # Outer join LegalContract with PropertyListing on property_id
        statement = (
            select(LegalContract, PropertyListing)
            .join(PropertyListing, LegalContract.property_id == PropertyListing.id, isouter=True)
            .order_by(LegalContract.generated_at.desc())
        )

        if credentials.role == UserRole.AGENT:
            logger.info("Scoping contract ledger fetch to agent: %s", credentials.user_id)
            statement = statement.where(LegalContract.user_id == credentials.user_id)
        else:
            logger.info("Admin contract ledger fetch; returning all records.")

        results = session.exec(statement).all()
        # SQLAlchemy select returns a list of Row objects or tuples (LegalContract, PropertyListing)
        return results
