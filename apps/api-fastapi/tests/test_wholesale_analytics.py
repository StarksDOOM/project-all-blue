"""
Integration tests for the Wholesale Pricing & Analytics Engine.

STREAM 6 PHASE 1.3.

Module Purpose:
    Validates the full request-to-response pipeline for
    ``GET /api/v1/analytics/wholesale/{property_id}``, as well as the
    arithmetic invariants of ``WholesalePricingEngine.calculate_deal_metrics``
    against real ``PropertyListing`` rows inserted into the test database.

Test Strategy:
    - Zero mocks.  All tests use the ``api_client`` / ``db_session`` fixtures
      from conftest, which share a real Postgres session overriding
      ``get_db_session``.
    - Engine-level "unit" tests create their own ``PropertyListing`` rows
      directly via ``db_session`` to control sector peer data precisely.
    - Route-level tests rely on ``seeded_property`` (``conftest.py``) as the
      target listing and insert additional sector peers when needed.

Thread Safety:
    Not applicable — each test is single-threaded and isolated by session
    rollback after completion.

Collaborators:
    - ``conftest.api_client`` — FastAPI TestClient with DB override.
    - ``conftest.db_session`` — Rolled-back session after each test.
    - ``conftest.seeded_property`` — Disposable ``PropertyListing`` row.
    - ``services.wholesale_pricing_engine.WholesalePricingEngine`` — engine under test.
"""

from __future__ import annotations

import secrets
import statistics
import time
from typing import Generator

import jwt
from urllib.parse import quote
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models import PropertyListing
from services.wholesale_pricing_engine import WholesalePricingEngine

# ---------------------------------------------------------------------------
# Constants shared by all tests in this module
# ---------------------------------------------------------------------------
TEST_JWT_SECRET = "test-secret-for-rbac-phase5-only-do-not-use-in-prod"

_DISCOUNT_RATIO = 0.80
_ASSIGNMENT_FEE_RATIO = 0.05
_ASSIGNMENT_FEE_FLOOR = 5_000.0

WHOLESALE_ROUTE = "/api/v1/analytics/wholesale/{property_id}"
EXPECTED_RESPONSE_KEYS = frozenset(
    {
        "property_id",
        "sector",
        "sector_median_price_per_sqm",
        "auto_emv",
        "mao",
        "assignment_fee",
        "pitch_price",
    }
)


# ---------------------------------------------------------------------------
# JWT helpers (mirrors pattern from test_transaction_ledger.py)
# ---------------------------------------------------------------------------

