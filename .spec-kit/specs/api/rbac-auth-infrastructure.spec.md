# Spec: Role-Based Access Control & Authentication Infrastructure

## Status: DRAFT
**Roadmap:** STREAM 5 PHASE 5.0  
**Branch:** `feat/stream-5-phase-5.0-rbac-auth-infrastructure` ← `develop`  
**Apps:** `apps/api-fastapi/` | `apps/storefront-next/`  
**Feature README:** `docs/features/rbac-auth-infrastructure/README.md`

**CRG Framework Baseline Note (per monitoring directive):** At completion of Phase 4.1: 9 core single-responsibility abstractions. This phase adds JWTTokenVerifier and RoleChecker (expanding baseline to 11). All new abstractions must be stateless processing containers. No session-passing or network creep in security layer. Re-assess formalization only via CRG if pattern duplication appears. Update this note on commit.

---

## 1. Objective

Implement local cryptographic JWT validation and RBAC tiering to secure the API perimeters and enforce tenant isolation on data mutations, using Supabase-issued tokens verified entirely locally against SUPABASE_JWT_SECRET. Extend the existing SavedSearch infrastructure with mandatory user_id for tenant scoping, while maintaining backward compatibility for legacy data via safe additive migration. Provide frontend support for token injection. All changes must preserve the existing 56-test matrix with zero failures.

**In scope**
- Local JWT validation using PyJWT or python-jose (HMAC SHA256), no Supabase network calls for verification.
- UserRole enum, UserCredentials model, JWTTokenVerifier class, RoleChecker dependency factory.
- get_current_user dependency.
- Update SavedSearch model with user_id; safe ALTER in ensure_ with default 'legacy_tenant'.
- Enforce user_id filters in SavedSearch and SavedSearchMatch queries.
- Protect saved_searches router with RoleChecker (e.g. agent/admin for certain ops).
- Frontend: inject Supabase session JWT as Bearer token in API calls.
- Full PEP 257 OOP docstrings on all new code.
- Isolated tests in test_rbac_perimeter.py using local token mocks.
- CRG monitoring and small atomic commits.
- Update spec, index, feature README before implementation.

**Out of scope**
- Full user management / registration flows (assume Supabase Auth handles issuance).
- Refresh token logic or session management beyond validation.
- RBAC on all existing routers (focus on saved_searches and related for this phase; document gaps).
- Production deployment of secrets (use env).
- Changes to notification or scraping pipelines.

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| (protected) | `/api/v1/saved-searches/*` | Now requires valid JWT via Depends(get_current_user); RoleChecker for mutations or sensitive ops. Queries scoped to credentials.user_id. |
| GET /signing/config or similar | (existing) | May remain open or protected based on role. |

**Models / tables:**
- UserRole(str, Enum): admin, agent, client
- UserCredentials(BaseModel): user_id: str, email: str, role: UserRole, raw_claims: dict
- Extend SavedSearch (and consider SavedSearchMatch if needed for consistency): add user_id: str = Field(index=True, nullable=False, default='legacy_tenant' in migration)

In queries:
```python
where(SavedSearch.user_id == credentials.user_id)
```

**Class interfaces (strict OOP + PEP257 required):**
- class JWTTokenVerifier: stateless; __init__ optional secret; verify_and_extract(token: str) -> UserCredentials ; raises HTTPException 401 on failure.
- class RoleChecker: __init__(self, allowed_roles: list[UserRole]); __call__(self, credentials: UserCredentials = Depends(get_current_user)) -> UserCredentials ; raises 403 if not allowed.
- def get_current_user(token: str = Depends(oauth2_scheme)) -> UserCredentials

Error handling: 401 for auth (invalid/expired/malformed token), 403 for insufficient role.

No network in verification path.

---

## 3. Storefront (if applicable)

- Update lib/api.ts (or api client) to get Supabase session (supabase.auth.getSession()), extract access_token, set Authorization: Bearer ${token} on requests to protected /api/v1/* .
- Update React Query hooks that call saved-searches to benefit automatically.
- No new UI for RBAC in this phase (focus infrastructure; roles assumed from Supabase user metadata or claims).

---

## 4. Security & boundaries

- Local-only validation: use jwt.decode with verify_signature=True, key=SUPABASE_JWT_SECRET, algorithms=["HS256"].
- Tenant isolation: every SavedSearch/SavedSearchMatch query filters by user_id from validated claims. Prevents cross-tenant access.
- No secrets in git; SUPABASE_JWT_SECRET via env (injected in deployment).
- Stateless: no DB sessions or state in verifier/checker.
- Preserve existing isolation: all prior mocks/tests continue to pass; new tests use local mocks only (no Supabase calls).
- OWASP: A01 broken access (enforced by roles + tenant filter), A07 auth failures (strict 401/403).
- Document gaps: full RLS at DB level may be future; Supabase policies should align but not relied on here.

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `cd apps/api-fastapi; .\.venv\Scripts\python.exe -m pytest -q --tb=no` (must remain 56+ passed, 0 failures; new test_rbac_perimeter.py adds coverage for verifier, roles, tenant filters) |
| Storefront | `cd apps/storefront-next; npm test -- --run && npm run build` |
| Manual / Isolation | Generate local test JWTs (with HS256); verify 401/403 behaviors; confirm queries return only own data; no outbound to supabase during auth. |
| CRG / Framework | Update after changes; confirm +2 abstractions (Verifier, RoleChecker); no creep (stateless, no session in auth). Log baseline to 11. |

**No** memory/session updates until full success.

Re-run full pytest + git status + CRG before EVERY git add/commit in chunks.

---

## 6. Drift policy

Implementation must match this spec exactly (local only, specific classes, DB additive with legacy default, tenant filters, DI, OOP docs, test structure). If new requirements emerge (e.g. more roles), update spec first. CRG used to detect if abstractions duplicate patterns warranting core framework extraction.

Phase 5.0 builds on prior (notification decoupling, isolation patterns) without regressing any behavior.

---

## 7. Implementation Blueprint (for agent)

- Spec + index + feature README first (before any .py/.ts changes).
- New file: services/auth.py containing all auth classes (stateless).
- Update models.py (SavedSearch user_id).
- Update database.py (ensure_ ALTER).
- Update routers/saved_searches.py (imports, Depends on routes, query filters).
- Update main.py? (add oauth2 scheme if global).
- Frontend: lib/api.ts + any using api calls for saved searches.
- New test file: tests/test_rbac_perimeter.py (use pyjwt to mint local tokens for tests; mock verifier if needed but prefer real with test secret).
- Config: assume SUPABASE_JWT_SECRET in env (add to .env.example if needed, but not committed).
- Dependencies: ensure PyJWT (or python-jose[cryptography]) in requirements.txt; add if missing via pip but note in commit.
- Chunks: 1. spec/docs, 2. auth classes + verifier, 3. DB + models, 4. route protection + filters, 5. frontend token injection, 6. tests. Each after full pytest + status capture.

Add to CRG note in this spec and update baseline log in commits.