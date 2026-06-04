# Role-Based Access Control & Authentication Infrastructure (STREAM 5 PHASE 5.0)

## Problem
The platform has grown sophisticated pipelines for scraping, matching (SearchMatchEngine), notifications (NotificationDispatcher + EmailClient protocol), and history. However, all API surfaces remain unauthenticated and unisolated: any client can read/write any user's SavedSearch alerts and matches by guessing IDs. This violates tenant isolation, enables data harvesting, and prevents role-based controls (e.g. agents vs clients). Supabase Auth can issue JWTs, but verification must be local (no network roundtrips in hot paths) and RBAC + data scoping must be enforced at the Python service layer.

## Outcomes
- Local-only HMAC-SHA256 JWT validation against SUPABASE_JWT_SECRET using stateless JWTTokenVerifier (no Supabase HTTP calls ever in request path).
- Clean RBAC via UserRole enum + RoleChecker dependency (403 on insufficient role).
- Tenant isolation: SavedSearch (and SavedSearchMatch queries) now require and filter by validated user_id from claims.
- Safe additive DB migration (ALTER with legacy_tenant default) so existing dev data isn't broken.
- Frontend transparently forwards Supabase session token as Bearer JWT.
- All new code is strict OOP with exhaustive PEP 257 docstrings (Purpose/Lifecycle/Thread-safety/Collaborators/Invariants/Params/Returns/Raises/Side Effects).
- New isolated tests using only local token generation (no external auth calls).
- Baseline expands from 9 to 11 abstractions (JWTTokenVerifier + RoleChecker); CRG monitored; no creep.
- Zero regression: existing 56 tests + 0 failures preserved.
- Spec-first: rbac spec + index + feature README created/updated before any implementation.

**Spec:** [.spec-kit/specs/api/rbac-auth-infrastructure.spec.md](../../.spec-kit/specs/api/rbac-auth-infrastructure.spec.md)

**CRG Baseline:** 11 at end of phase (see spec for monitoring log).

Status: Implementation follows DRAFT spec; SHIPPED only after gates + manual success on develop.
