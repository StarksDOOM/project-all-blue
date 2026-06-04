"""Pydantic contracts for DocuSign embedded signing API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class DocusignEnvelopeCreateResponse(BaseModel):
    envelope_id: str
    docusign_status: str
    transaction_id: str


class DocusignSigningUrlRequest(BaseModel):
    role: Literal["BUYER", "SELLER"]
    return_url: str = Field(..., min_length=10, description="Dashboard URL after ceremony")


class DocusignSigningUrlResponse(BaseModel):
    signing_url: str
    role: str
    envelope_id: str


class SigningConfigResponse(BaseModel):
    provider: Literal["docusign", "internal"]
    docusign_configured: bool