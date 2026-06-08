"""
Unit tests for STR (Short-Term Rental) yield calculation in WholesalePricingEngine.

STREAM 6 PHASE 1.6 — Airbnb ROI & Pitch Engine.

Tests the ``calculate_str_metrics`` pure-computation method and the
end-to-end API endpoint with STR query parameters.
"""

from __future__ import annotations

import urllib.parse
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models import PropertyListing
from services.str_default_predictor import StrDefaultPredictor
from services.wholesale_pricing_engine import WholesalePricingEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> WholesalePricingEngine:
    """Provide a fresh WholesalePricingEngine instance."""
    return WholesalePricingEngine()


# ---------------------------------------------------------------------------
# Unit tests — calculate_str_metrics (pure computation, no DB)
# ---------------------------------------------------------------------------

class TestCalculateStrMetrics:
    """
    Verify the STR formula produces correct results for known inputs.

    Formula reference (spec-locked):
        monthly_gross = nightly_rate × 30 × occupancy_pct
        pm_cost = monthly_gross × 0.20
        monthly_net = monthly_gross - pm_cost - monthly_maintenance - 150
        annual_noi = monthly_net × 12
        cash_on_cash_pct = (annual_noi / pitch_price) × 100
        projection_Nmo = monthly_net × N
    """

    def test_known_inputs(self, engine: WholesalePricingEngine) -> None:
        """Verify correct calculation with realistic Airbnb numbers."""
        result = engine.calculate_str_metrics(
            nightly_rate=150.0,
            occupancy_pct=0.70,
            monthly_maintenance=300.0,
            pitch_price=200_000.0,
        )

        # monthly_gross = 150 × 30 × 0.70 = 3150.0
        assert result["str_monthly_gross"] == 3150.0

        # pm_cost = 3150.0 × 0.20 = 630.0
        assert result["str_pm_cost"] == 630.0

        # monthly_net = 3150 - 630 - 300 - 150 = 2070.0
        assert result["str_monthly_net"] == 2070.0

        # annual_noi = 2070 × 12 = 24840.0
        assert result["str_annual_noi"] == 24840.0

        # cash_on_cash = (24840 / 200000) × 100 = 12.42
        assert result["str_cash_on_cash_pct"] == 12.42

        # projections
        assert result["str_projection_6mo"] == 2070.0 * 6   # 12420.0
        assert result["str_projection_1yr"] == 2070.0 * 12  # 24840.0
        assert result["str_projection_3yr"] == 2070.0 * 36  # 74520.0

    def test_zero_nightly_rate(self, engine: WholesalePricingEngine) -> None:
        """Zero nightly rate → gross is zero, net is negative (costs only)."""
        result = engine.calculate_str_metrics(
            nightly_rate=0.0,
            occupancy_pct=0.70,
            monthly_maintenance=0.0,
            pitch_price=100_000.0,
        )

        assert result["str_monthly_gross"] == 0.0
        assert result["str_pm_cost"] == 0.0
        # monthly_net = 0 - 0 - 0 - 150 = -150.0
        assert result["str_monthly_net"] == -150.0
        assert result["str_annual_noi"] == -1800.0

    def test_full_occupancy(self, engine: WholesalePricingEngine) -> None:
        """100% occupancy maximises gross income."""
        result = engine.calculate_str_metrics(
            nightly_rate=100.0,
            occupancy_pct=1.0,
            monthly_maintenance=0.0,
            pitch_price=100_000.0,
        )

        # monthly_gross = 100 × 30 × 1.0 = 3000.0
        assert result["str_monthly_gross"] == 3000.0
        # pm = 600, net = 3000 - 600 - 0 - 150 = 2250
        assert result["str_monthly_net"] == 2250.0

    def test_zero_occupancy(self, engine: WholesalePricingEngine) -> None:
        """0% occupancy → zero gross, negative net (costs only)."""
        result = engine.calculate_str_metrics(
            nightly_rate=200.0,
            occupancy_pct=0.0,
            monthly_maintenance=500.0,
            pitch_price=150_000.0,
        )

        assert result["str_monthly_gross"] == 0.0
        # monthly_net = 0 - 0 - 500 - 150 = -650
        assert result["str_monthly_net"] == -650.0

    def test_zero_pitch_price(self, engine: WholesalePricingEngine) -> None:
        """Edge case: pitch_price=0 → cash_on_cash should be 0, not divide-by-zero."""
        result = engine.calculate_str_metrics(
            nightly_rate=100.0,
            occupancy_pct=0.70,
            monthly_maintenance=0.0,
            pitch_price=0.0,
        )

        assert result["str_cash_on_cash_pct"] == 0.0

    def test_high_maintenance_yields_negative_net(self, engine: WholesalePricingEngine) -> None:
        """When maintenance exceeds gross minus PM, net should be negative."""
        result = engine.calculate_str_metrics(
            nightly_rate=50.0,
            occupancy_pct=0.50,
            monthly_maintenance=2000.0,
            pitch_price=100_000.0,
        )

        # gross = 50 × 30 × 0.5 = 750
        # pm = 150
        # net = 750 - 150 - 2000 - 150 = -1550
        assert result["str_monthly_gross"] == 750.0
        assert result["str_monthly_net"] == -1550.0
        assert result["str_annual_noi"] < 0
        assert result["str_cash_on_cash_pct"] < 0

    def test_all_fields_rounded_to_2_decimals(self, engine: WholesalePricingEngine) -> None:
        """Verify all output values are rounded to 2 decimal places."""
        result = engine.calculate_str_metrics(
            nightly_rate=133.33,
            occupancy_pct=0.73,
            monthly_maintenance=275.50,
            pitch_price=187_654.32,
        )

        for key, value in result.items():
            assert value is not None
            # Check that the value has at most 2 decimal places
            assert round(value, 2) == value, f"{key}={value} is not rounded to 2 decimals"


