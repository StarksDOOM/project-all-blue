# All Blue — Spec-Kit Index

Architectural ground truth for **All Blue Core**. Implementation must match these specs before a feature is marked final.

## Mandatory agent workflow

1. **Before coding any new feature:** create or identify a spec under `.spec-kit/specs/` (copy [templates/feature.spec.template.md](templates/feature.spec.template.md)).
2. **During implementation:** update the spec if architecture changes — fix code or spec in the same PR, never silent drift.
3. **Before merge:** spec `Status` → `SHIPPED` only after pytest/npm gates in the spec pass + user Manual Success.
4. **Pair with feature README:** every `docs/features/<slug>/README.md` must link to its spec (problem/outcomes only in README; contracts in spec).

## Spec index

| Spec | Roadmap | Status |
|------|---------|--------|
| [api/ingestion-oop.spec.md](specs/api/ingestion-oop.spec.md) | STREAM 2 PHASE 4.1 | SHIPPED |
| [api/scraper-error-telemetry.spec.md](specs/api/scraper-error-telemetry.spec.md) | STREAM 2 PHASE 3.9 | SHIPPED |
| [api/transaction-legal-engine.spec.md](specs/api/transaction-legal-engine.spec.md) | STREAM 4 PHASE 4.0 | SHIPPED |
| [api/secure-pdf-signatures.spec.md](specs/api/secure-pdf-signatures.spec.md) | STREAM 4 PHASE 5.0 | SHIPPED |
| [api/docusign-embedded-signing.spec.md](specs/api/docusign-embedded-signing.spec.md) | STREAM 4 PHASE 5.1 | SHIPPED |
| [api/post-execution-audit.spec.md](specs/api/post-execution-audit.spec.md) | STREAM 4 PHASE 6.0 | SHIPPED |
| [api/realtime-sse-sync.spec.md](specs/api/realtime-sse-sync.spec.md) | STREAM 4 PHASE 7.0 | SHIPPED |
| [frontend/performance-optimization.spec.md](specs/frontend/performance-optimization.spec.md) | STREAM 5 PHASE 1.0 | SHIPPED |
| [api/faceted-filtering-matrix.spec.md](specs/api/faceted-filtering-matrix.spec.md) | STREAM 5 PHASE 2.0 | SHIPPED |
| [api/saved-searches-alerts.spec.md](specs/api/saved-searches-alerts.spec.md) | STREAM 5 PHASE 3.0 | SHIPPED |
| [api/outbound-notification-delivery.spec.md](specs/api/outbound-notification-delivery.spec.md) | STREAM 5 PHASE 4.1 (external email gateway) | DRAFT |
| [api/rbac-auth-infrastructure.spec.md](specs/api/rbac-auth-infrastructure.spec.md) | STREAM 5 PHASE 5.0 | DRAFT |
| [api/tier-limits-admin-overrides.spec.md](specs/api/tier-limits-admin-overrides.spec.md) | STREAM 5 PHASE 5.1 | DRAFT |
| [api/contract-generation-docusign.spec.md](specs/api/contract-generation-docusign.spec.md) | STREAM 6 PHASE 1.0 | SHIPPED |
| [api/docusign-connect-webhooks.spec.md](specs/api/docusign-connect-webhooks.spec.md) | STREAM 6 PHASE 1.1 | SHIPPED |
| [api/transaction-ledger-dashboard.spec.md](specs/api/transaction-ledger-dashboard.spec.md) | STREAM 6 PHASE 1.2 | SHIPPED |
| [api/wholesale-analytics-engine.spec.md](specs/api/wholesale-analytics-engine.spec.md) | STREAM 6 PHASE 1.3 | DRAFT |

## Roadmap map (legal & execution pipeline)

```text
STREAM 2 — Ingestion & inventory
  PHASE 3.9  scraper-error-telemetry
  PHASE 4.1  ingestion-oop

STREAM 4 — Transactions & execution
  PHASE 4.0  transaction-legal-engine
  PHASE 5.0  secure-pdf-signatures
  PHASE 5.1  docusign-embedded-signing
  PHASE 6.0  post-execution-audit
  PHASE 7.0  realtime-sse-sync

STREAM 5 — Storefront performance
  PHASE 1.0  performance-optimization (RSC prefetch, hydration, Suspense, bundle analyzer)
  PHASE 2.0  faceted-filtering-matrix (dynamic SQL facets, URL state, debounced panel)
  PHASE 3.0  saved-searches-alerts (persist filter matrix + async match evaluator on ingestion) [SHIPPED; baseline 7 OOP structural abstractions per CRG monitoring]
  PHASE 4.0  outbound-notification-delivery (jinja2 email compiler + dispatcher + match history ledger) [DRAFT; baseline started at 7]
  PHASE 4.1  external-email-gateway (Resend via httpx, EmailClient Protocol, DI, network error handling) [DRAFT; update baseline, no creep, full docs]
  PHASE 5.0  rbac-auth-infrastructure (local JWT validation, RBAC RoleChecker, tenant user_id isolation on SavedSearch) [DRAFT; expands baseline to 11; strict local crypto, no network creep]
  PHASE 5.1  tier-limits-admin-overrides (per-role SavedSearch caps via TierLimitEvaluator, admin-only scraper trigger via BackgroundTasks) [DRAFT; +1 abstraction to 12; atomic commits + full isolation tests]

STREAM 6 — Contract automation & signing
  PHASE 1.0  contract-generation-docusign (M2M authentication, envelope builder, dispatcher, UI action trigger) [SHIPPED; baseline 12]
  PHASE 1.1  docusign-connect-webhooks (stateless Connect webhook, HMAC SHA-256 verification, notifications) [SHIPPED; baseline 14]
  PHASE 1.2  transaction-ledger-dashboard (protected backend service, GET /contracts route, Next.js table UI) [SHIPPED; baseline 15]
  PHASE 1.3  wholesale-analytics-engine (stateless WholesalePricingEngine, sector median ARV, role-gated Guía de Wholesaling UI) [DRAFT; baseline 16]
```

## Developer tooling

- **Code reviews (token-efficient):** [docs/development/code-review-graph.md](../docs/development/code-review-graph.md)
- **Agent operating manual:** [docs/development/agent-operating-manual.md](../docs/development/agent-operating-manual.md) — Spec-Kit, tests, merge, CRG, OWASP
- **Agent engineering directives:** [docs/development/engineering-directives.md](../docs/development/engineering-directives.md) — CRG, Graphify gates, **Spec-Kit enforcement**
- **Graphify upgrade:** [docs/development/graphify-upgrade-requirements.md](../docs/development/graphify-upgrade-requirements.md)

## Conventions

- **File naming:** `<domain>-<feature>.spec.md` under `specs/<area>/` (`api/`, `storefront/` when UI-only)
- **Phases:** Use `STREAM X PHASE X.X` in every spec header
- **Verification:** Each spec ends with test gates; no memory/session updates until Manual Success
- **Drift:** If code diverges from spec, fix code or update spec first — never ship silent drift
- **New feature checklist:** spec → feature README → branch → tests → merge (clean tree)