"""
Integration tests for the Multi-Source Lead Magnet Engine.

STREAM 6 PHASE 1.7.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from models import LeadCapture


def test_create_lead_capture_success(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Validate successful lead capture via API and verify database persistence."""
    payload = {
        "email": "investor@example.com",
        "location_slug": "punta-cana",
        "traffic_source": "fb-ad",
        "simulated_purchase_price": 285000.0,
        "simulated_nightly_rate": 180.0,
        "simulated_occupancy": 0.65,
        "simulated_maintenance": 220.0,
    }

    response = api_client.post("/api/v1/leads/capture", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    lead_id = data["id"]

    # Verify database persistence
    db_session.rollback()  # Sync session transactions
    lead = db_session.exec(
        select(LeadCapture).where(LeadCapture.id == lead_id)
    ).first()

    assert lead is not None
    assert lead.email == "investor@example.com"
    assert lead.location_slug == "punta-cana"
    assert lead.traffic_source == "fb-ad"
    assert lead.simulated_purchase_price == 285000.0
    assert lead.simulated_nightly_rate == 180.0
    assert lead.simulated_occupancy == 0.65
    assert lead.simulated_maintenance == 220.0
    assert lead.created_at is not None


def test_create_lead_capture_default_traffic_source(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Verify that traffic_source defaults to 'organic' when omitted."""
    payload = {
        "email": "organic-investor@example.com",
        "location_slug": "samana",
        # traffic_source omitted
        "simulated_purchase_price": 195000.0,
        "simulated_nightly_rate": 120.0,
        "simulated_occupancy": 0.40,
        "simulated_maintenance": 150.0,
    }

    response = api_client.post("/api/v1/leads/capture", json=payload)
    assert response.status_code == 201

    lead_id = response.json()["id"]

    db_session.rollback()
    lead = db_session.exec(
        select(LeadCapture).where(LeadCapture.id == lead_id)
    ).first()

    assert lead is not None
    assert lead.traffic_source == "organic"


def test_create_lead_capture_invalid_email(api_client: TestClient) -> None:
    """Validate invalid email rejection with 422 Unprocessable Entity."""
    invalid_emails = [
        "not-an-email",
        "investor@",
        "@example.com",
        "investor@example",
    ]

    for bad_email in invalid_emails:
        payload = {
            "email": bad_email,
            "location_slug": "punta-cana",
            "traffic_source": "fb-ad",
            "simulated_purchase_price": 250000.0,
            "simulated_nightly_rate": 150.0,
            "simulated_occupancy": 0.50,
            "simulated_maintenance": 150.0,
        }

        response = api_client.post("/api/v1/leads/capture", json=payload)
        assert response.status_code == 422


def test_create_lead_capture_invalid_simulated_values(api_client: TestClient) -> None:
    """Validate constraints on simulated parameters (e.g. occupancy bounds)."""
    bad_payloads = [
        # Negative purchase price
        {
            "email": "investor@example.com",
            "location_slug": "punta-cana",
            "simulated_purchase_price": -100.0,
            "simulated_nightly_rate": 150.0,
            "simulated_occupancy": 0.50,
            "simulated_maintenance": 150.0,
        },
        # Occupancy too high (> 1.0)
        {
            "email": "investor@example.com",
            "location_slug": "punta-cana",
            "simulated_purchase_price": 250000.0,
            "simulated_nightly_rate": 150.0,
            "simulated_occupancy": 1.2,
            "simulated_maintenance": 150.0,
        },
        # Negative occupancy
        {
            "email": "investor@example.com",
            "location_slug": "punta-cana",
            "simulated_purchase_price": 250000.0,
            "simulated_nightly_rate": 150.0,
            "simulated_occupancy": -0.1,
            "simulated_maintenance": 150.0,
        },
    ]

    for payload in bad_payloads:
        response = api_client.post("/api/v1/leads/capture", json=payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# STREAM 6 PHASE 1.7.1 — GET /api/v1/leads integration tests
# ---------------------------------------------------------------------------

def _make_lead_payload(email: str, location_slug: str = "punta-cana") -> dict:
    """Build a minimal valid lead capture payload."""
    return {
        "email": email,
        "location_slug": location_slug,
        "traffic_source": "organic",
        "simulated_purchase_price": 200000.0,
        "simulated_nightly_rate": 150.0,
        "simulated_occupancy": 0.60,
        "simulated_maintenance": 200.0,
    }


def test_list_leads_returns_newest_first(
    api_client: TestClient,
) -> None:
    """Verify GET /api/v1/leads returns records sorted newest-first (created_at DESC)."""
    # Create three leads in sequence
    emails = [
        "first@example.com",
        "second@example.com",
        "third@example.com",
    ]
    created_ids = []
    for email in emails:
        r = api_client.post("/api/v1/leads/capture", json=_make_lead_payload(email))
        assert r.status_code == 201
        created_ids.append(r.json()["id"])

    response = api_client.get("/api/v1/leads")
    assert response.status_code == 200

    body = response.json()
    assert "data" in body
    assert "total" in body
    assert "skip" in body
    assert "limit" in body

    # Filter to the three leads we just created (other tests may have created leads too)
    our_rows = [row for row in body["data"] if row["id"] in created_ids]
    assert len(our_rows) == 3

    # The list endpoint is globally sorted newest-first, so our third lead
    # should appear before the first.
    our_positions = {row["id"]: idx for idx, row in enumerate(body["data"])}
    assert our_positions[created_ids[2]] < our_positions[created_ids[0]], (
        "Third (newest) lead should appear before the first (oldest) in the sorted list"
    )


def test_list_leads_pagination_skip_limit(
    api_client: TestClient,
) -> None:
    """Verify skip and limit query params correctly slice the lead list."""
    # Create 4 leads so we have a stable set to paginate
    for i in range(4):
        r = api_client.post(
            "/api/v1/leads/capture",
            json=_make_lead_payload(f"page-test-{i}@example.com"),
        )
        assert r.status_code == 201

    # Fetch first page of 2
    r1 = api_client.get("/api/v1/leads?skip=0&limit=2")
    assert r1.status_code == 200
    body1 = r1.json()
    assert len(body1["data"]) == 2
    assert body1["limit"] == 2
    assert body1["skip"] == 0

    # Fetch second page of 2
    r2 = api_client.get("/api/v1/leads?skip=2&limit=2")
    assert r2.status_code == 200
    body2 = r2.json()
    assert len(body2["data"]) == 2
    assert body2["skip"] == 2

    # Pages must not overlap
    ids_page1 = {row["id"] for row in body1["data"]}
    ids_page2 = {row["id"] for row in body2["data"]}
    assert ids_page1.isdisjoint(ids_page2), "Pages must not contain the same records"

    # Total must reflect entire dataset, not just the page
    assert body1["total"] >= 4


def test_list_leads_empty(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Verify the list endpoint returns 200 with empty data when no leads exist."""
    from models import LeadCapture as LC
    from sqlmodel import delete as sql_delete

    # Clear the table for this test
    db_session.exec(sql_delete(LC))  # type: ignore[call-overload]
    db_session.commit()

    response = api_client.get("/api/v1/leads")
    assert response.status_code == 200

    body = response.json()
    assert body["data"] == []
    assert body["total"] == 0
    assert body["skip"] == 0
    assert body["limit"] == 100
