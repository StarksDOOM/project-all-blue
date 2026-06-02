from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Column, String, BigInteger
from database import generate_blu_id, get_current_timestamp_ms

class ContractType(str, Enum):
    RENTAL = "RENTAL"
    PURCHASE_RESERVATION = "PURCHASE_RESERVATION"
    MANAGEMENT = "MANAGEMENT"

class ContractStatus(str, Enum):
    DRAFT = "DRAFT"
    SIGNED = "SIGNED"
    ESCROW_HOLD = "ESCROW_HOLD"
    COMPLETED = "COMPLETED"

class AllBlueBaseModel(SQLModel):
    """Core synchronization and multi-tenant primitives for downstream pipelines."""
    id: str = Field(
        default_factory=generate_blu_id,
        primary_key=True,
        index=True
    )
    tenant_id: str = Field(default="tenant_all_blue", index=True)
    server_version: int = Field(default=1)
    
    # Use sa_type instead of sa_column to keep it safe for abstract inheritance
    last_modified: int = Field(
        default_factory=get_current_timestamp_ms,
        sa_type=BigInteger,
        index=True
    )
    
    # Pure SQLModel native field safely cloning datetime across tables
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    
class PropertyListing(AllBlueBaseModel, table=True):
    __tablename__ = "properties"
    __table_args__ = {"schema": "real_estate"}

    remote_id: str = Field(index=True)
    source_portal: str = Field(index=True)  # e.g., 'remaxrd', 'realtor'
    url: str
    title: str
    price_usd: float
    price_dop: Optional[float] = Field(default=None, nullable=True)
    province: str
    sector: str = Field(index=True)
    bedrooms: int
    bathrooms: float
    square_meters: float
    raw_description: str
    is_active: bool = Field(default=True)

class SRLContract(AllBlueBaseModel, table=True):
    __tablename__ = "srl_contracts"
    __table_args__ = {"schema": "real_estate"}

    contract_number: str = Field(index=True, unique=True)
    property_id: str = Field(foreign_key="real_estate.properties.id")
    property_remote_id: str = Field(index=True)
    client_name: str
    client_rnc_or_cedula: str
    buyer_name: str
    buyer_id: str
    seller_name: str
    seller_id: str
    contract_type: ContractType
    total_value_usd: float
    earnest_deposit_usd: float
    execution_date: datetime
    status: ContractStatus = Field(default=ContractStatus.DRAFT)
    document_body: str = Field(default="")