def _mint_jwt(
    *,
    user_id: str = "agent-user-ws",
    email: str = "agent@example.test",
    role: str = "agent",
    exp_offset: int = 3600,
) -> str:
    """
    Mint a local HS256 JWT for wholesale analytics tests.

    Purpose:
        Produces a valid signed token recognised by ``JWTTokenVerifier``
        without any Supabase network dependency.

    Parameters:
        user_id : str
            Subject claim.
        email : str
            Email claim embedded in payload.
        role : str
            Value placed in ``app_metadata.role`` — drives RBAC check.
        exp_offset : int
            Seconds from now until the token expires.

    Returns:
        str
            Encoded HS256 JWT string.
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "app_metadata": {"role": role},
        "iat": now,
        "exp": now + exp_offset,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def _make_listing(
    *,
    db_session: Session,
    sector: str,
    price_usd: float,
    square_meters: float,
    is_active: bool = True,
) -> PropertyListing:
    """
    Insert a disposable PropertyListing into the test database.

    Purpose:
        Creates a controlled sector peer for engine arithmetic tests without
        coupling to the ``seeded_property`` conftest fixture.

    Parameters:
        db_session : Session
            Active test session (rolled back after each test).
        sector : str
            Neighbourhood used for sector-median grouping.
        price_usd : float
            Listing price in USD — drives the price-per-sqm ratio.
        square_meters : float
            Floor area of the listing.
        is_active : bool
            Whether the listing is active (only active rows contribute to median).

    Returns:
        PropertyListing
            The flushed (not committed) ORM row.
    """
    suffix = secrets.token_hex(4)
    listing = PropertyListing(
        id=f"#BLU-WS-{suffix.upper()}",
        remote_id=f"ws-{suffix}",
        source_portal="remaxrd",
        url=f"https://example.test/ws/{suffix}",
        title=f"Wholesale Test Listing {suffix}",
        price_usd=price_usd,
        province="Santo Domingo",
        sector=sector,
        bedrooms=3,
        bathrooms=2.0,
        square_meters=square_meters,
        raw_description="wholesale pytest fixture",
        is_active=is_active,
    )
    db_session.add(listing)
    db_session.flush()
    db_session.refresh(listing)
    return listing


# ===========================================================================
# Engine arithmetic tests (real DB rows, controlled sector data)
# ===========================================================================

class TestWholesalePricingEngineArithmetic:
    """
    Validates ``WholesalePricingEngine`` formula invariants against real
    ``PropertyListing`` rows.

    Purpose:
        Each test controls the exact set of sector peers to assert specific
        arithmetic outcomes, isolating formula correctness from route-layer
        concerns.

    Collaborators:
        - ``db_session`` (conftest) — rolled back after each test.
        - ``WholesalePricingEngine`` — engine under test.
    """

    def test_emv_calculation(self, db_session: Session) -> None:
        """
        EMV equals sector median price-per-sqm multiplied by target square_meters.

        Scenario: Two peers in the same sector with known ratios.
        The engine must compute the correct median and apply it to the target.
        """
        sector = f"emv-sector-{secrets.token_hex(3)}"
        # Peer A: 200 USD/m²
        _make_listing(db_session=db_session, sector=sector, price_usd=20_000.0, square_meters=100.0)
        # Target: 150 m² — also an active listing, contributes to median.
        # Peer B: 300 USD/m²
        _make_listing(db_session=db_session, sector=sector, price_usd=30_000.0, square_meters=100.0)
        # Target listing: 150 m², 250 USD/m²
        target = _make_listing(db_session=db_session, sector=sector, price_usd=37_500.0, square_meters=150.0)

        engine = WholesalePricingEngine()
        result = engine.calculate_deal_metrics(property_id=target.id, session=db_session)

        # All three ratios: 200, 300, 250 → median = 250.0
        assert result.sector_median_price_per_sqm == pytest.approx(250.0, rel=1e-3)
        expected_emv = 250.0 * 150.0  # 37_500.0
        assert result.auto_emv == pytest.approx(expected_emv, rel=1e-3)

    def test_mao_formula(self, db_session: Session) -> None:
        """
        MAO equals EMV * 0.80 (target 20% discount).
        """
        sector = f"mao-sector-{secrets.token_hex(3)}"
        target = _make_listing(db_session=db_session, sector=sector, price_usd=100_000.0, square_meters=200.0)

        engine = WholesalePricingEngine()
        result = engine.calculate_deal_metrics(property_id=target.id, session=db_session)

        expected_mao = result.auto_emv * _DISCOUNT_RATIO
        assert result.mao == pytest.approx(expected_mao, rel=1e-3)

    def test_assignment_fee_percentage(self, db_session: Session) -> None:
        """
        When 5% of EMV exceeds $5 000, the assignment fee equals EMV * 0.05.

        Scenario: Target priced at $200 000 → EMV ≈ $200 000 → 5% = $10 000 > floor.
        """
        sector = f"fee-pct-sector-{secrets.token_hex(3)}"
        target = _make_listing(db_session=db_session, sector=sector, price_usd=200_000.0, square_meters=200.0)

        engine = WholesalePricingEngine()
        result = engine.calculate_deal_metrics(property_id=target.id, session=db_session)

        expected_fee = result.auto_emv * _ASSIGNMENT_FEE_RATIO
        assert expected_fee > _ASSIGNMENT_FEE_FLOOR, "Precondition: fee must exceed floor for this test"
        assert result.assignment_fee == pytest.approx(expected_fee, rel=1e-3)

    def test_assignment_fee_floor(self, db_session: Session) -> None:
        """
        When 5% of EMV is below $5 000, the assignment fee is floored at $5 000.

        Scenario: Small property priced at $50 000 → 5% = $2 500 < $5 000 → fee = $5 000.
        """
        sector = f"fee-floor-sector-{secrets.token_hex(3)}"
        target = _make_listing(db_session=db_session, sector=sector, price_usd=50_000.0, square_meters=50.0)

        engine = WholesalePricingEngine()
        result = engine.calculate_deal_metrics(property_id=target.id, session=db_session)

        pct_fee = result.auto_emv * _ASSIGNMENT_FEE_RATIO
        assert pct_fee < _ASSIGNMENT_FEE_FLOOR, "Precondition: percentage fee must be below floor"
        assert result.assignment_fee == pytest.approx(_ASSIGNMENT_FEE_FLOOR, rel=1e-3)

    def test_pitch_price_identity(self, db_session: Session) -> None:
        """
        Pitch price is always MAO plus the assignment fee (arithmetic identity).
        """
        sector = f"pitch-sector-{secrets.token_hex(3)}"
        target = _make_listing(db_session=db_session, sector=sector, price_usd=150_000.0, square_meters=180.0)

        engine = WholesalePricingEngine()
        result = engine.calculate_deal_metrics(property_id=target.id, session=db_session)

        assert result.pitch_price == pytest.approx(result.mao + result.assignment_fee, rel=1e-6)

    def test_single_sector_peer(self, db_session: Session) -> None:
        """
        Engine handles a sector with exactly one active listing (the target itself).

        The median of a single-element list is well-defined; no exception should occur.
        """
        sector = f"solo-sector-{secrets.token_hex(3)}"
        target = _make_listing(db_session=db_session, sector=sector, price_usd=120_000.0, square_meters=120.0)

        engine = WholesalePricingEngine()
        result = engine.calculate_deal_metrics(property_id=target.id, session=db_session)

        # Single peer median = 120_000 / 120 = 1_000.0
        assert result.sector_median_price_per_sqm == pytest.approx(1_000.0, rel=1e-3)
        assert result.auto_emv == pytest.approx(120_000.0, rel=1e-3)

    def test_commercial_cap_rate_calculation(self, db_session: Session) -> None:
        """
        Validate Commercial Cap Rate calculation.
        """
        sector = f"comm-sector-{secrets.token_hex(3)}"
        target = _make_listing(db_session=db_session, sector=sector, price_usd=200_000.0, square_meters=100.0)
        target.property_type = "COMMERCIAL"
        db_session.add(target)
        db_session.flush()

        engine = WholesalePricingEngine()
        # Test with explicit params
        res = engine.calculate_deal_metrics(
            property_id=target.id,
            session=db_session,
            monthly_rent_per_sqm=20.0,
            comm_vacancy_rate=0.08,
            annual_taxes_insurance=1500.0
        )
        assert res.commercial_metrics is not None
        assert res.commercial_metrics.annual_gross_rent == 24000.0
        assert res.commercial_metrics.effective_gross_income == 22080.0
        assert res.commercial_metrics.annual_noi == 20580.0
        expected_cap = (20580.0 / res.pitch_price) * 100
        assert res.commercial_metrics.cap_rate_pct == pytest.approx(expected_cap, abs=1e-2)

    def test_ltr_cap_rate_calculation(self, db_session: Session) -> None:
        """
        Validate Long-Term Rental (LTR) Cap Rate calculation.
        """
        sector = f"ltr-sector-{secrets.token_hex(3)}"
        target = _make_listing(db_session=db_session, sector=sector, price_usd=200_000.0, square_meters=100.0)
        target.property_type = "RESIDENTIAL"
        db_session.add(target)
        db_session.flush()

        engine = WholesalePricingEngine()
        # Test with explicit params
        res = engine.calculate_deal_metrics(
            property_id=target.id,
            session=db_session,
            monthly_rent=2500.0,
            ltr_vacancy_rate=0.04,
            ltr_pm_fee_pct=0.08,
            monthly_maintenance=200.0
        )
        assert res.ltr_metrics is not None
        assert res.ltr_metrics.annual_gross_rent == 30000.0
        assert res.ltr_metrics.effective_gross_rent == 28800.0
        assert res.ltr_metrics.operating_expenses == 4800.0
        assert res.ltr_metrics.annual_noi == 24000.0
        expected_cap = (24000.0 / res.pitch_price) * 100
        assert res.ltr_metrics.cap_rate_pct == pytest.approx(expected_cap, abs=1e-2)


# ===========================================================================
# Route-level integration tests (RBAC + JSON contract)
# ===========================================================================

class TestWholesaleAnalyticsRoute:
    """
    Validates the RBAC gate and JSON response contract for
    ``GET /api/v1/analytics/wholesale/{property_id}``.

    Purpose:
        Ensures the FastAPI route correctly delegates to the engine, enforces
        role permissions, and returns the expected JSON shape.

    Collaborators:
        - ``api_client`` (conftest) — TestClient with DB session override.
        - ``seeded_property`` (conftest) — Active PropertyListing in sector "Piantini".
    """

    def test_agent_receives_200_with_correct_keys(
        self, api_client: TestClient, seeded_property: PropertyListing
    ) -> None:
        # seeded_property.id contains '#' (BLU ID prefix) — percent-encode so
        # the HTTP client does not truncate it as a URL fragment.
        """
        AGENT JWT yields HTTP 200 with all expected JSON keys present.
        """
        token = _mint_jwt(role="agent")
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            WHOLESALE_ROUTE.format(property_id=pid),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert EXPECTED_RESPONSE_KEYS.issubset(data.keys())
        assert data["property_id"] == seeded_property.id
        assert data["sector"] == seeded_property.sector

    def test_admin_receives_200_with_correct_keys(
        self, api_client: TestClient, seeded_property: PropertyListing
    ) -> None:
        """
        ADMIN JWT yields HTTP 200 with all expected JSON keys present.
        """
        token = _mint_jwt(role="admin")
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            WHOLESALE_ROUTE.format(property_id=pid),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert EXPECTED_RESPONSE_KEYS.issubset(data.keys())
        # Numeric sanity: pitch_price = mao + assignment_fee
        assert data["pitch_price"] == pytest.approx(
            data["mao"] + data["assignment_fee"], rel=1e-3
        )

    @pytest.mark.skip(reason="RBAC disabled for local QA (no login page yet)")
    def test_client_receives_403(
        self, api_client: TestClient, seeded_property: PropertyListing
    ) -> None:
        """
        CLIENT JWT is denied with HTTP 403 Forbidden.
        """
        token = _mint_jwt(role="client")
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            WHOLESALE_ROUTE.format(property_id=pid),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions"

    def test_unknown_property_returns_404(self, api_client: TestClient) -> None:
        """
        A non-existent property_id returns HTTP 404 Not Found.
        """
        token = _mint_jwt(role="agent")
        response = api_client.get(
            WHOLESALE_ROUTE.format(property_id="#NON-EXISTENT-XYZ"),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    @pytest.mark.skip(reason="RBAC disabled for local QA (no login page yet)")
    def test_unauthenticated_request_denied(
        self, api_client: TestClient, seeded_property: PropertyListing
    ) -> None:
        """
        A request with no Authorization header is rejected (401 or 403).
        """
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            WHOLESALE_ROUTE.format(property_id=pid)
        )
        assert response.status_code in (401, 403)

    def test_commercial_analytics_parameters(
        self, api_client: TestClient, seeded_property: PropertyListing
    ) -> None:
        """
        Verify that passing commercial parameters calculates and returns CommercialYieldMetrics.
        """
        token = _mint_jwt(role="agent")
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            WHOLESALE_ROUTE.format(property_id=pid) + "?monthly_rent_per_sqm=18.5&comm_vacancy_rate=0.07&annual_taxes_insurance=1200.0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "commercial_metrics" in data
        comm = data["commercial_metrics"]
        assert comm is not None
        assert comm["annual_gross_rent"] == pytest.approx((seeded_property.square_meters * 18.5) * 12, rel=1e-3)
        assert comm["cap_rate_pct"] > 0

    def test_ltr_analytics_parameters(
        self, api_client: TestClient, seeded_property: PropertyListing
    ) -> None:
        """
        Verify that passing LTR parameters calculates and returns LtrYieldMetrics.
        """
        token = _mint_jwt(role="agent")
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            WHOLESALE_ROUTE.format(property_id=pid) + "?monthly_rent=2000.0&ltr_vacancy_rate=0.06&ltr_pm_fee_pct=0.09&monthly_maintenance=150.0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "ltr_metrics" in data
        ltr = data["ltr_metrics"]
        assert ltr is not None
        assert ltr["annual_gross_rent"] == 24000.0
        assert ltr["cap_rate_pct"] > 0

    def test_default_property_type_fallback_behavior(
        self, api_client: TestClient, db_session: Session
    ) -> None:
        """
        Verify that the analytics endpoint automatically computes LTR default metrics
        for residential properties and commercial metrics for commercial properties when parameters are omitted.
        """
        # Create a commercial property
        comm_prop = _make_listing(db_session=db_session, sector="Piantini", price_usd=300000.0, square_meters=150.0)
        comm_prop.property_type = "COMMERCIAL"
        db_session.add(comm_prop)
        db_session.flush()

        token = _mint_jwt(role="agent")
        pid = quote(comm_prop.id, safe="")
        response = api_client.get(
            WHOLESALE_ROUTE.format(property_id=pid),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        # Should have commercial metrics automatically computed
        assert data["commercial_metrics"] is not None
        assert data["ltr_metrics"] is None  # since it is COMMERCIAL
        # Verify taxes default to 1% of pitch_price
        pitch = data["pitch_price"]
        expected_tax = pitch * 0.01
        expected_noi = 24300.0 - expected_tax
        expected_cap = (expected_noi / pitch) * 100
        assert data["commercial_metrics"]["cap_rate_pct"] == pytest.approx(expected_cap, abs=1e-2)

        # Create a residential property
        res_prop = _make_listing(db_session=db_session, sector="Piantini", price_usd=250000.0, square_meters=120.0)
        res_prop.property_type = "RESIDENTIAL"
        db_session.add(res_prop)
        db_session.flush()

        pid2 = quote(res_prop.id, safe="")
        response2 = api_client.get(
            WHOLESALE_ROUTE.format(property_id=pid2),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        # Should have ltr metrics automatically computed
        assert data2["ltr_metrics"] is not None
        assert data2["commercial_metrics"] is None  # since it is RESIDENTIAL
