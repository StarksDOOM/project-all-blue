"""
Contracts router - STREAM 6 PHASE 1.0.

Provides endpoints for initializing manual contracts and generating/dispatching
DocuSign M2M contract envelopes.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from database import get_db_session
from models import LegalContract, PropertyListing
from schemas.contracts import (
    ContractInitializeRequest,
    ContractResponse,
    ContractGenerateRequest,
    ContractGenerateResponse,
)
from services.auth import RoleChecker, UserCredentials, UserRole, get_current_user
from services.contract_dispatcher import ContractDispatcher
from services.contract_envelope_builder import ContractEnvelopeBuilder
from services.docusign_jwt_authenticator import DocuSignJWTAuthenticator
from services.contract_service import (
    contract_to_response,
    get_contract,
    initialize_contract,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])

# Protected: only agent and admin may trigger M2M contract generation
generate_contract_checker = RoleChecker(allowed_roles=[UserRole.AGENT, UserRole.ADMIN])


def get_authenticator() -> DocuSignJWTAuthenticator:
    """Dependency resolver for DocuSign M2M Authenticator."""
    return DocuSignJWTAuthenticator()


def get_envelope_builder() -> ContractEnvelopeBuilder:
    """Dependency resolver for DocuSign envelope mapper."""
    return ContractEnvelopeBuilder()


def get_dispatcher(
    authenticator: DocuSignJWTAuthenticator = Depends(get_authenticator),
) -> ContractDispatcher:
    """Dependency resolver for DocuSign execution container."""
    api_client = authenticator.authenticate()
    return ContractDispatcher(api_client)


@router.post(
    "/initialize/{property_id}",
    response_model=ContractResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_draft(
    property_id: str,
    payload: ContractInitializeRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    """Initialize a draft legal agreement for physical signing workflow."""
    contract, property_listing, business_type = initialize_contract(
        session=session,
        property_id=property_id,
        buyer_name=payload.buyer_name,
        buyer_id=payload.buyer_id,
        seller_name=payload.seller_name,
        seller_id=payload.seller_id,
    )
    return contract_to_response(contract, property_listing, business_type)


@router.get("/{contract_id}", response_model=ContractResponse)
def read_contract(
    contract_id: str,
    session: Session = Depends(get_db_session),
) -> dict:
    """Retrieve details of a manual contract draft."""
    contract, property_listing, business_type = get_contract(session, contract_id)
    return contract_to_response(contract, property_listing, business_type)


@router.post(
    "/generate",
    response_model=ContractGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(generate_contract_checker)],
)
def generate_contract(
    payload: ContractGenerateRequest,
    credentials: UserCredentials = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    envelope_builder: ContractEnvelopeBuilder = Depends(get_envelope_builder),
    dispatcher: ContractDispatcher = Depends(get_dispatcher),
) -> ContractGenerateResponse:
    """
    Generate and dispatch a DocuSign contract envelope for a property listing.

    Purpose:
        Perform end-to-end M2M contract generation. Loads the property listing,
        builds the DocuSign EnvelopeDefinition containing listing details and
        signatures, dispatches it to the DocuSign servers, and records a
        LegalContract row in the database tracking the envelope status.

    Lifecycle:
        Called by agents or admins on the storefront via the Property Detail page.
        The created LegalContract persists in the DB and tracks signature lifecycle.

    Thread-safety:
        Fully thread-safe. Uses FastAPI request-scoped session and stateless
        builders/dispatchers.

    Collaborators:
        - PropertyListing (verifies existence and fetches metadata)
        - ContractEnvelopeBuilder (maps data to DocuSign)
        - ContractDispatcher (sends to DocuSign)
        - Session (writes LegalContract)

    Invariants:
        - Raises 404 if the property listing is not found or is inactive.
        - Scopes the contract creation to the authenticated agent's user ID.
        - Persists the returned docusign_envelope_id.
    """
    # Verify the property listing exists and is active (SSRF mitigation)
    property_stmt = select(PropertyListing).where(
        PropertyListing.id == payload.property_id,
        PropertyListing.is_active == True,
    )
    listing = session.exec(property_stmt).first()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active property listing not found",
        )

    # Build the envelope definition
    envelope_definition = envelope_builder.build_envelope(listing, credentials)

    # Dispatch to DocuSign
    envelope_id = dispatcher.dispatch(envelope_definition)

    # Generate a version hash of the metadata
    version_hash_input = f"{listing.id}-{datetime.now(timezone.utc).isoformat()}"
    version_hash = hashlib.sha256(version_hash_input.encode("utf-8")).hexdigest()

    # Persist the LegalContract tracking record
    contract = LegalContract(
        property_id=listing.id,
        user_id=credentials.user_id,
        docusign_envelope_id=envelope_id,
        docusign_status="sent",
        version_hash=version_hash,
        generated_at=datetime.now(timezone.utc),
    )
    session.add(contract)
    session.commit()
    session.refresh(contract)

    logger.info(
        "DocuSign contract generated successfully: listing_id=%s envelope_id=%s contract_id=%s",
        listing.id,
        envelope_id,
        contract.id,
    )

    return ContractGenerateResponse(
        envelope_id=envelope_id,
        status="sent",
        contract_id=contract.id,
    )