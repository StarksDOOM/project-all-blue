"""Bathroom count fallback from RE/MAX description prose."""

from models import PropertyListing
from scrapers.utils.normalization import (
    hydrate_listing_bathrooms,
    parse_bathrooms_from_text,
    resolve_bathroom_count,
    resolve_bathroom_count_from_specs,
)
from services.remax_detail_enrichment import apply_detail_payload_to_listing


def test_parse_bathrooms_from_spanish_complete_phrase() -> None:
    text = "<p>La casa cuenta con 3 baños completos y cocina amplia.</p>"
    assert parse_bathrooms_from_text(text) == 3.0


def test_parse_bathrooms_from_full_and_half_phrase() -> None:
    text = "1 habitación, 1 baño completo y 1 medio baño, cocina integrada."
    assert parse_bathrooms_from_text(text) == 1.5


def test_resolve_bathroom_count_prefers_structured_fields() -> None:
    assert resolve_bathroom_count(2, 1, "5 baños completos") == 2.5


def test_resolve_bathroom_count_falls_back_to_description() -> None:
    assert (
        resolve_bathroom_count(0, 0, "Apartamento con 2 baños completos en zona premium.")
        == 2.0
    )


def test_resolve_from_specs_uses_bathroom_count_without_double_half() -> None:
    total = resolve_bathroom_count_from_specs(
        {"bathroom_count": 3, "bathrooms": 3, "half_bathrooms": 1},
        description_text="ignored 9 baños",
    )
    assert total == 3.0


def test_hydrate_listing_from_raw_description() -> None:
    listing = PropertyListing(
        remote_id="888002",
        source_portal="remaxrd",
        url="https://example.test/888002",
        title="Test",
        price_usd=1.0,
        province="SD",
        sector="Test",
        bedrooms=0,
        bathrooms=0.0,
        square_meters=0.0,
        raw_description="currency=USD | 2 baños completos en suite",
        is_active=True,
    )
    hydrate_listing_bathrooms(listing)
    assert listing.bathrooms == 2.0


def test_apply_detail_sets_bathrooms_from_description_when_specs_empty() -> None:
    listing = PropertyListing(
        remote_id="888001",
        source_portal="remaxrd",
        url="https://www.remaxrd.com/propiedad/redirected/888001",
        title="Local comercial",
        price_usd=100_000.0,
        price_dop=None,
        province="Santo Domingo",
        sector="Piantini",
        bedrooms=0,
        bathrooms=0.0,
        square_meters=0.0,
        raw_description="currency=USD",
        is_active=True,
    )
    detail = {
        "property_id": "888001",
        "title": "Local comercial",
        "price": "100000",
        "currency": "USD",
        "description_text": "Excelente local con 2 baños completos y mezzanine.",
        "specs": {
            "bathroom_count": 0,
            "bathrooms": 0,
            "half_bathrooms": 0,
            "bedrooms": 0,
        },
    }

    apply_detail_payload_to_listing(listing, detail)

    assert listing.bathrooms == 2.0