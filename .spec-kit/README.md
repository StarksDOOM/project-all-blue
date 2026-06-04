# All Blue — Spec-Kit Index

Architectural ground truth for **All Blue Core**. Implementation must match these specs before a feature is marked final.

| Spec | Roadmap | Status |
|------|---------|--------|
| [api/ingestion-oop.spec.md](specs/api/ingestion-oop.spec.md) | STREAM 2 PHASE 4.1 | DRAFT — OOP refactor target |

## Developer tooling

- **Code reviews (token-efficient):** [docs/development/code-review-graph.md](../docs/development/code-review-graph.md) — local index via [code-review-graph](https://github.com/tirth8205/code-review-graph); not committed to git.
- **Agent engineering directives:** [docs/development/engineering-directives.md](../docs/development/engineering-directives.md) — CRG default, Graphify upgrade gates, code comments, **OWASP Top 10 (mandatory)**.
- **Graphify upgrade (when CRG is not enough):** [docs/development/graphify-upgrade-requirements.md](../docs/development/graphify-upgrade-requirements.md)

## Conventions

- **File naming:** `<domain>-<feature>.spec.md` under `specs/<area>/`
- **Phases:** Use `STREAM X PHASE X.X` in every spec header
- **Verification:** Each spec ends with test gates; no memory/session updates until Manual Success
- **Drift:** If code diverges from spec, fix code or update spec first — never ship silent drift