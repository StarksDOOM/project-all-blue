"""Tests for RE/MAX URL detail enrichment → PropertyListing merge."""

from models import PropertyListing
from scrapers.utils.normalization import resolve_prices_usd_dop, safe_float
from services.remax_detail_enrichment import apply_detail_payload_to_listing


def _base_listing() -> PropertyListing:
    return PropertyListing(
        remote_id="222574",
        source_portal="remaxrd",
        url="https://www.remaxrd.com/en/propiedad/apartamento-222574",
        title="Apartamento (alquiler) en La Esperilla",
        price_usd=15.0,
        price_dop=None,
        province="Santo Domingo",
        sector="La Esperilla",
        bedrooms=0,
        bathrooms=0.0,
        square_meters=0.0,
        raw_description="currency=USD|alquiler",
        is_active=True,
    )


def test_apply_detail_uses_portal_api_price_and_currency_from_payload() -> None:
    listing = _base_listing()
    detail = {
        "property_id": "222574",
        "title": "Apartamento en La Esperilla",
        "price": "900.00",
        "currency": "USD",
        "scrape_url": "https://www.remaxrd.com/propiedad/apartamento-en-alquiler-en-la-esperilla-222574?city=santo-domingo",
        "description_text": "Amplio apartamento con vista.",
        "agent_name": "Alicia Rodríguez",
        "agent_phone": "8095321844",
        "agent_email": "agent@test.com",
        "agent_agency": "REMAX Test",
        "whatsapp_link": "https://wa.me/18095551234",
        "image_list": ["https://images.remaxrd.com/a.jpg", "https://images.remaxrd.com/b.jpg"],
        "specs": {
            "bedrooms": 1,
            "bathrooms": 1,
            "half_bathrooms": 1,
            "sqm_construction": 65,
            "sqm_land": 80,
            "sector": "La Esperilla",
            "city": "Santo Domingo De Guzman",
            "business_type": "alquiler",
            "realstate_type": "Apartamento",
            "status": "disponible",
        },
    }

    portal_price = safe_float(detail["price"])
    portal_currency = str(detail["currency"]).upper()
    expected_usd, expected_dop = resolve_prices_usd_dop(detail["price"], portal_currency)

    apply_detail_payload_to_listing(listing, detail)

    assert listing.title == detail["title"]
    assert listing.list_price == portal_price
    assert listing.listing_currency == portal_currency
    assert listing.price_usd == expected_usd
    if expected_dop is not None:
        assert listing.price_dop == expected_dop
    assert listing.bedrooms == 1
    assert listing.bathrooms == 1.5
    assert listing.square_meters == 65
    assert listing.sqm_land == 80
    assert listing.agent_name == detail["agent_name"]
    assert listing.agent_phone == detail["agent_phone"]
    assert listing.image_urls is not None and len(listing.image_urls) == len(detail["image_list"])
    assert "business_type=alquiler" in listing.raw_description
    assert detail["description_text"] in listing.raw_description
    assert f"currency={portal_currency}" in listing.raw_description
    assert "/propiedad/redirected/222574" in listing.url