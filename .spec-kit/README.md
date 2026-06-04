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
```

## Developer tooling

- **Code reviews (token-efficient):** [docs/development/code-review-graph.md](../docs/development/code-review-graph.md)
- **Agent engineering directives:** [docs/development/engineering-directives.md](../docs/development/engineering-directives.md) — CRG, Graphify gates, OWASP, **Spec-Kit enforcement**
- **Graphify upgrade:** [docs/development/graphify-upgrade-requirements.md](../docs/development/graphify-upgrade-requirements.md)

## Conventions

- **File naming:** `<domain>-<feature>.spec.md` under `specs/<area>/` (`api/`, `storefront/` when UI-only)
- **Phases:** Use `STREAM X PHASE X.X` in every spec header
- **Verification:** Each spec ends with test gates; no memory/session updates until Manual Success
- **Drift:** If code diverges from spec, fix code or update spec first — never ship silent drift
- **New feature checklist:** spec → feature README → branch → tests → merge (clean tree)