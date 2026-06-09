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


class CommercialYieldMetrics(BaseModel):
    """Underwriting metrics for commercial assets using Cap Rates."""
    annual_gross_rent: float = Field(..., description="Annual gross rent (USD)")
    effective_gross_income: float = Field(..., description="Effective Gross Income (EGI) after vacancy (USD)")
    annual_noi: float = Field(..., description="Annual Net Operating Income (USD)")
    cap_rate_pct: float = Field(..., description="Capitalisation Rate (%)")


class LtrYieldMetrics(BaseModel):
    """Underwriting metrics for long-term rental residential assets using Cap Rates."""
    annual_gross_rent: float = Field(..., description="Annual gross rent (USD)")
    effective_gross_rent: float = Field(..., description="Effective gross rent after vacancy (USD)")
    operating_expenses: float = Field(..., description="Sum of annual PM fees and maintenance (USD)")
    annual_noi: float = Field(..., description="Annual Net Operating Income (USD)")
    cap_rate_pct: float = Field(..., description="Capitalisation Rate (%)")


class WholesaleDealMetrics(BaseModel):
    """
    Response schema for the wholesale deal analytics endpoint.

    Purpose:
        Carries all computed wholesale metrics for a single property back to the
        caller of ``GET /api/v1/analytics/wholesale/{property_id}``.  The payload
        is intentionally complete — role-based field filtering is performed on the
        frontend, not here, so that both AGENT and ADMIN receive the same wire
        format and the backend remains role-agnostic at the schema layer.

    Collaborators:
        - ``WholesalePricingEngine`` — sole producer of instances of this schema.
        - ``routers.analytics`` — serialises this model as the 200 JSON response.

    Invariants:
        - All monetary values are expressed in USD.
        - ``sector_median_price_per_sqm`` is derived exclusively from
          ``PropertyListing.price_usd`` (always populated) divided by
          ``PropertyListing.square_meters``.
        - ``assignment_fee`` is always >= 5 000.0 (floor enforced by the engine).
        - ``pitch_price == mao + assignment_fee`` (arithmetic identity).
    """

    property_id: str = Field(..., description="BLU ID of the analysed property")
    sector: str = Field(..., description="Neighbourhood / sector of the property")
    sector_median_price_per_sqm: float = Field(
        ..., description="Median price_usd / square_meters across active sector listings (USD/m²)"
    )
    auto_emv: float = Field(
        ..., description="Estimated Market Value: sector_median_price_per_sqm × target.square_meters (USD)"
    )
    mao: float = Field(
        ..., description="Maximum Allowable Offer: auto_emv × 0.80 (USD)"
    )
    assignment_fee: float = Field(
        ..., description="Wholesale assignment fee: max(auto_emv × 0.05, 5 000) (USD)"
    )
    pitch_price: float = Field(
        ..., description="Investor pitch price: mao + assignment_fee (USD)"
    )

    # ------------------------------------------------------------------
    # STR yield metrics (populated only when nightly_rate is supplied)
    # ------------------------------------------------------------------
    str_monthly_gross: float | None = Field(
        None, description="Monthly gross STR income: nightly_rate × 30 × occupancy_pct (USD)"
    )
    str_pm_cost: float | None = Field(
        None, description="Property management cost: str_monthly_gross × 0.20 (USD)"
    )
    str_monthly_net: float | None = Field(
        None, description="Monthly net income: gross − PM − maintenance − maintenance reserve (USD)"
    )
    str_annual_noi: float | None = Field(
        None, description="Annual Net Operating Income: str_monthly_net × 12 (USD)"
    )
    str_cash_on_cash_pct: float | None = Field(
        None, description="Cash-on-Cash return: (str_annual_noi / pitch_price) × 100 (%)"
    )
    str_projection_6mo: float | None = Field(
        None, description="6-month net profit projection: str_monthly_net × 6 (USD)"
    )
    str_projection_1yr: float | None = Field(
        None, description="1-year net profit projection: str_monthly_net × 12 (USD)"
    )
    str_projection_3yr: float | None = Field(
        None, description="3-year net profit projection: str_monthly_net × 36 (USD)"
    )
    recommended_str_assumptions: dict[str, float] = Field(
        ..., description="Recommended initial defaults for nightly_rate, occupancy_pct, and monthly_maintenance"
    )
    commercial_metrics: Optional[CommercialYieldMetrics] = Field(
        None, description="Commercial Cap Rate underwriting metrics (populated only when commercial parameters are supplied)"
    )
    ltr_metrics: Optional[LtrYieldMetrics] = Field(
        None, description="Long-Term Rental (LTR) Cap Rate underwriting metrics (populated only when LTR parameters are supplied)"
    )
