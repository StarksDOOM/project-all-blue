"""Faceted property list filters — compile + HTTP integration."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from models import PropertyListing
from schemas.property_filters import PropertyFilterParams
from services.property_list_service import compile_property_filters, list_properties_paginated


def test_compile_filters_price_and_beds() -> None:
    criteria = compile_property_filters(
        PropertyFilterParams(
            source_portal="remaxrd",
            price_min=100_000.0,
            price_max=500_000.0,
            bedrooms_min=3,
        )
    )
    assert len(criteria) >= 5


def test_list_filters_by_sector(
    api_client: TestClient,
    seeded_property: PropertyListing,
) -> None:
    response = api_client.get(
        "/api/v1/properties",
        params={
            "source_portal": "remaxrd",
            "sector": seeded_property.sector,
            "limit": 10,
            "include_total": "false",
        },
    )
    assert response.status_code == 200
    body = response.json()
    remote_ids = {row["remote_id"] for row in body["data"]}
    assert seeded_property.remote_id in remote_ids


def test_list_rejects_invalid_price_range(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/properties",
        params={"price_min": 500000, "price_max": 100000},
    )
    assert response.status_code == 400


def test_list_keyword_filter(
    db_session: Session,
    seeded_property: PropertyListing,
) -> None:
    result = list_properties_paginated(
        db_session,
        filters=PropertyFilterParams(
            source_portal="remaxrd",
            keyword="Pytest Integration",
        ),
        page=1,
        page_size=20,
        include_total=False,
    )
    assert any(row.remote_id == seeded_property.remote_id for row in result.rows)