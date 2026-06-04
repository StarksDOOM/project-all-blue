# All Blue Core — Agent Operating Manual (committed)

> Local `AGENTS.md` at repo root is gitignored for machine-specific overrides. **This file is the team canonical copy** — keep it in sync when agent rules change.

> [!CAUTION]
> **CRITICAL PRE-FLIGHT**: Before coding, read `memories/REGRESSIONS.md` when present. Identify or create the `.spec-kit/` spec for the active **STREAM X PHASE X.X** (see `.spec-kit/README.md`).

## Spec-Kit (ZERO-TOLERANCE — every feature)

Canonical index: **`.spec-kit/README.md`**. Enforcement table: **`engineering-directives.md` § Spec-Kit enforcement** (same directory).

| Rule | Requirement |
|------|-------------|
| **New feature** | Create `.spec-kit/specs/<area>/<feature>.spec.md` from `.spec-kit/templates/feature.spec.template.md` **before** implementation. |
| **Backfill** | All shipped features on `develop` must have a spec (see index table). |
| **Drift** | Code and spec change together — never merge architectural drift without spec update. |
| **README** | `docs/features/<slug>/README.md` = problem/outcomes only; API contracts live in the spec. |
| **Done** | Set spec `Status: SHIPPED` only after tests in the spec pass + user Manual Success. |
| **Register** | Add row to `.spec-kit/README.md` for every new spec. |

**STREAM 2:** scraper-error-telemetry (3.9), ingestion-oop (4.1).  
**STREAM 4:** transaction-legal-engine (4.0) → secure-pdf-signatures (5.0) → docusign-embedded-signing (5.1) → post-execution-audit (6.0) → realtime-sse-sync (7.0).

## Repository scope (STRICT)

**Work only in `project-all-blue`.** Do not modify `project-rodar` unless the user explicitly names another project.

## Pre-Commit Test Gate (ZERO-TOLERANCE)

No `git add` / `git commit` until applicable tests pass with **zero failures**.

| Workspace | Command |
| :--- | :--- |
| `apps/api-fastapi` | `.\.venv\Scripts\python.exe -m pytest` |
| `apps/storefront-next` | `npm test` / `npm run lint` when defined |

User approval (**Go**, **Stage this**) required before staging.

## Version control

- Feature branches off `develop`.
- Chunk commits after tests + user approval.
- **Clean tree before merge** — `git status` must be clean immediately before `git merge`.

## Code-review-graph (CRG)

See `code-review-graph.md`. Run `code_review_graph update` (or `build` when stale) without asking the user.

## Security — OWASP

See `engineering-directives.md` § Security — OWASP-aligned development.