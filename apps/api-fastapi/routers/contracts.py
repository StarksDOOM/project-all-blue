"""
Contracts router - STREAM 6 PHASE 1.0.

Provides endpoints for initializing manual contracts and generating/dispatching
DocuSign M2M contract envelopes.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, BackgroundTasks
from sqlmodel import Session, select

from database import get_db_session
from models import LegalContract, PropertyListing
from schemas.contracts import (
    ContractInitializeRequest,
    ContractResponse,
    ContractGenerateRequest,
    ContractGenerateResponse,
    DashboardContractProperty,
    DashboardContractResponse,
)
from services.auth import RoleChecker, UserCredentials, UserRole, get_current_user
from services.docuseal_dispatcher import DocuSealDispatcher
from services.docuseal_webhook_validator import DocuSealWebhookValidator
from services.contract_service import (
    contract_to_response,
    get_contract,
    initialize_contract,
)
from services.contract_lifecycle_manager import ContractLifecycleManager
from services.notification_dispatcher import NotificationDispatcher
from services.contract_query_service import ContractQueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])

# Protected: only agent and admin may trigger M2M contract generation
generate_contract_checker = RoleChecker(allowed_roles=[UserRole.AGENT, UserRole.ADMIN])


def get_docuseal_dispatcher() -> DocuSealDispatcher:
    """Dependency resolver for DocuSeal execution container."""
    return DocuSealDispatcher()


def get_docuseal_webhook_validator() -> DocuSealWebhookValidator:
    """Dependency resolver for DocuSeal Webhook validator."""
    return DocuSealWebhookValidator()


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
    dispatcher: DocuSealDispatcher = Depends(get_docuseal_dispatcher),
) -> ContractGenerateResponse:
    """
    Generate and dispatch a DocuSeal contract submission for a property listing.

    Purpose:
        Perform end-to-end contract generation. Loads the property listing,
        submits the e-sign request to DocuSeal using templates, and records a
        LegalContract row in the database tracking the status.

    Lifecycle:
        Called by agents or admins on the storefront via the Property Detail page.
        The created LegalContract persists in the DB and tracks signature lifecycle.

    Thread-safety:
        Fully thread-safe. Uses FastAPI request-scoped session and stateless
        dispatchers.

    Collaborators:
        - PropertyListing (verifies existence and fetches metadata)
        - DocuSealDispatcher (sends request to DocuSeal)
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

    # Dispatch to DocuSeal
    envelope_id = dispatcher.dispatch(
        property_id=listing.id,
        buyer_email="cliente.comprador@example.com",
        agent_email=credentials.email,
    )

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
        "DocuSeal contract generated successfully: listing_id=%s envelope_id=%s contract_id=%s",
        listing.id,
        envelope_id,
        contract.id,
    )

    return ContractGenerateResponse(
        envelope_id=envelope_id,
        status="sent",
        contract_id=contract.id,
    )


def get_lifecycle_manager() -> ContractLifecycleManager:
    """Dependency resolver for standalone contract lifecycle processor."""
    return ContractLifecycleManager()


def get_notification_dispatcher() -> NotificationDispatcher:
    """Dependency resolver for outbound email notifications dispatcher."""
    return NotificationDispatcher()


@router.post("/webhooks/esign", status_code=status.HTTP_200_OK)
async def docuseal_webhook_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    x_docuseal_signature: str | None = Header(default=None, alias="X-Docuseal-Signature"),
    session: Session = Depends(get_db_session),
    validator: DocuSealWebhookValidator = Depends(get_docuseal_webhook_validator),
    lifecycle_manager: ContractLifecycleManager = Depends(get_lifecycle_manager),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
) -> dict[str, str]:
    """
    DocuSeal Connect Webhook callback for standalone property contracts.

    Purpose:
        Ingest completed/declined signing envelope updates from DocuSeal.
        Validates HMAC signature and schedules database updates and notification dispatch.

    Lifecycle:
        Invoked as a webhook callback by DocuSeal when signing completes/declines.

    Thread-safety:
        Fully thread-safe.

    Collaborators:
        - DocuSealWebhookValidator (cryptographic validator)
        - ContractLifecycleManager (business lifecycle processor)
        - Session (database persistence)
    """
    raw_body = await request.body()

    # 1. Cryptographically verify payload signature
    validator.verify(raw_body, x_docuseal_signature)

    # 2. Parse payload JSON
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to parse DocuSeal webhook raw body JSON: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload",
        )

    # 3. Process contract lifecycle updates
    lifecycle_manager.process_webhook_event(
        session=session,
        background_tasks=background_tasks,
        event_payload=payload,
        dispatcher=dispatcher,
    )

    return {"status": "success"}


def get_query_service() -> ContractQueryService:
    """Dependency resolver for ContractQueryService."""
    return ContractQueryService()


# Protected: only agent and admin may retrieve transaction ledger contracts list
ledger_checker = RoleChecker(allowed_roles=[UserRole.AGENT, UserRole.ADMIN])


@router.get(
    "",
    response_model=list[DashboardContractResponse],
    dependencies=[Depends(ledger_checker)],
)
def list_contracts(
    credentials: UserCredentials = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    query_service: ContractQueryService = Depends(get_query_service),
) -> list[DashboardContractResponse]:
    """
    Retrieve transaction ledger contracts list for Agent / Admin dashboard.

    Purpose:
        Perform dynamic role-scoped database query to fetch generated DocuSign
        contracts and serialize them with basic associated property details
        to avoid lazy loading exceptions.

    Lifecycle:
        Called by storefront client when viewing the transaction dashboard.

    Thread-safety:
        Fully thread-safe. Uses request-scoped FastAPI sessions.

    Collaborators:
        - ContractQueryService (fetches raw database tuples)
        - Session (database transactions)
        - UserCredentials (agent/admin claims)

    Invariants:
        - Denies access to clients (returns 403 via RoleChecker).
        - Scopes contracts to current user if role is AGENT.
    """
    raw_results = query_service.get_ledger_contracts(session, credentials)

    response_items = []
    for contract, listing in raw_results:
        prop_meta = None
        if listing:
            prop_meta = DashboardContractProperty(
                title=listing.title,
                price_usd=listing.price_usd,
            )
        response_items.append(
            DashboardContractResponse(
                id=contract.id,
                created_at=contract.generated_at,
                status=contract.docusign_status,
                property=prop_meta,
            )
        )
    return response_items