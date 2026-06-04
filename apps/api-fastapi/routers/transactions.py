"""
Phase 4 — Transaction and legal document generation routes.

POST /api/v1/transactions — create session
POST /api/v1/transactions/{id}/generate — compile Promesa de Venta
GET  /api/v1/transactions/{id}/contract — fetch latest generated document
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from database import get_db_session
from schemas.transactions import (
    LegalContractResponse,
    TransactionCreateRequest,
    TransactionResponse,
)
from services.transaction_service import (
    contract_to_dict,
    create_transaction_session,
    generate_legal_contract,
    get_latest_legal_contract,
    transaction_to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreateRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    """Initialize a transaction session mapped to a property listing."""
    from services.contract_service import resolve_property

    property_listing = resolve_property(session, payload.property_id)
    transaction = create_transaction_session(
        session,
        property_id=payload.property_id,
        buyer_name=payload.buyer_name,
        buyer_id_doc=payload.buyer_id_doc,
        seller_name=payload.seller_name,
        seller_id_doc=payload.seller_id_doc,
        agreed_price=payload.agreed_price,
        currency=payload.currency,
    )
    return transaction_to_dict(transaction, property_listing)


@router.post(
    "/{transaction_id}/generate",
    response_model=LegalContractResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_contract(
    transaction_id: str,
    session: Session = Depends(get_db_session),
) -> dict:
    """Execute template interpolation and persist ``LegalContract``."""
    try:
        transaction, contract, property_listing = generate_legal_contract(
            session,
            transaction_id,
        )
        return contract_to_dict(contract, transaction, property_listing)
    except Exception:
        logger.exception("generate_contract failed transaction_id=%s", transaction_id)
        raise


@router.get("/{transaction_id}/contract", response_model=LegalContractResponse)
def fetch_contract(
    transaction_id: str,
    session: Session = Depends(get_db_session),
) -> dict:
    """Return the latest compiled contract for a transaction."""
    transaction, contract, property_listing = get_latest_legal_contract(
        session,
        transaction_id,
    )
    return contract_to_dict(contract, transaction, property_listing)


@router.get(
    "/{transaction_id}/contract/raw",
    response_class=PlainTextResponse,
)
def fetch_contract_raw_markdown(
    transaction_id: str,
    session: Session = Depends(get_db_session),
) -> str:
    """Stream raw markdown (print/download friendly)."""
    _, contract, _ = get_latest_legal_contract(session, transaction_id)
    return contract.document_body