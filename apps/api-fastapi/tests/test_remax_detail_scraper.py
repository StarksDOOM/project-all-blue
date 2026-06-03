"""Unit tests for RE/MAX detail scraper (offline fixtures + mocked HTTP)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from scrapers.remax_detail_scraper import (
    _find_property_in_next_data,
    _parse_next_data,
    _record_to_detail,
    extract_remote_id_from_url,
    normalize_remax_listing_url,
    scrape_remax_property_detail,
)

SAMPLE_NEXT_HTML = """
<html><body>
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"data":{"data":{"id":222598,"name":"Casa LA CEIBA","price":"150000.00","currency":{"iso":"USD"},"bedrooms":3,"bathrooms":3,"half_bathrooms":0,"sqm_construction":165,"pictures":[{"pictures":"https://images.remaxrd.com/media/pictures/watermark/big/a.jpg"}],"agents":[{"name":"Jane Agent","mobile":"8095551234"}],"description":"<p>Gran oportunidad</p>"}}}}}
</script>
<p>Código: 222598</p>
<a href="tel:+18095551234">Call</a>
<a href="https://wa.me/18095551234">WhatsApp</a>
</body></html>
"""

SAMPLE_API_RECORD = {
    "id": 222574,
    "slug": "apartamento-en-alquiler-en-la-esperilla-222574",
    "name": "Apartamento en La Esperilla",
    "price": "900.00",
    "currency": {"iso": "USD"},
    "bedrooms": 1,
    "bathrooms": 1,
    "half_bathrooms": 1,
    "sqm_construction": 65,
    "pictures": [{"pictures": "https://images.remaxrd.com/media/pictures/watermark/big/x.jpg"}],
    "agents": [{"name": "Alicia Rodríguez", "phone": "8095321844"}],
    "description": "<p>Amplio apartamento</p>",
}


def test_extract_remote_id_from_url() -> None:
    url = "https://www.remaxrd.com/en/propiedad/apartamento-en-alquiler-en-la-esperilla-222574"
    assert extract_remote_id_from_url(url) == "222574"


def test_normalize_remax_listing_url_strips_en_and_adds_city() -> None:
    url = "https://www.remaxrd.com/en/propiedad/foo-222598"
    out = normalize_remax_listing_url(url, city_slug="higüey")
    assert "/en/" not in out
    assert "/propiedad/foo-222598" in out
    assert "city=hig" in out or "city=hig%C3%BCey" in out


def test_parse_next_data_finds_property() -> None:
    payload = _parse_next_data(SAMPLE_NEXT_HTML)
    assert payload is not None
    record = _find_property_in_next_data(payload)
    assert record is not None
    assert record["id"] == 222598


def test_record_to_detail_shape() -> None:
    detail = _record_to_detail(
        SAMPLE_API_RECORD,
        source="test",
        scrape_url="https://example.test",
    )
    assert detail["property_id"] == "222574"
    assert detail["title"] == "Apartamento en La Esperilla"
    assert detail["agent_name"] == "Alicia Rodríguez"
    assert len(detail["image_list"]) == 1
    assert "Amplio apartamento" in (detail["description_text"] or "")


@patch("scrapers.remax_detail_scraper._fetch_html", return_value=SAMPLE_NEXT_HTML)
def test_scrape_prefers_next_data(mock_html) -> None:
    detail = scrape_remax_property_detail(
        "https://www.remaxrd.com/propiedad/casa-vendo-222598?city=higüey"
    )
    assert detail["source"] == "next_data"
    assert detail["property_id"] == "222598"
    assert detail["title"] == "Casa LA CEIBA"
    mock_html.assert_called_once()


@patch("scrapers.remax_detail_scraper._fetch_html", return_value="<html><body><p>Código: 999001</p></body></html>")
@patch("scrapers.remax_detail_scraper._parse_next_data", return_value=None)
@patch("scrapers.remax_detail_scraper._fetch_api_detail", return_value=SAMPLE_API_RECORD)
def test_scrape_falls_back_to_api(mock_api, mock_next, mock_html) -> None:
    detail = scrape_remax_property_detail("https://www.remaxrd.com/propiedad/x-999001")
    assert detail["source"] == "remax_api"
    assert detail["property_id"] == "222574"
    mock_api.assert_called_once()