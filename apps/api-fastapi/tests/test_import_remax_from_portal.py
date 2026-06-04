"""Import-on-read for RE/MAX listings not yet in Postgres."""

from unittest.mock import patch

from sqlmodel import Session, select

from database import engine, init_db
from models import PropertyListing
from services.remax_detail_enrichment import import_remax_listing_from_portal
from tests.db_cleanup import delete_property_cascade

SAMPLE_DETAIL = {
    "property_id": "222598",
    "title": "Casa en Nisibon",
    "price": "150000.00",
    "currency": "USD",
    "scrape_url": "https://www.remaxrd.com/propiedad/casa-vendo-casa-de-oportunidad-en-nisibon-222598?city=higuey",
    "description_text": "Gran oportunidad en Nisibon.",
    "specs": {
        "bedrooms": 3,
        "bathrooms": 3,
        "half_bathrooms": 0,
        "sqm_construction": 165,
        "sector": "LA CEIBA",
        "city": "HIGUEY",
        "business_type": "Venta",
        "realstate_type": "Casa",
        "status": "Disponible",
    },
}


@patch(
    "services.remax_detail_enrichment.scrape_remax_property_detail",
    return_value=SAMPLE_DETAIL,
)
@patch(
    "services.remax_detail_enrichment.resolve_remax_portal_url",
    return_value=SAMPLE_DETAIL["scrape_url"],
)
def test_import_creates_row_when_missing(mock_url, mock_scrape) -> None:
    init_db()
    portal_url = SAMPLE_DETAIL["scrape_url"]
    with Session(engine) as session:
        existing = session.exec(
            select(PropertyListing).where(PropertyListing.remote_id == "222598")
        ).first()
        if existing:
            delete_property_cascade(session, property_id=existing.id)

        row = import_remax_listing_from_portal(session, "222598", portal_url=portal_url)
        assert row.title == "Casa en Nisibon"
        assert row.price_usd == 150000.0
        assert row.bedrooms == 3
        assert "Gran oportunidad" in row.raw_description
        assert "higuey" in row.url or "hig" in row.url

        session.delete(row)
        session.commit()