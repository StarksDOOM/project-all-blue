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


def list_properties_paginated(
    session: Session,
    *,
    filters: PropertyFilterParams,
    page: int,
    page_size: int,
    include_total: bool,
) -> PropertyListResult:
    """Single list query path — criteria compiled once, reused for count + page."""
    criteria = compile_property_filters(filters)
    cache_key = filters.cache_fingerprint()

    total: Optional[int] = None
    pages: Optional[int] = None
    if include_total:
        total = _resolve_list_total(session, criteria, cache_key)
        pages = (total + page_size - 1) // page_size if page_size else 0

    offset = (page - 1) * page_size
    fetch_limit = page_size + (0 if include_total else 1)
    rows = session.exec(
        select(PropertyListing)
        .where(*criteria)
        .order_by(PropertyListing.last_modified.desc())
        .offset(offset)
        .limit(fetch_limit)
    ).all()

    has_next = (
        len(rows) > page_size
        if not include_total
        else pages is not None and page < pages
    )
    page_rows = rows[:page_size]
    hydrated = [hydrate_listing_bathrooms(row) for row in page_rows]

    return PropertyListResult(
        rows=hydrated,
        total=total,
        page=page,
        limit=page_size,
        pages=pages,
        has_next=has_next,
    )