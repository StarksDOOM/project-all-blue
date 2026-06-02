"""
Spec-kit verification gates V1, V3, V4, V5 (see ingestion-oop.spec.md §9).

V1 — implied if this script imports app + routers
V3 — POST remaxrd → 202 (sync mocked — no AdsPower)
V4 — POST realtor → 501
V5 — POST unknown portal → 400

Full E2E (V2, V6, V7): python crawl_test.py --portal remaxrd
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Allow `from main import app` when executed as scripts/verify_ingestion_v1_v7.py
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from main import app
from services.sync_service import IngestionOrchestrator


def main() -> int:
    """Run HTTP contract checks; return 0 on success, 1 on failure."""
    print("V1: import smoke already passed if this script runs")
    client = TestClient(app)

    # Starlette runs background tasks inline — mock to avoid 90s+ real crawl during CI.
    with patch.object(
        IngestionOrchestrator,
        "run_sync_for_portal",
        return_value={"status": "COMPLETED"},
    ):
        r3 = client.post(
            "/api/v1/properties/trigger-crawl",
            params={"source_portal": "remaxrd"},
        )
    print(f"V3 remaxrd: {r3.status_code} {r3.json()}")
    if r3.status_code != 202:
        return 1

    r4 = client.post(
        "/api/v1/properties/trigger-crawl",
        params={"source_portal": "realtor"},
    )
    print(f"V4 realtor: {r4.status_code} {r4.json()}")
    if r4.status_code != 501:
        return 1

    r5 = client.post(
        "/api/v1/properties/trigger-crawl",
        params={"source_portal": "foo"},
    )
    print(f"V5 foo: {r5.status_code} {r5.json()}")
    if r5.status_code != 400:
        return 1

    print("V3-V5 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())