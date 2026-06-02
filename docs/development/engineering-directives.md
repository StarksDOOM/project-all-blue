# Engineering directives (All Blue Core)

Canonical copy for agents and reviewers. Local `AGENTS.md` is gitignored; sync this section there if your assistant reads `AGENTS.md` at session start.

Applies to `apps/api-fastapi/`, `apps/storefront-next/`, `.spec-kit/`, and `docs/features/`.

## Code intelligence (default: CRG)

**Default tool:** [code-review-graph (CRG)](code-review-graph.md) — token-minimal reviews via MCP (`get_minimal_context`, `detect_changes`, `get_impact_radius`). Do not paste whole repos or large `GRAPH_REPORT` dumps into chat unless the user asks.

**Agent duty:** Before large refactors or cross-module reviews, use CRG MCP tools (or `code-review-graph detect-changes --brief`) and read only impacted files. Physical verification still requires tests and `.spec-kit/` specs.

## Graphify upgrade (suggest only when requirements are met)

Graphify (`graphifyy` on PyPI) is **richer and higher-token** than CRG. Do **not** install or migrate by default.

When work touches architecture spanning multiple apps, docs, or schemas, **check** [Graphify upgrade requirements](graphify-upgrade-requirements.md). If **all mandatory gates** pass and **at least two** optional triggers apply, **propose** upgrading to Graphify to the human (do not run install/build without explicit approval). Include: why CRG is insufficient, estimated token/disk cost, and the minimal install command (`uv tool install graphifyy` + `graphify cursor install --project`).

Until then, stay on CRG.

## Code comments (required where necessary)

When writing or changing production code in this repo:

- Add **module-level** docstrings for packages and orchestration entry points (`services/`, `scrapers/drivers/`, routers).
- Add **class and public method** docstrings (purpose, inputs, outputs, raised errors, side effects).
- Add **inline comments** only for non-obvious logic: business rules (e.g. DOP/USD, portal keys), concurrency, retries, idempotency/upsert keys, security boundaries, and integration quirks (AdsPower, pagination fields).
- Do **not** narrate obvious code (`# increment i`). Prefer clearer names over comments when that suffices.
- Keep comments accurate when behavior changes; remove stale comments in the same edit.
- Match existing file style (Python: PEP 257; TypeScript: JSDoc on exported APIs).

Spec-kit and walkthroughs do not replace in-code documentation for maintainers.