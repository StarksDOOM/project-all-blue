"""Pydantic contracts for Phase 4–5 transaction + legal document API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TransactionCreateRequest(BaseModel):
    property_id: str = Field(..., description="Blu id or portal remote_id")
    buyer_name: str = Field(..., min_length=2)
    buyer_id_doc: str = Field(..., min_length=5)
    seller_name: str = Field(..., min_length=2)
    seller_id_doc: str = Field(..., min_length=5)
    agreed_price: float = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class SignatureExecuteRequest(BaseModel):
    role: Literal["BUYER", "SELLER"]


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
    buyer_signed_at: str | None = None
    seller_signed_at: str | None = None
    signature_telemetry: dict[str, Any] = Field(default_factory=dict)
    is_locked: bool = False


class LegalContractResponse(BaseModel):
    id: str
    transaction_session_id: str | None = None
    file_path: str | None
    storage_url: str | None
    document_body: str
    generated_at: str
    version_hash: str
    document_hash: str | None = None
    pdf_file_path: str | None = None
    has_secure_pdf: bool = False
    docusign_envelope_id: str | None = None
    docusign_status: str | None = None
    has_audit_certificate: bool = False
    audit_certificate_path: str | None = None
    transaction: TransactionResponse | None = None
    property: dict
    signing_url: str | None = None