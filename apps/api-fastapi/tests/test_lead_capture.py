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
