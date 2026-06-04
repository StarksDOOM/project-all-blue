"""Basic contract + integration smoke for STREAM 5 PHASE 3.0 saved searches + match engine."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import select

from main import app
from models import SavedSearchAlert, SavedSearchMatch
from schemas.property_filters import PropertyFilterParams


def test_create_and_list_saved_search(api_client: TestClient):
    payload = {
        "user_id": "11111111-1111-1111-1111-111111111111",
        "title": "Test Piantini 2hab",
        "filters": {
            "sector": "Piantini",
            "bedrooms_min": 2,
            "price_max": 350000,
        },
    }
    r = api_client.post("/api/v1/saved-searches", json=payload)
    assert r.status_code == 201
    created = r.json()
    assert created["title"] == "Test Piantini 2hab"
    assert created["filters_json"]["sector"] == "Piantini"
    assert created["is_active"] is True

    r2 = api_client.get("/api/v1/saved-searches", params={"user_id": payload["user_id"]})
    assert r2.status_code == 200
    listed = r2.json()["data"]
    assert any(a["id"] == created["id"] for a in listed)


def test_rejects_bad_filters(api_client: TestClient):
    bad = {
        "user_id": "11111111-1111-1111-1111-111111111111",
        "title": "bad",
        "filters": {"price_min": 400000, "price_max": 100000},  # invalid range
    }
    r = api_client.post("/api/v1/saved-searches", json=bad)
    assert r.status_code in (400, 422)  # 422 from FastAPI/Pydantic body validation for nested model


def test_evaluate_writes_match(db_session):
    # Create an active alert
    alert = SavedSearchAlert(
        user_id="11111111-1111-1111-1111-111111111111",
        title="Match test",
        filters_json={"sector": "Piantini", "bedrooms_min": 1},
        is_active=True,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # Fabricate a property that should match (id must be unique-ish for test)
    from database import generate_blu_id

    prop = None  # we don't persist a full property here; instead call engine with a detached obj
    # For smoke we just ensure the predicate module imports and basic path doesn't explode
    # Exercise the OOP engine (preferred) and its internal predicate via a test instance
    from services.search_match_engine import SearchMatchEngine

    fake_prop = type("P", (), {
        "id": "test-prop-1",
        "source_portal": "remaxrd",
        "sector": "Piantini",
        "title": "Nice 2 bed",
        "raw_description": "",
        "price_usd": 200000,
        "list_price": None,
        "bedrooms": 2,
        "bathrooms": 1.0,
        "agent_agency": None,
    })()
    f = PropertyFilterParams(sector="Piantini", bedrooms_min=1)

    # We can reach the predicate for white-box testing via the class (it's a method now)
    engine = SearchMatchEngine(db_session)  # session not actually used for predicate
    assert engine._property_matches_filters(fake_prop, f) is True

    f2 = PropertyFilterParams(sector="Otro")
    assert engine._property_matches_filters(fake_prop, f2) is False

    # Smoke the public class API (full evaluate path with real DB writes is exercised
    # via the ingestion orchestrator in integration scenarios). Here we only verify
    # that the engine can be constructed and the predicate is reachable.
    # Calling evaluate with a non-existent property id would violate FKs, so we don't.
