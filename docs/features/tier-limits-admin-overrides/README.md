# Tenant Operational Tier Limits & Administrative Execution Overrides (STREAM 5 PHASE 5.1)

## Problem
Post-Phase 5.0, any authenticated user (regardless of tier) can create unlimited SavedSearch alerts. This leads to resource abuse (DB bloat, excessive matching/evaluation load on ingestion pipeline) by lower-tier users (clients/agents). There is also no controlled way for admins to force immediate scraping outside the normal schedule without exposing powerful operations to non-admins or risking abuse.

## Outcomes
- Operational capacity limits enforced at creation time: client max 3 active searches, agent max 25, admin unlimited.
- New stateless 'TierLimitEvaluator' class (injected after RBAC) performs count query and raises 400 on breach. Fully documented per PEP 257.
- New admin-only 'POST /api/v1/scrapers/run' (guarded by RoleChecker([ADMIN])) that schedules IngestionOrchestrator work via BackgroundTasks and returns 202 immediately.
- Zero regression on existing 63 tests (0 failures); new high-density tests use only local JWT mocks (no networks).
- Spec-first: complete spec + index registration + feature README before any code.
- Small atomic commits only, with full pytest + git status captured before every add/commit.
- CRG monitored; abstraction count from 11 to 12 (TierLimitEvaluator is the new one). No creep.
- Maintains strict tenant isolation and local auth from prior phases.

**Spec:** [.spec-kit/specs/api/tier-limits-admin-overrides.spec.md](../../.spec-kit/specs/api/tier-limits-admin-overrides.spec.md)

**Baseline:** 12 abstractions at end of phase (see spec for CRG log).

Status: Follows DRAFT spec; SHIPPED only after gates + manual success.
