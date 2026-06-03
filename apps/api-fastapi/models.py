"""
SQLModel entities for All Blue Core (real_estate schema).

Ingestion-related tables:
  - PropertyListing — normalized portal inventory (upsert key: source_portal + remote_id)
  - IngestionSyncJob — per-crawl lifecycle and metrics
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, String, BigInteger
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


class SyncJobStatus(str, Enum):
    """Ingestion job lifecycle tracked by IngestionOrchestrator."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

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
    """
    Normalized listing row produced by portal drivers (RemaxRdDriver, etc.).

    Persisted exclusively via IngestionOrchestrator bulk upsert.
    """

    __tablename__ = "properties"
    __table_args__ = {"schema": "real_estate"}

    remote_id: str = Field(index=True)  # Portal-native id; upsert conflict key (with source_portal)
    source_portal: str = Field(index=True)  # Driver token: remaxrd, realtor, ...
    url: str  # Canonical property URL on portal site
    title: str  # Display title for storefront / contracts
    price_usd: float  # Required USD amount (derived when portal lists DOP)
    price_dop: Optional[float] = Field(default=None, nullable=True)  # Optional DOP mirror
    list_price: Optional[float] = Field(
        default=None, nullable=True
    )  # Exact portal list amount in listing_currency
    image_urls: Optional[List[str]] = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )  # RE/MAX CDN URLs from detail scrape
    province: str  # City / province label
    sector: str = Field(index=True)  # Neighborhood — filtered in GET /properties
    bedrooms: int
    bathrooms: float  # Full + 0.5 * half baths (see scrapers.utils.normalization)
    square_meters: float
    sqm_land: Optional[float] = Field(default=None, nullable=True)  # Land area when portal provides it
    listing_currency: str = Field(default="USD")  # Portal list currency (USD, DOP)
    agent_name: Optional[str] = Field(default=None, nullable=True)
    agent_phone: Optional[str] = Field(default=None, nullable=True)
    agent_email: Optional[str] = Field(default=None, nullable=True)
    agent_whatsapp: Optional[str] = Field(default=None, nullable=True)
    agent_agency: Optional[str] = Field(default=None, nullable=True)
    raw_description: str  # Compact summary for search and contract templates
    is_active: bool = Field(default=True)  # RE/MAX: status == disponible


class IngestionSyncJob(AllBlueBaseModel, table=True):
    """One row per crawl execution; metrics filled when status reaches COMPLETED."""

    __tablename__ = "ingestion_sync_jobs"
    __table_args__ = {"schema": "real_estate"}

    source_portal: str = Field(index=True)  # Portal that was crawled
    status: SyncJobStatus = Field(default=SyncJobStatus.PENDING, index=True)
    fetched: int = Field(default=0)  # Rows returned by driver.run_sync()
    inserted: int = Field(default=0)  # New (source_portal, remote_id) rows in upsert
    updated: int = Field(default=0)  # Existing rows refreshed on conflict
    error_message: Optional[str] = Field(default=None, nullable=True)  # Set when status=FAILED


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