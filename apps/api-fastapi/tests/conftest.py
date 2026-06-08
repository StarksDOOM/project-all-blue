"""
Pytest fixtures — real Postgres via DATABASE_URL (no mocked DB layer).

Requires: schema bootstrapped (init_db), Docker Postgres up for CI/local integration runs.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

# Phase 5.0: ensure SUPABASE_JWT_SECRET is present *before* any import that triggers
# services.auth module-level JWTTokenVerifier() construction. This prevents import-time
# RuntimeError during test collection.
os.environ.setdefault(
    "SUPABASE_JWT_SECRET",
    "test-secret-for-rbac-phase5-only-do-not-use-in-prod",
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import engine, get_db_session, init_db  # noqa: E402
from main import app  # noqa: E402
from models import LegalContract, PropertyListing, SavedSearchAlert, SavedSearchMatch, TransactionSession  # noqa: E402
from tests.db_cleanup import delete_property_cascade  # noqa: E402

# Full PropertyListing JSON shape returned by GET /api/v1/properties/{property_id}
PROPERTY_RESPONSE_KEYS = frozenset(
    {
        "id",
        "tenant_id",
        "server_version",
        "last_modified",
        "deleted_at",
        "remote_id",
        "source_portal",
        "url",
        "title",
        "price_usd",
        "price_dop",
        "list_price",
        "listing_currency",
        "image_urls",
        "province",
        "sector",
        "bedrooms",
        "bathrooms",
        "square_meters",
        "sqm_land",
        "agent_name",
        "agent_phone",
        "agent_email",
        "agent_whatsapp",
        "agent_agency",
        "raw_description",
        "is_active",
        "portal_refresh_failed",
        "portal_refresh_message",
    }
)


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_schema() -> None:
    """Ensure tables and ingestion indexes exist once per test session."""
    init_db()


@pytest.fixture(autouse=True)
def _default_internal_signing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 5 signature tests use internal provider unless test_docusign overrides."""
    monkeypatch.setenv("DOCUSIGN_PROVIDER", "")
    from config.docusign_settings import get_docusign_settings

    get_docusign_settings.cache_clear()


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 5.0 RBAC: provide a test JWT secret so module-level JWTTokenVerifier() succeeds.
    Tests that need specific claims use local minting; this just prevents import-time crash.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-for-rbac-phase5-only-do-not-use-in-prod")
    # Clear any cached verifiers if added later
    try:
        from services.auth import _default_verifier  # type: ignore[attr-defined]
        # Re-init not strictly needed; secret read at construction time in tests
    except Exception:
        pass


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Transactional session; rolls back after each test to avoid polluting inventory."""
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture()
def seeded_property(db_session: Session) -> Generator[PropertyListing, None, None]:
    """
    Insert a disposable PropertyListing row for endpoint integration tests.

    Uses a numeric remote_id so integer-style URL segments are exercised.
    """
    suffix = secrets.token_hex(3)
    numeric_remote_id = str(900_000 + int(suffix, 16) % 99_000)
    blu_id = f"#BLU-TEST{suffix.upper()}"

    listing = PropertyListing(
        id=blu_id,
        remote_id=numeric_remote_id,
        source_portal="remaxrd",
        url=f"https://example.test/properties/{numeric_remote_id}",
        title=f"Pytest Integration Asset {suffix}",
        price_usd=185_000.0,
        price_dop=11_007_500.0,
        province="Santo Domingo",
        sector="Piantini",
        bedrooms=3,
        bathrooms=2.5,
        square_meters=142.0,
        raw_description="currency=DOP|alquiler|pytest fixture",
        is_active=True,
    )
    db_session.add(listing)
    db_session.flush()
    db_session.refresh(listing)

    yield listing
    # Rolled back by db_session fixture — no committed pytest rows when tests finish cleanly.


@pytest.fixture()
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with get_db_session overridden to the test session."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clean_test_db_rows() -> Generator[None, None, None]:
    """
    Autouse fixture that runs after every single test function to ensure
    all test-created DB rows are completely purged from the Postgres database.
    """
    yield
    from sqlmodel import text
    with Session(engine) as session:
        # Delete matches linked to test alerts or test properties
        session.exec(
            text(
                "DELETE FROM real_estate.saved_search_matches "
                "WHERE property_id LIKE '#BLU-TEST%' OR property_id LIKE '#BLU-WS%' "
                "OR property_id IN (SELECT id FROM real_estate.properties WHERE remote_id LIKE 'test-remote-%') "
                "OR saved_search_alert_id IN ("
                "   SELECT id FROM real_estate.saved_search_alerts "
                "   WHERE user_id LIKE 'limit-test-%' OR user_id = '11111111-1111-1111-1111-111111111111' OR user_id = 'test-user-1'"
                ")"
            )
        )
        # Delete legal contracts linked to test properties or test transaction sessions
        session.exec(
            text(
                "DELETE FROM real_estate.legal_contracts "
                "WHERE property_id LIKE '#BLU-TEST%' OR property_id LIKE '#BLU-WS%' "
                "OR property_id IN (SELECT id FROM real_estate.properties WHERE remote_id LIKE 'test-remote-%') "
                "OR transaction_session_id IN ("
                "   SELECT id FROM real_estate.transaction_sessions "
                "   WHERE property_id LIKE '#BLU-TEST%' OR property_id LIKE '#BLU-WS%' "
                "      OR property_id IN (SELECT id FROM real_estate.properties WHERE remote_id LIKE 'test-remote-%') "
                ")"
            )
        )
        # Delete transaction sessions linked to test properties
        session.exec(
            text(
                "DELETE FROM real_estate.transaction_sessions "
                "WHERE property_id LIKE '#BLU-TEST%' OR property_id LIKE '#BLU-WS%' "
                "OR property_id IN (SELECT id FROM real_estate.properties WHERE remote_id LIKE 'test-remote-%')"
            )
        )
        # Delete saved search alerts for test users or with test titles
        session.exec(
            text(
                "DELETE FROM real_estate.saved_search_alerts "
                "WHERE user_id LIKE 'limit-test-%' OR user_id = '11111111-1111-1111-1111-111111111111' "
                "OR user_id = 'test-user-1' OR user_id = 'agent-user-ws' OR user_id = 'agent-user-123' "
                "OR user_id = 'agent-uid-100' OR user_id = 'agent-uid-200' "
                "OR title LIKE 'Client Cap%' OR title = 'Match test' "
                "OR title = 'Test Piantini 2hab' OR title = 'Test Alert for Notifications'"
            )
        )
        # Delete properties with test patterns
        session.exec(
            text(
                "DELETE FROM real_estate.properties "
                "WHERE id LIKE '#BLU-TEST%' OR id LIKE '#BLU-WS%' "
                "OR remote_id = '222598' OR remote_id LIKE 'test-remote-%'"
            )
        )
        # Delete scraper error logs for test IDs
        session.exec(
            text(
                "DELETE FROM real_estate.scraper_error_logs "
                "WHERE remote_id IN ('222598', '999001', '999002')"
            )
        )
        session.commit()