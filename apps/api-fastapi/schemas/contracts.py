from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from models import ContractStatus, ContractType


class ContractInitializeRequest(BaseModel):
    buyer_name: str = Field(..., min_length=1, max_length=255)
    buyer_id: str = Field(..., min_length=1, max_length=64)
    seller_name: str = Field(..., min_length=1, max_length=255)
    seller_id: str = Field(..., min_length=1, max_length=64)


class ContractResponse(BaseModel):
    id: str
    contract_number: str
    property_id: str
    property_remote_id: str
    property_title: str
    business_type: str
    contract_type: ContractType
    status: ContractStatus
    client_name: str
    client_rnc_or_cedula: str
    buyer_name: str
    buyer_id: str
    seller_name: str
    seller_id: str
    total_value_usd: float
    earnest_deposit_usd: float
    execution_date: datetime
    document_body: str
    last_modified: int
    server_version: int


class ContractGenerateRequest(BaseModel):
    """
    Client request payload to trigger DocuSign contract envelope generation.
    """
    property_id: str = Field(..., min_length=1, description="Unique BLU ID of the listing property")


class ContractGenerateResponse(BaseModel):
    """
    API response containing the created DocuSign envelope metadata.
    """
    envelope_id: str = Field(..., description="The GUID tracking the dispatched DocuSign envelope")
    status: str = Field(..., description="The status of the envelope dispatch (e.g. 'sent')")
    contract_id: str = Field(..., description="The ID of the generated LegalContract database record")


class DashboardContractProperty(BaseModel):
    """
    Flat property representation for transaction dashboard.
    """
    title: str = Field(..., description="The title of the property")
    price_usd: float = Field(..., description="The list price of the property in USD")


class DashboardContractResponse(BaseModel):
    """
    Response schema for contract list items in the transaction ledger dashboard.
    """
    id: str = Field(..., description="The unique ID of the contract")
    created_at: datetime = Field(..., description="Creation date and time of the contract")
    status: Optional[str] = Field(None, description="The signature status from DocuSign (e.g. 'sent', 'executed')")
    property: Optional[DashboardContractProperty] = Field(None, description="Associated property details")