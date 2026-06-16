# All Blue Core — Agent Operating Manual (committed)

> Local `AGENTS.md` at repo root is gitignored for machine-specific overrides. **This file is the team canonical copy** — keep it in sync when agent rules change.

> [!CAUTION]
> **CRITICAL PRE-FLIGHT**: BEFORE making any changes, running any terminal commands, or writing code, the Agent MUST open and read `memories/REGRESSIONS.md` in full to ensure no regressions are introduced. Identify or create the `.spec-kit/` spec for the active **STREAM X PHASE X.X** (see `.spec-kit/README.md`).

## Regression Pre-Flight Check (ZERO-TOLERANCE)

Before proposing any implementation plan, making any code modifications, or running any commands in this workspace, the Agent MUST:
1. Open and read `memories/REGRESSIONS.md` in full.
2. Confirm that the planned implementation or verification command does not conflict with or regress any of the documented environment traps, caching conflicts, or routing behaviors listed in the regression log.
3. This is a mandatory zero-tolerance gate for all active streams and bug-fix tasks.

## Spec-Kit (ZERO-TOLERANCE — every feature)

Canonical index: **`.spec-kit/README.md`**. Enforcement table: **`engineering-directives.md` § Spec-Kit enforcement** (same directory).

| Rule | Requirement |
|------|-------------|
| **New feature** | Create `.spec-kit/specs/<area>/<feature>.spec.md` from `.spec-kit/templates/feature.spec.template.md` **before** implementation. |
| **Backfill** | All shipped features on `develop` must have a spec (see index table). |
| **Drift** | Code and spec change together — never merge architectural drift without spec update. |
| **README** | `docs/features/<slug>/README.md` = problem/outcomes only; API contracts live in the spec. |
| **Done** | Set spec `Status: SHIPPED` only after tests in the spec pass + explicit user confirmation/approval. |
| **Register** | Add row to `.spec-kit/README.md` for every new spec. |

**STREAM 2:** scraper-error-telemetry (3.9), ingestion-oop (4.1).  
**STREAM 4:** transaction-legal-engine (4.0) → secure-pdf-signatures (5.0) → docusign-embedded-signing (5.1) → post-execution-audit (6.0) → realtime-sse-sync (7.0).  
**STREAM 6:** contract-generation-docusign (1.0) → docusign-connect-webhooks (1.1).

## Repository scope (STRICT)

**Work only in `project-all-blue`.** Do not modify `project-rodar` unless the user explicitly names another project.

## Pre-Commit Test Gate (ZERO-TOLERANCE)

No `git add` / `git commit` until applicable tests pass with **zero failures**.

| Workspace | Command |
| :--- | :--- |
| `apps/api-fastapi` | `.\.venv\Scripts\python.exe -m pytest` |
| `apps/storefront-next` | `npm test` / `npm run lint` when defined |

User approval (**Go**, **Stage this**) required before staging.

## Integration Tests (ZERO-MOCKS)

- Mocks are **strictly forbidden** in integration tests.
- Only unit tests may use structural mocks/patches (e.g., for isolating external third-party SDKs like DocuSign, Supabase, or Resend).
- Integration tests must execute against real local/test database engines and services without mocking or patching.

## Regression-Free Fixes (ZERO-TOLERANCE)

When the user instructs you to **fix** something (a bug report, "the gallery is broken for X", "remove the test data", "make Y work"), that directive is **narrowly scoped**. Implementing the fix **must not**:

- Break, regress, or change behavior in any other part of the system.
- Introduce new bugs, side effects, or altered defaults in unrelated components, pages, endpoints, models, or flows.
- "While I'm here" cleanups, refactors, or expansions that touch areas outside the exact request.
- Assume that fixing A automatically justifies touching B, C, or the test suite in ways that could destabilize them.

**Rules:**
- Scope the change to the minimal correct fix for the stated problem + root cause only.
- Before editing, use available tools (CRG `get_impact_radius_tool`, grep, code review of callers) to understand the blast radius.
- Run **all** applicable full test gates (not just "the changed file") + manual verification of the reported symptom **and** areas that could be affected.
- If any ambiguity exists about whether a change could affect other things, **stop and ask the user** for clarification or explicit approval to broaden scope — do not guess or "be helpful" by doing extra.
- Document in thinking (and commit message if applicable) exactly what was changed and why it is isolated.
- This rule applies on top of (and does not replace) the pre-commit test gate, small atomic commits, spec-kit, and clean-tree rules.

Violations are treated as seriously as other ZERO-TOLERANCE rules. The user has been explicit that "fix X" does **not** mean "break or change Y".

## Agent Development Safeguards (ZERO-TOLERANCE)

To prevent security leaks, broken documentation, and incomplete work, the Agent MUST adhere to these checks on every task:

- **Stray Secrets**: Double-check recent commits, diffs, and environment setups to ensure absolutely no live API keys, database URLs, or staging credentials accidentally slip past the `.gitignore` into the public repository.
- **Dead Document Links**: Verify all links inside markdown documents (such as [README.md](file:///c:/Users/Leo%20Fulgencio/Projects/project-all-blue/README.md) or manuals pointing to [engineering-directives.md](file:///c:/Users/Leo%20Fulgencio/Projects/project-all-blue/docs/development/engineering-directives.md) or [REGRESSIONS.md](file:///c:/Users/Leo%20Fulgencio/Projects/project-all-blue/memories/REGRESSIONS.md)) are valid and do not throw a GitHub 404.
- **No Naked Placeholders**: Ensure that core markdown files do not have empty "TODO: fill this in later" or placeholder blocks at the top of the document.

## Version control

- **Branching Strategy**: Each new phase or stream must have its own explicit branching strategy (branching off `develop`).
- Feature branches off `develop`.
- Chunk commits into **small, atomic units** after tests + user approval (per the "Small commits rule" in Agents.md — one focused change per commit, no large bundles).
- **Clean tree before merge** — `git status` must be clean immediately before `git merge`.

## Code-review-graph (CRG)

See `code-review-graph.md`. Run `code_review_graph update` (or `build` when stale) without asking the user.

## Security — OWASP

See `engineering-directives.md` § Security — OWASP-aligned development.

## Python OOP & Documentation Standards

See `engineering-directives.md` § Python OOP & Documentation Standards (mandatory for all `apps/api-fastapi` work).

All domain logic must be class-based (inheritance + composition). Every module, class, and public method requires complete, accurate PEP 257 documentation updated in the same change. Thin orchestrators only; behavior belongs in classes.

## Internal Framework Creep Monitoring (CRG-driven)

See `engineering-directives.md` § Monitoring Internal Framework Creep with CRG.

Use CRG (CLI updates + MCP tools like get_minimal_context_tool with framework assessment task, query_graph_tool for children_of/inheritors_of on base/orchestrator classes) to monitor growth of the custom OOP layer. Trigger assessment for formalization (small internal core/ framework with base classes) when signals appear (multiple similar orchestrators/engines, duplicated patterns). Only formalize after explicit user approval. This is now a standing monitoring responsibility.