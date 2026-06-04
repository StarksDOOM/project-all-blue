"""Scraper error telemetry — context manager, persistence, admin API."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import ScraperErrorLog
from observability.scraper_errors import persist_scraper_error_record, scraper_error_scope


def test_scraper_error_scope_persists_row(db_session: Session) -> None:
    """Parse failures inside swallow=True scope write ScraperErrorLog without raising."""
    with scraper_error_scope(
        "json",
        remote_id="222598",
        url="https://www.remaxrd.com/propiedad/redirected/222598",
        session=db_session,
        swallow=True,
        reraise=False,
    ):
        raise KeyError("missing baths key")

    row = db_session.exec(
        select(ScraperErrorLog).where(ScraperErrorLog.remote_id == "222598")
    ).first()
    assert row is not None
    assert row.scraper_method == "json"
    assert row.error_type == "KeyError"
    assert row.resolved is False
    assert "missing baths key" in row.stack_trace


def test_persist_scraper_error_record_uses_custom_sink() -> None:
    """Swapping the sink avoids DB writes (Sentry / Datadog path)."""
    captured: list[dict] = []

    def _sink(**kwargs: object) -> None:
        captured.append(kwargs)

    with patch("observability.scraper_errors._error_sink", _sink):
        persist_scraper_error_record(
            scraper_method="dom",
            error_type="AttributeError",
            stack_trace="trace",
            remote_id="1",
            url="https://example.test",
        )

    assert len(captured) == 1
    assert captured[0]["scraper_method"] == "dom"


def test_admin_list_unresolved_scraper_errors(
    api_client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(
        ScraperErrorLog(
            remote_id="999001",
            url="https://example.test/999001",
            scraper_method="json",
            error_type="ValueError",
            stack_trace="test stack",
            resolved=False,
        )
    )
    db_session.add(
        ScraperErrorLog(
            remote_id="999002",
            url="https://example.test/999002",
            scraper_method="dom",
            error_type="RuntimeError",
            stack_trace="resolved stack",
            resolved=True,
        )
    )
    db_session.flush()

    response = api_client.get("/api/admin/scraper-errors?resolved=false&limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    remote_ids = {row["remote_id"] for row in body["data"]}
    assert "999001" in remote_ids
    assert "999002" not in remote_ids


def test_property_detail_includes_portal_refresh_flags(
    api_client: TestClient,
    seeded_property,
) -> None:
    with patch(
        "routers.properties.enrich_remax_listing",
        side_effect=RuntimeError("portal down"),
    ):
        response = api_client.get(
            f"/api/v1/properties/{seeded_property.remote_id}?refresh_from_portal=true"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["portal_refresh_failed"] is True
    assert "last known data" in (body.get("portal_refresh_message") or "").lower()
    assert body["remote_id"] == seeded_property.remote_id