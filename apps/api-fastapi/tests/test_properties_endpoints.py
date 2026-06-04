"""
Integration tests for GET /api/v1/properties/{property_id}.

Uses real Postgres (see tests/conftest.py). Run from apps/api-fastapi:

    pytest tests/test_properties_endpoints.py -v
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi.testclient import TestClient

from models import PropertyListing
from tests.conftest import PROPERTY_RESPONSE_KEYS


def _assert_property_payload(body: dict, expected: PropertyListing) -> None:
    """Validate 200 response contains full, un-truncated PropertyListing fields."""
    assert set(body.keys()) == PROPERTY_RESPONSE_KEYS
    assert body["id"] == expected.id
    assert body["remote_id"] == expected.remote_id
    assert body["source_portal"] == expected.source_portal
    assert body["title"] == expected.title
    assert body["price_usd"] == expected.price_usd
    assert body["price_dop"] == expected.price_dop
    assert body["province"] == expected.province
    assert body["sector"] == expected.sector
    assert body["bedrooms"] == expected.bedrooms
    assert body["bathrooms"] == expected.bathrooms
    assert body["square_meters"] == expected.square_meters
    assert body["raw_description"] == expected.raw_description
    assert body["is_active"] is expected.is_active
    assert body["deleted_at"] is None


def test_get_property_by_int_id_success(
    api_client: TestClient,
    seeded_property: PropertyListing,
) -> None:
    """
    Numeric path segment resolves portal remote_id (e.g. 222574).

    All Blue internal PK is a Blu string (#BLU-…); integer-style URLs use remote_id.
    """
    response = api_client.get(
        f"/api/v1/properties/{seeded_property.remote_id}?refresh_from_portal=false"
    )

    assert response.status_code == 200
    body = response.json()
    assert body.get("portal_refresh_failed") is False
    _assert_property_payload(body, seeded_property)


def test_get_property_by_remote_id_success(
    api_client: TestClient,
    seeded_property: PropertyListing,
) -> None:
    """Explicit string remote_id returns 200 with full row payload."""
    response = api_client.get(
        f"/api/v1/properties/{seeded_property.remote_id}?refresh_from_portal=false"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["remote_id"] == seeded_property.remote_id
    assert body.get("portal_refresh_failed") is False
    _assert_property_payload(body, seeded_property)


def test_get_property_by_internal_blu_id_success(
    api_client: TestClient,
    seeded_property: PropertyListing,
) -> None:
    """Internal database primary key (Blu id string) resolves successfully."""
    encoded_id = quote(seeded_property.id, safe="")
    response = api_client.get(
        f"/api/v1/properties/{encoded_id}?refresh_from_portal=false"
    )

    assert response.status_code == 200
    body = response.json()
    assert body.get("portal_refresh_failed") is False
    _assert_property_payload(body, seeded_property)


def test_get_property_not_found(api_client: TestClient) -> None:
    """Unknown id and remote_id return 404 with exact detail payload."""
    response = api_client.get("/api/v1/properties/invalid-asset-id-00000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "Property asset not found"}