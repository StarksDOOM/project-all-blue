"""
High-density test matrix for STREAM 5 PHASE 5.1: Tenant Operational Tier Limits
& Administrative Execution Overrides.

Validates:
- TierLimitEvaluator enforcement on POST /api/v1/saved-searches via the saved_searches router
  (client=3, agent=25, admin=unlimited via sys.maxsize).
- New admin-only POST /api/v1/scrapers/run guarded by RoleChecker([UserRole.ADMIN]).
- 202 Accepted + execution receipt on success for admin.
- 403 Forbidden for client/agent on the scraper endpoint.
- Background task registration (via mock; no actual sync executed).
- All using locally-minted HS256 JWTs only (conftest SUPABASE_JWT_SECRET + _mint_test_jwt).
- Zero external network / live Supabase / Resend / DocuSign / portal calls.

This file brings the total assertion count above the Phase 5.0 baseline of 63 while
preserving zero regressions on all prior tests.

See tier-limits-admin-overrides.spec.md for the exact matrix and contracts.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from main import app
from models import SavedSearchAlert
from services.sync_service import IngestionOrchestrator

# Must match the secret set by _auth_env autouse fixture in conftest.py (Phase 5.0 RBAC).
TEST_JWT_SECRET = "test-secret-for-rbac-phase5-only-do-not-use-in-prod"


def _mint_test_jwt(
    user_id: str = "11111111-1111-1111-1111-111111111111",
    role: str = "client",
) -> str:
    """
    Mint a minimal valid HS256 JWT for test client calls.

    Purpose:
        Provide authenticated requests to protected endpoints without any
        outbound call to Supabase or external IdP. Uses the test secret so that
        the in-process JWTTokenVerifier succeeds.

    Lifecycle:
        Called inside individual test functions; produces a fresh expiring token
        each time.

    Thread-safety:
        Pure function; safe for concurrent test collection if pytest xdist used.

    Collaborators:
        - jwt (PyJWT)
        - TEST_JWT_SECRET (matches conftest monkeypatch)
        - api_client / TestClient (carries the Bearer header)

    Invariants:
        - 'sub' claim becomes user_id for tenant scoping.
        - 'app_metadata.role' is used by JWTTokenVerifier to resolve UserRole.
        - exp is 1h in future; iat now.

    Parameters:
        user_id (str): The 'sub' for tenant isolation in queries/limits.
        role (str): One of 'client' | 'agent' | 'admin' (string for payload).

    Returns:
        str: Signed compact JWT.

    Raises:
        None (jwt.encode failures would be test env problems).

    Side Effects:
        None (stateless).
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": f"{user_id[:8]}@example.com",
        "app_metadata": {"role": role},
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _count_active_for_user(db_session: Session, user_id: str) -> int:
    """Helper count for assertions (mirrors the evaluator query)."""
    stmt = select(SavedSearchAlert).where(
        SavedSearchAlert.user_id == user_id,
        SavedSearchAlert.is_active == True,
    )
    return len(db_session.exec(stmt).all())


def test_client_blocked_at_3_when_already_has_3(db_session: Session, api_client: TestClient):
    """
    Client role: pre-populate 3 active searches for a fresh user -> 4th create returns 400.
    """
    uid = "limit-test-client-3"
    token = _mint_test_jwt(user_id=uid, role="client")
    headers = {"Authorization": f"Bearer {token}"}

    # Clean any rows for this uid left by prior test runs (shared DB + committed inserts from previous executions)
    from database import engine
    from sqlmodel import Session as SMSession
    with SMSession(engine) as s:
        for e in s.exec(select(SavedSearchAlert).where(SavedSearchAlert.user_id == uid)).all():
            s.delete(e)
        s.commit()

    # Pre-populate exactly 3 (committed so count query in evaluator sees them)
    for i in range(3):
        alert = SavedSearchAlert(
            user_id=uid,
            title=f"Client Cap {i}",
            filters_json={"sector": "Piantini"},
            is_active=True,
        )
        db_session.add(alert)
    db_session.commit()

    assert _count_active_for_user(db_session, uid) == 3

    payload = {
        "user_id": uid,  # server overrides from token (Phase 5.0); schema still requires the field
        "title": "4th should fail",
        "filters": {"sector": "Piantini", "bedrooms_min": 1},
    }
    r = api_client.post("/api/v1/saved-searches", json=payload, headers=headers)
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "maximum of 3" in detail
    assert "client" in detail


