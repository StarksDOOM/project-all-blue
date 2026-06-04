"""
Phase 4 — Transaction and legal document generation routes.

POST /api/v1/transactions — create session
POST /api/v1/transactions/{id}/generate — compile Promesa de Venta
GET  /api/v1/transactions/{id}/contract — fetch latest generated document
"""

from __future__ import annotations

import logging

from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlmodel import Session

from database import get_db_session
from models import SignatureRole
from schemas.docusign import (
    DocusignEnvelopeCreateResponse,
    DocusignSigningUrlRequest,
    DocusignSigningUrlResponse,
)
from schemas.transactions import (
    LegalContractResponse,
    SignatureExecuteRequest,
    TransactionCreateRequest,
    TransactionResponse,
)
from services.docusign_orchestrator import (
    create_docusign_envelope,
    get_embedded_signing_url,
)
from services.signature_service import execute_signature, generate_secure_pdf
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


@router.post(
    "/{transaction_id}/generate-pdf",
    response_model=LegalContractResponse,
    status_code=status.HTTP_200_OK,
)
def generate_contract_pdf(
    transaction_id: str,
    session: Session = Depends(get_db_session),
) -> dict:
    """Compile secure PDF and persist SHA-256 ``document_hash``."""
    transaction, contract, property_listing = generate_secure_pdf(session, transaction_id)
    return contract_to_dict(contract, transaction, property_listing)


@router.post(
    "/{transaction_id}/execute-signature",
    response_model=LegalContractResponse,
    status_code=status.HTTP_200_OK,
)
def execute_contract_signature(
    transaction_id: str,
    payload: SignatureExecuteRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> dict:
    """Capture BUYER or SELLER digital signature with tamper-evidence checks."""
    role = SignatureRole(payload.role)
    transaction, contract, property_listing = execute_signature(
        session,
        transaction_id,
        role,
        request,
    )
    return contract_to_dict(contract, transaction, property_listing)


@router.post(
    "/{transaction_id}/docusign/envelope",
    response_model=DocusignEnvelopeCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction_docusign_envelope(
    transaction_id: str,
    session: Session = Depends(get_db_session),
) -> dict:
    """Upload sealed PDF to DocuSign and start embedded signing envelope."""
    transaction, contract, _ = create_docusign_envelope(session, transaction_id)
    return {
        "envelope_id": contract.docusign_envelope_id or "",
        "docusign_status": contract.docusign_status or "sent",
        "transaction_id": transaction.id,
    }


@router.post(
    "/{transaction_id}/docusign/signing-url",
    response_model=DocusignSigningUrlResponse,
)
def create_transaction_docusign_signing_url(
    transaction_id: str,
    payload: DocusignSigningUrlRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    """One-time embedded signing ceremony URL for BUYER or SELLER."""
    role = SignatureRole(payload.role)
    return get_embedded_signing_url(
        session,
        transaction_id,
        role,
        payload.return_url,
    )


@router.get("/{transaction_id}/contract/pdf")
def download_contract_pdf(
    transaction_id: str,
    session: Session = Depends(get_db_session),
) -> FileResponse:
    """Stream the tamper-sealed PDF binary."""
    _, contract, _ = get_latest_legal_contract(session, transaction_id)
    if not contract.pdf_file_path:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Secure PDF not generated")
    pdf_path = Path(contract.pdf_file_path)
    if not pdf_path.is_file():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Secure PDF file not found on disk")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )