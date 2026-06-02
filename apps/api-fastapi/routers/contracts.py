from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from database import get_db_session
from schemas.contracts import ContractInitializeRequest, ContractResponse
from services.contract_service import (
    contract_to_response,
    get_contract,
    initialize_contract,
)

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])


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
    contract, property_listing, business_type = get_contract(session, contract_id)
    return contract_to_response(contract, property_listing, business_type)