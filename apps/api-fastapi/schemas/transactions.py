"""Pydantic contracts for Phase 4 transaction + legal document API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TransactionCreateRequest(BaseModel):
    property_id: str = Field(..., description="Blu id or portal remote_id")
    buyer_name: str = Field(..., min_length=2)
    buyer_id_doc: str = Field(..., min_length=5)
    seller_name: str = Field(..., min_length=2)
    seller_id_doc: str = Field(..., min_length=5)
    agreed_price: float = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class TransactionResponse(BaseModel):
    id: str
    property_id: str
    property_remote_id: str | None = None
    property_title: str | None = None
    buyer_name: str
    buyer_id_doc: str
    seller_name: str
    seller_id_doc: str
    agreed_price: float
    currency: str
    status: str
    created_at: str
    updated_at: str


class LegalContractResponse(BaseModel):
    id: str
    transaction_session_id: str
    file_path: str | None
    storage_url: str | None
    document_body: str
    generated_at: str
    version_hash: str
    transaction: TransactionResponse
    property: dict