def test_agent_passes_3_threshold_but_blocked_at_25(db_session: Session, api_client: TestClient):
    """
    Agent role: successfully creates when crossing the client threshold (e.g. at 25),
    but is blocked when hitting the agent cap of 25.
    """
    uid = "limit-test-agent-25"
    token = _mint_test_jwt(user_id=uid, role="agent")
    headers = {"Authorization": f"Bearer {token}"}

    # Clean any rows for this uid left by prior test runs (shared DB + committed inserts from previous executions)
    from database import engine
    from sqlmodel import Session as SMSession
    with SMSession(engine) as s:
        for e in s.exec(select(SavedSearchAlert).where(SavedSearchAlert.user_id == uid)).all():
            s.delete(e)
        s.commit()

    # Pre-populate 24 (agent can go to 25)
    for i in range(24):
        alert = SavedSearchAlert(
            user_id=uid,
            title=f"Agent Pre {i}",
            filters_json={"sector": "Piantini"},
            is_active=True,
        )
        db_session.add(alert)
    db_session.commit()
    assert _count_active_for_user(db_session, uid) == 24

    # 25th via the API path (exercises evaluator) -> must succeed (passes 3 easily)
    payload_ok = {
        "user_id": uid,
        "title": "Agent reaches 25",
        "filters": {"sector": "Piantini"},
    }
    r_ok = api_client.post("/api/v1/saved-searches", json=payload_ok, headers=headers)
    assert r_ok.status_code == 201
    assert _count_active_for_user(db_session, uid) == 25

    # At cap (25): the next create attempt must be rejected with the agent limit message.
    payload_block = {
        "user_id": uid,
        "title": "Agent 26th blocked",
        "filters": {"sector": "Piantini"},
    }
    r_block = api_client.post("/api/v1/saved-searches", json=payload_block, headers=headers)
    assert r_block.status_code == 400
    detail = r_block.json().get("detail", "")
    assert "maximum of 25" in detail
    assert "agent" in detail


def test_admin_unlimited_past_all_thresholds(db_session: Session, api_client: TestClient):
    """
    Admin role: can create many more than 25 (or 3) without restriction.
    """
    uid = "limit-test-admin-unlim"
    token = _mint_test_jwt(user_id=uid, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    # Clean any rows for this uid left by prior test runs (shared DB + committed inserts from previous executions)
    from database import engine
    from sqlmodel import Session as SMSession
    with SMSession(engine) as s:
        for e in s.exec(select(SavedSearchAlert).where(SavedSearchAlert.user_id == uid)).all():
            s.delete(e)
        s.commit()

    # Pre-populate a high number (past both client and agent caps)
    for i in range(30):
        alert = SavedSearchAlert(
            user_id=uid,
            title=f"Admin Bulk {i}",
            filters_json={"sector": "Piantini"},
            is_active=True,
        )
        db_session.add(alert)
    db_session.commit()
    assert _count_active_for_user(db_session, uid) == 30

    # Still allowed
    payload = {
        "user_id": uid,
        "title": "Admin 31st",
        "filters": {"sector": "Piantini", "price_max": 999999},
    }
    r = api_client.post("/api/v1/saved-searches", json=payload, headers=headers)
    assert r.status_code == 201
    assert _count_active_for_user(db_session, uid) == 31


def test_scraper_run_202_for_admin_and_registers_background_task(api_client: TestClient):
    """
    Admin token on /api/v1/scrapers/run returns 202 + receipt and calls add_task exactly once.
    """
    admin_token = _mint_test_jwt(user_id="admin-override-1", role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
        r = api_client.post("/api/v1/scrapers/run", headers=headers)
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "accepted"
        assert "initiated_at" in body and body["initiated_at"]
        assert body["task"] == "ingestion_sync_remaxrd"
        assert "background task" in body["message"].lower()

        mock_add_task.assert_called_once()
        # Verify the callable and portal arg were passed to add_task
        called_args = mock_add_task.call_args[0]
        assert called_args[0] == IngestionOrchestrator.trigger_sync_cycle
        assert called_args[1] == "remaxrd"


def test_scraper_run_403_for_client_token(api_client: TestClient):
    """Non-admin (client) immediately rejected with 403 on the admin override endpoint."""
    client_token = _mint_test_jwt(user_id="client-no-scrape", role="client")
    headers = {"Authorization": f"Bearer {client_token}"}
    r = api_client.post("/api/v1/scrapers/run", headers=headers)
    assert r.status_code == 403


def test_scraper_run_403_for_agent_token(api_client: TestClient):
    """Non-admin (agent) immediately rejected with 403 on the admin override endpoint."""
    agent_token = _mint_test_jwt(user_id="agent-no-scrape", role="agent")
    headers = {"Authorization": f"Bearer {agent_token}"}
    r = api_client.post("/api/v1/scrapers/run", headers=headers)
    assert r.status_code == 403
