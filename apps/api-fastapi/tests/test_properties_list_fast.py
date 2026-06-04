"""Fast list pagination (include_total=false)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_properties_fast_page_skips_total(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/properties",
        params={
            "page": 2,
            "limit": 5,
            "source_portal": "remaxrd",
            "include_total": "false",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["total"] is None
    assert body["metadata"]["pages"] is None
    assert "has_next" in body["metadata"]
    assert len(body["data"]) <= 5