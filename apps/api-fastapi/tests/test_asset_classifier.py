"""Unit tests for the Asset Classifier service.

STREAM 6 PHASE 1.8.
"""

from __future__ import annotations

import unittest
from models import PropertyListing
from services.asset_classifier import AssetClassifier


class TestAssetClassifier(unittest.TestCase):
    """Test suite for validating NLP classifier keyword matches on listings."""

    def test_default_classification(self) -> None:
        """Verify that a listing with no triggers defaults to SALE and RESIDENTIAL."""
        listing = PropertyListing(
            id="#TEST-1",
            remote_id="r-1",
            source_portal="remaxrd",
            url="https://example.test/1",
            title="Hermosa Casa en Arroyo Hondo",
            price_usd=150000.0,
            province="Santo Domingo",
            sector="Arroyo Hondo",
            bedrooms=3,
            bathrooms=2.5,
            square_meters=200.0,
            raw_description="Bella casa familiar en zona residencial tranquila.",
            is_active=True,
        )
        AssetClassifier.classify_property_listing(listing)
        self.assertEqual(listing.listing_type, "FOR_SALE")
        self.assertEqual(listing.property_type, "RESIDENTIAL")

    def test_listing_type_rent_triggers(self) -> None:
        """Verify that rental keyword triggers classify the listing as FOR_RENT."""
        triggers = ["alquiler", "renta", "for rent", "se alquila"]
        for kw in triggers:
            listing = PropertyListing(
                id="#TEST-RENT",
                remote_id="r-rent",
                source_portal="remaxrd",
                url="https://example.test/rent",
                title=f"Propiedad en {kw} hoy",
                price_usd=1500.0,
                province="Santo Domingo",
                sector="Evaristo Morales",
                bedrooms=2,
                bathrooms=2.0,
                square_meters=100.0,
                raw_description="Standard details",
                is_active=True,
            )
            AssetClassifier.classify_property_listing(listing)
            self.assertEqual(listing.listing_type, "FOR_RENT", f"Failed on keyword: {kw}")

    def test_property_type_commercial_triggers(self) -> None:
        """Verify that commercial keywords classify the property as COMMERCIAL."""
        triggers = [
            "local comercial",
            "nave industrial",
            "plaza",
            "oficina",
            "edificio corporativo",
        ]
        for kw in triggers:
            listing = PropertyListing(
                id="#TEST-COMM",
                remote_id="r-comm",
                source_portal="remaxrd",
                url="https://example.test/comm",
                title="Grandes espacios",
                price_usd=350000.0,
                province="Santo Domingo",
                sector="Piantini",
                bedrooms=0,
                bathrooms=4.0,
                square_meters=350.0,
                raw_description=f"Se vende {kw} con excelente ubicación.",
                is_active=True,
            )
            AssetClassifier.classify_property_listing(listing)
            self.assertEqual(listing.property_type, "COMMERCIAL", f"Failed on keyword: {kw}")

    def test_case_insensitivity(self) -> None:
        """Verify that triggers are scanned case-insensitively."""
        listing = PropertyListing(
            id="#TEST-CASE",
            remote_id="r-case",
            source_portal="remaxrd",
            url="https://example.test/case",
            title="LOCAL COMERCIAL y ALQUILER de oficina",
            price_usd=2500.0,
            province="Santo Domingo",
            sector="Naco",
            bedrooms=1,
            bathrooms=1.5,
            square_meters=80.0,
            raw_description="SE ALQUILA excelente nave industrial en zona premium.",
            is_active=True,
        )
        AssetClassifier.classify_property_listing(listing)
        self.assertEqual(listing.listing_type, "FOR_RENT")
        self.assertEqual(listing.property_type, "COMMERCIAL")
