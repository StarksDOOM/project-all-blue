# Project All Blue

Internal platform for **real estate listing ingestion**, **agent-facing inventory**, and **transaction/legal document workflows** (Dominican Republic market).

This repository is the **All Blue Core** monorepo. It is not a public product marketing site.

---

## What’s in the repo

| Area | Purpose |
|------|---------|
| `apps/api-fastapi` | Core API, ingestion, transactions, contracts |
| `apps/storefront-next` | Next.js agent dashboard and property UX |
| `docs/features/` | **Problem/solution** notes per major feature (no implementation runbooks) |
| `docs/development/` | Engineering directives (agents, reviews, security posture) |
| `.spec-kit/` | Architectural specs (STREAM / PHASE nomenclature) |

---

## Feature documentation (problem / solution only)

High-level **why** and **what**—not portal parsing, scraping, or internal “how”:

- [Scraper error telemetry & listing integrity](docs/features/scraper-error-telemetry/README.md)
- [Transaction & legal document engine (Phase 4)](docs/features/transaction-legal-engine/README.md)
- [Secure PDF & signatures (Phase 5)](docs/features/secure-pdf-signatures/README.md)

Detailed implementation stays in code and private engineering notes.

---

## Local development (summary)

1. Start Postgres (`docker compose up -d` from repo root).
2. Configure `apps/api-fastapi/.env` and `apps/storefront-next/.env.local` (not committed).
3. API: `apps/api-fastapi` virtualenv + application server on port **8000**.
4. Storefront: `apps/storefront-next` dev server on port **3000**.

Run tests before commits:

- API: `pytest` from `apps/api-fastapi`
- Storefront: `npm test` from `apps/storefront-next`

---

## Branching

- **`develop`** — integration branch  
- **`feat/*`** — feature work; merge after verification and clean `git status`

---

## Security & agents

Agents and contributors must follow [engineering directives](docs/development/engineering-directives.md) (OWASP-aligned development, reviews, no secrets in git).

**CRITICAL PRE-FLIGHT FOR AGENTS**: Before making any changes, proposing plans, running commands, or writing code, all agents MUST open and read [REGRESSIONS.md](file:///c:/Users/Leo%20Fulgencio/Projects/project-all-blue/memories/REGRESSIONS.md) in full to prevent environment, cache, or routing regressions.

Root `AGENTS.md` may exist locally for assistants; canonical tracked policy is under `docs/development/`.

---

## Agentic workflows & subagents

This project uses a suite of specialized, token-efficient subagents to automate task tracking, implementation, pre-commit safety checks, and code reviews:

- **[Subagents Manual](docs/development/subagents_manual.md)**: Guides the invocation, operational prompts, and best practices for all defined agents.
- **Subagents**:
  - `issue-monitor`: Automatically scans open issues, parses task checklists, and updates/closes them based on local git history.
  - `feature-developer`: Implements spec-locked tasks in Python (OOP + PEP 257) or TypeScript, utilizing the `code-review-graph` (CRG) index to read targeted line ranges.
  - `regression-checker`: Pre-commit safety checker verifying secret leaks, dead document links, and naked placeholders.
  - `code-reviewer`: Analyzes the impact radius of code changes and audits security posture (OWASP) using structural CRG queries.

---

## License / distribution

Private repository. Do not publish implementation details from this codebase without explicit approval.