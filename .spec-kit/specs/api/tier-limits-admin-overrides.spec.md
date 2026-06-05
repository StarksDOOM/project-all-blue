# Spec: Tenant Operational Tier Limits & Administrative Execution Overrides

## Status: DRAFT
**Roadmap:** STREAM 5 PHASE 5.1  
**Branch:** `feat/stream-5-phase-5.1-tier-limits-admin-overrides` ← `develop`  
**Apps:** `apps/api-fastapi/`  
**Feature README:** `docs/features/tier-limits-admin-overrides/README.md`

**CRG Framework Baseline Note (per monitoring directive):** Post-Phase 5.0: 11 core single-responsibility abstractions. This phase adds 'TierLimitEvaluator' (the 12th; confirmed via code-review-graph query_graph_tool file_summary + node id). Implementation complete: 69 tests passed 0 failures (63 legacy preserved + 6 new in test_tier_limits_overrides.py). All commits followed pre-pytest + git status --porcelain gates + CRG update. Status remains DRAFT pending explicit user "Manual Success" assertion (per spec-kit rules). No creep; new class is stateless, single-responsibility.

---

## 1. Objective

Enforce operational capacity thresholds (max active SavedSearches) on users based on their RBAC tier (client/agent/admin) at the point of creation (POST /api/v1/saved-searches). Expose a strictly admin-protected administrative endpoint to trigger on-demand scraping jobs via BackgroundTasks, allowing overrides of normal scheduled ingestion without exposing it to non-admins.

This builds directly on Phase 5.0 RBAC without regressing any existing isolation or test coverage.

**In scope**
- 'TierLimitEvaluator' class with assert_can_create_search enforcing the exact matrices (client=3, agent=25, admin=unlimited via sys.maxsize).
- Integration into the existing saved_searches router POST (after auth/role check, before creation).
- New protected admin route POST /api/v1/scrapers/run (or equivalent) guarded by RoleChecker([UserRole.ADMIN]), using BackgroundTasks to invoke IngestionOrchestrator logic, returning 202 Accepted with receipt.
- Full PEP 257 OOP docstrings on all new code.
- High-density tests in new test file using only local JWT mocks (no live networks).
- Safe additive changes only; preserve all 63 existing tests at 0 failures.
- CRG monitoring and atomic small commits with pre-commit pytest + git status.
- Update spec, index, feature README before any code.

**Out of scope**
- Changes to limits enforcement on other operations (e.g. updates).
- UI for tier display or admin controls (backend only for this phase).
- Modifying IngestionOrchestrator itself (assume trigger_sync_cycle or equivalent exists or is called appropriately).
- Full RLS at DB layer (app-level enforcement is sufficient here).
- Rate limiting beyond the per-user search caps.

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| POST | /api/v1/saved-searches | Now additionally enforces tier limit via TierLimitEvaluator after RoleChecker but before DB write. Returns 400 if over limit for role. |
| POST | /api/v1/scrapers/run | Admin-only (403 otherwise). Triggers background scrape. Returns 202 Accepted with { "status": "accepted", "initiated_at": "...", "task": "..." } |

**Models / tables:** No new models. Uses existing SavedSearchAlert (count active per user_id + role from credentials).

**Class interfaces (strict OOP + full PEP 257 required):**
- class TierLimitEvaluator: __init__(self, session: Session). assert_can_create_search(self, user_id: str, role: UserRole) -> None. Performs count query on SavedSearchAlert where user_id == ... and is_active. Compares against matrix. Raises HTTPException(400) on breach.

**Capacity matrices (enforced on create):**
- client: <= 3 active SavedSearch
- agent: <= 25 active SavedSearch
- admin: unlimited (sys.maxsize)

**Admin route details:**
- Guard: Depends(RoleChecker([UserRole.ADMIN]))
- Execution: background_tasks.add_task(IngestionOrchestrator... or equivalent trigger)
- Immediate 202 response.

---

## 3. Storefront (if applicable)
- None for this phase (backend infrastructure only; frontend can call admin endpoint if token has admin role, but no new UI/components required).

---

## 4. Security & boundaries
- Server-side: RoleChecker already in place from 5.0; additional limit check inside transaction boundary.
- Tenant isolation: still enforced via user_id from credentials (limits are per-user).
- No privilege escalation: admin route strictly checked.
- Error messages: generic for limits (do not leak counts of other users).
- No network creep in tests or new logic beyond existing.
- Auth (current): fully implemented in 5.0; this extends it.

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `cd apps/api-fastapi; .\.venv\Scripts\python.exe -m pytest -q --tb=no` (must stay 63+ passed, 0 failures; new tests/test_tier_limits_overrides.py adds the matrix) |
| CRG / Framework | Re-run update after changes; confirm +1 abstraction (TierLimitEvaluator); no creep. |
| Manual | As client create 4th search -> 400; agent hits 25 -> 400; admin unlimited; non-admin hits /scrapers/run -> 403; admin hits -> 202 + background fires. |

**No** memory/session updates until full success.

Re-run full pytest + capture `git status --porcelain` BEFORE every git add/commit.

---

## 6. Drift policy

If implementation diverges (e.g. different limits, no TierLimitEvaluator class, missing PEP257, live network in tests, non-atomic commits, 403 not used for role, etc.), update spec or code in same change — never silent drift.

This phase must keep the 11 abstractions +1 without introducing new long-lived state or duplicating limit logic elsewhere.

---

## 7. Implementation Notes (for agent)

- Spec + index + feature README **first** (before any .py changes).
- New file: services/tier_limit_evaluator.py (or integrate if fits existing, but prefer dedicated for single responsibility).
- Modify routers/saved_searches.py POST (inject evaluator via Depends or constructor, call assert before create).
- Add admin route (consider routers/admin.py if exists, or new; use existing IngestionOrchestrator patterns from sync_service).
- Tests: full isolation with local JWT (reuse patterns from test_rbac_perimeter.py).
- Chunks: 1. spec/docs, 2. TierLimitEvaluator + router mod, 3. admin scraper route, 4. test file. Each with pytest + status before commit.
- Update CRG note in this spec on commits.
- Ensure IngestionOrchestrator has a trigger method callable from background (add if missing, but prefer reuse).

Track abstractions: previous 11 + TierLimitEvaluator = 12.