# ---------------------------------------------------------------------------
# Integration tests — API endpoint with STR params
# ---------------------------------------------------------------------------

class TestWholesaleEndpointWithSTR:
    """
    Verify the GET /api/v1/analytics/wholesale/{property_id} endpoint
    correctly returns STR metrics when query params are supplied.
    """

    def test_without_str_params_returns_no_str_fields(
        self,
        api_client: TestClient,
        db_session: Session,
        seeded_property: PropertyListing,
    ) -> None:
        """Backwards-compatibility: no STR params → STR fields are null."""
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            f"/api/v1/analytics/wholesale/{pid}"
        )

        assert response.status_code == 200
        data = response.json()
        # Core wholesale fields should be present
        assert "property_id" in data
        assert "pitch_price" in data
        # STR fields should be null
        assert data["str_monthly_gross"] is None
        assert data["str_cash_on_cash_pct"] is None
        assert data["str_projection_3yr"] is None

    def test_with_str_params_returns_str_fields(
        self,
        api_client: TestClient,
        db_session: Session,
        seeded_property: PropertyListing,
    ) -> None:
        """When nightly_rate is supplied, STR fields are populated."""
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            f"/api/v1/analytics/wholesale/{pid}",
            params={
                "nightly_rate": 150.0,
                "occupancy_pct": 0.70,
                "monthly_maintenance": 300.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # STR fields should now be populated (not None)
        assert data["str_monthly_gross"] is not None
        assert data["str_monthly_gross"] > 0
        assert data["str_pm_cost"] is not None
        assert data["str_monthly_net"] is not None
        assert data["str_annual_noi"] is not None
        assert data["str_cash_on_cash_pct"] is not None
        assert data["str_projection_6mo"] is not None
        assert data["str_projection_1yr"] is not None
        assert data["str_projection_3yr"] is not None

    def test_nightly_rate_only_uses_defaults(
        self,
        api_client: TestClient,
        db_session: Session,
        seeded_property: PropertyListing,
    ) -> None:
        """When only nightly_rate is supplied, occupancy defaults to 0.70, maintenance to 0."""
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            f"/api/v1/analytics/wholesale/{pid}",
            params={"nightly_rate": 100.0},
        )

        assert response.status_code == 200
        data = response.json()
        # monthly_gross should reflect 70% occupancy default
        # gross = 100 × 30 × 0.70 = 2100
        assert data["str_monthly_gross"] == 2100.0

    def test_negative_nightly_rate_rejected(
        self,
        api_client: TestClient,
    ) -> None:
        """Negative nightly_rate should be rejected by Pydantic validation (ge=0)."""
        response = api_client.get(
            "/api/v1/analytics/wholesale/fake-id",
            params={"nightly_rate": -50.0},
        )

        assert response.status_code == 422

    def test_occupancy_above_one_rejected(
        self,
        api_client: TestClient,
    ) -> None:
        """Occupancy > 1.0 should be rejected by validation (le=1.0)."""
        response = api_client.get(
            "/api/v1/analytics/wholesale/fake-id",
            params={"nightly_rate": 100.0, "occupancy_pct": 1.5},
        )

        assert response.status_code == 422

    def test_recommended_str_assumptions_populated(
        self,
        api_client: TestClient,
        seeded_property: PropertyListing,
    ) -> None:
        """Endpoint always returns recommended STR assumptions based on location/size."""
        pid = quote(seeded_property.id, safe="")
        response = api_client.get(
            f"/api/v1/analytics/wholesale/{pid}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "recommended_str_assumptions" in data
        rec = data["recommended_str_assumptions"]
        assert "nightly_rate" in rec
        assert "occupancy_pct" in rec
        assert "monthly_maintenance" in rec
        # For seeded_property (Piantini, Santo Domingo, square_meters=142.0)
        assert rec["nightly_rate"] == 80.0
        assert rec["occupancy_pct"] == 0.40
        assert rec["monthly_maintenance"] == 142.0 * 2.50 # 355.0


class TestStrDefaultPredictor:
    """Verify that StrDefaultPredictor resolves correct DR market assumptions."""

    def test_predictor_punta_cana(self) -> None:
        """Punta Cana / Altagracia keywords yield $169 ADR and 45% occupancy."""
        res = StrDefaultPredictor.predict_defaults(100.0, "La Altagracia", "Punta Cana")
        assert res["nightly_rate"] == 169.0
        assert res["occupancy_pct"] == 0.45
        assert res["monthly_maintenance"] == 250.0  # 100 * 2.50

    def test_predictor_las_terrenas(self) -> None:
        """Las Terrenas / Samana keywords yield $234 ADR and 40% occupancy."""
        res = StrDefaultPredictor.predict_defaults(80.0, "Samaná", "Las Terrenas")
        assert res["nightly_rate"] == 234.0
        assert res["occupancy_pct"] == 0.40
        assert res["monthly_maintenance"] == 200.0  # 80 * 2.50

    def test_predictor_santo_domingo(self) -> None:
        """Santo Domingo yields $80 ADR and 40% occupancy."""
        res = StrDefaultPredictor.predict_defaults(120.0, "Santo Domingo", "Piantini")
        assert res["nightly_rate"] == 80.0
        assert res["occupancy_pct"] == 0.40
        assert res["monthly_maintenance"] == 300.0  # 120 * 2.50

    def test_predictor_fallback(self) -> None:
        """Other locations yield fallback $120 ADR and 40% occupancy."""
        res = StrDefaultPredictor.predict_defaults(None, "Santiago", "Cerros de Gurabo")
        assert res["nightly_rate"] == 120.0
        assert res["occupancy_pct"] == 0.40
        assert res["monthly_maintenance"] == 150.0  # fallback when size is None

    def test_predictor_zero_or_negative_size(self) -> None:
        """Zero or negative size yields fallback maintenance of $150."""
        res = StrDefaultPredictor.predict_defaults(0.0, "Punta Cana")
        assert res["monthly_maintenance"] == 150.0

        res2 = StrDefaultPredictor.predict_defaults(-5.0, "Punta Cana")
        assert res2["monthly_maintenance"] == 150.0
