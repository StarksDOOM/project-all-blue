"""Dynamic SQL filter compiler and paginated property list execution."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlmodel import Session, select

from models import PropertyListing
from schemas.property_filters import PropertyFilterParams
from scrapers.utils.normalization import hydrate_listing_bathrooms
from services.str_default_predictor import StrDefaultPredictor

_LIST_COUNT_CACHE: dict[str, tuple[int, float]] = {}
_LIST_COUNT_TTL_SEC = 90.0

_EFFECTIVE_LIST_PRICE = PropertyListing.price_usd


@dataclass(frozen=True)
class PropertyListResult:
    rows: list[PropertyListing]
    total: Optional[int]
    page: int
    limit: int
    pages: Optional[int]
    has_next: bool


def compile_property_filters(filters: PropertyFilterParams) -> list[Any]:
    """
    Build ANDed SQLAlchemy criteria. Always excludes soft-deleted rows.
    No raw SQL — planner-friendly parameterized expressions only.
    """
    criteria: list[Any] = [
        PropertyListing.deleted_at == None,
        or_(
            PropertyListing.listing_type == None,
            PropertyListing.listing_type != "FOR_RENT",
        ),
    ]

    if filters.source_portal:
        criteria.append(
            PropertyListing.source_portal == filters.source_portal.strip().lower()
        )
    if filters.sector:
        criteria.append(PropertyListing.sector == filters.sector)
    if filters.keyword:
        pattern = f"%{filters.keyword}%"
        criteria.append(
            or_(
                PropertyListing.title.ilike(pattern),
                PropertyListing.raw_description.ilike(pattern),
            )
        )
    if filters.price_min is not None:
        criteria.append(_EFFECTIVE_LIST_PRICE >= filters.price_min)
    if filters.price_max is not None:
        criteria.append(_EFFECTIVE_LIST_PRICE <= filters.price_max)
    if filters.bedrooms_min is not None:
        criteria.append(PropertyListing.bedrooms >= filters.bedrooms_min)
    if filters.bathrooms_min is not None:
        criteria.append(PropertyListing.bathrooms >= filters.bathrooms_min)
    if filters.property_type == "venta":
        criteria.append(
            or_(
                PropertyListing.raw_description.ilike("%business_type=venta%"),
                PropertyListing.title.ilike("%venta%"),
            )
        )
    elif filters.property_type == "alquiler":
        criteria.append(
            or_(
                PropertyListing.raw_description.ilike("%business_type=alquiler%"),
                PropertyListing.title.ilike("%alquiler%"),
            )
        )
    if filters.agency:
        criteria.append(PropertyListing.agent_agency.ilike(f"%{filters.agency}%"))

    return criteria


def _resolve_list_total(session: Session, criteria: list[Any], cache_key: str) -> int:
    now = time.monotonic()
    cached = _LIST_COUNT_CACHE.get(cache_key)
    if cached is not None:
        total, expires = cached
        if now < expires:
            return total
    total = session.exec(
        select(func.count()).select_from(PropertyListing).where(*criteria)
    ).one()
    _LIST_COUNT_CACHE[cache_key] = (total, now + _LIST_COUNT_TTL_SEC)
    return total


def is_toxic_listing(listing: PropertyListing) -> bool:
    """Check if both default STR Annual NOI and LTR Annual NOI are negative.

    Excludes deals that are unprofitable under both default underwriting strategies.
    """
    sqm = listing.square_meters
    province = listing.province
    sector = listing.sector

    # Resolve predicted maintenance
    if sqm is None or sqm <= 0:
        maint = 150.0
    else:
        maint = min(round(sqm * 2.50, 2), 400.0)

    # Calculate STR default NOI
    recommended = StrDefaultPredictor.predict_defaults(sqm, province, sector)
    nightly_rate = recommended["nightly_rate"]
    occupancy_pct = recommended["occupancy_pct"]

    str_monthly_gross = nightly_rate * 30 * occupancy_pct
    str_pm_cost = str_monthly_gross * 0.20
    str_monthly_net = str_monthly_gross - str_pm_cost - maint - 150.0
    str_annual_noi = str_monthly_net * 12

    # Calculate LTR default NOI
    default_rent = round((listing.price_usd * 0.08) / 12, 2) if listing.price_usd else 0.0
    if default_rent <= 0:
        default_rent = 1200.0

    ltr_annual_gross = default_rent * 12
    ltr_egr = ltr_annual_gross * 0.95
    ltr_opex = (ltr_annual_gross * 0.10) + (maint * 12)
    ltr_annual_noi = ltr_egr - ltr_opex

    return str_annual_noi < 0 and ltr_annual_noi < 0


def list_properties_paginated(
    session: Session,
    *,
    filters: PropertyFilterParams,
    page: int,
    page_size: int,
    include_total: bool,
) -> PropertyListResult:
    """Single list query path — criteria compiled once, filters toxic deals in-memory, and paginates."""
    criteria = compile_property_filters(filters)

    # Fetch all matching rows from DB to filter toxic listings in Python
    all_rows = session.exec(
        select(PropertyListing)
        .where(*criteria)
        .order_by(PropertyListing.last_modified.desc())
    ).all()

    # Filter toxic deals in Python
    filtered_rows = [row for row in all_rows if not is_toxic_listing(row)]

    offset = (page - 1) * page_size
    page_rows = filtered_rows[offset : offset + page_size]
    has_next = (offset + page_size) < len(filtered_rows)

    total_val = None
    pages_val = None
    if include_total:
        total_val = len(filtered_rows)
        pages_val = (total_val + page_size - 1) // page_size if page_size else 0

    hydrated = [hydrate_listing_bathrooms(row) for row in page_rows]

    return PropertyListResult(
        rows=hydrated,
        total=total_val,
        page=page,
        limit=page_size,
        pages=pages_val,
        has_next=has_next,
    )