"""Phase 7 SSE broadcaster and transaction stream endpoint."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from services.realtime_broadcaster import RealtimeBroadcaster, broadcaster, format_sse_message
from tests.db_cleanup import delete_transaction_cascade


def test_broadcaster_publish_delivers_to_subscriber() -> None:
    async def _run() -> None:
        local = RealtimeBroadcaster()
        queue = await local.subscribe("txn-1")
        delivered = await local.publish(
            "txn-1",
            {"event": "TRANSACTION_UPDATED", "transaction_id": "txn-1", "status": "EXECUTED"},
        )
        assert delivered == 1
        payload = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert payload["event"] == "TRANSACTION_UPDATED"
        await local.unsubscribe("txn-1", queue)

    asyncio.run(_run())


def test_format_sse_message() -> None:
    frame = format_sse_message({"event": "CONNECTED"}, event="connected")
    assert "event: connected" in frame
    assert "data:" in frame
    assert frame.endswith("\n\n")


def test_stream_endpoint_requires_existing_transaction(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/transactions/nonexistent-txn/stream")
    assert response.status_code == 404


def test_stream_route_registered(api_client: TestClient) -> None:
    paths = {route.path for route in api_client.app.routes}
    assert "/api/v1/transactions/{transaction_id}/stream" in paths


def test_process_wide_broadcaster_singleton() -> None:
    assert broadcaster is not None