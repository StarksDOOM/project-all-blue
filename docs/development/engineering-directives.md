# Engineering directives (All Blue Core)

Canonical copy for agents and reviewers. Full operating manual (committed): **[agent-operating-manual.md](agent-operating-manual.md)**. Local root `AGENTS.md` is gitignored for machine overrides — keep it aligned with that file.

Applies to `apps/api-fastapi/`, `apps/storefront-next/`, `.spec-kit/`, and `docs/features/`.

## Code intelligence (default: CRG)

**Default tool:** [code-review-graph (CRG)](code-review-graph.md) — token-minimal reviews via MCP (`get_minimal_context`, `detect_changes`, `get_impact_radius`). Do not paste whole repos or large `GRAPH_REPORT` dumps into chat unless the user asks.

**Agent duty:** Before large refactors or cross-module reviews, use CRG MCP tools (or `code-review-graph detect-changes --brief`) and read only impacted files. Physical verification still requires tests and `.spec-kit/` specs.

**Autonomous refresh (no user prompt):** The agent MUST refresh the graph before relying on it—run `C:\Python313\python.exe -m code_review_graph update` from the repo root on each session or before MCP/detect-changes; run `build` when `status` reports a branch mismatch, after rebase/merge, or when the index is missing/stale. Do not ask permission to update/build. See `Agents.md` § Code-review-graph.

## Graphify upgrade (suggest only when requirements are met)

Graphify (`graphifyy` on PyPI) is **richer and higher-token** than CRG. Do **not** install or migrate by default.

When work touches architecture spanning multiple apps, docs, or schemas, **check** [Graphify upgrade requirements](graphify-upgrade-requirements.md). If **all mandatory gates** pass and **at least two** optional triggers apply, **propose** upgrading to Graphify to the human (do not run install/build without explicit approval). Include: why CRG is insufficient, estimated token/disk cost, and the minimal install command (`uv tool install graphifyy` + `graphify cursor install --project`).

Until then, stay on CRG.

## Regression-Free Fixes & Pre-Flight Check (agent behavior)

> [!CAUTION]
> **CRITICAL PRE-FLIGHT**: BEFORE making any changes, proposing implementation plans, running terminal commands, or writing code, the Agent MUST:
> 1. Open and read `memories/REGRESSIONS.md` in full.
> 2. Confirm that the planned changes or verification commands do not conflict with or regress the documented environment traps, caching conflicts, or routing behaviors listed in the regression log.
> This is a mandatory zero-tolerance pre-flight gate.

See root `Agents.md` § "Regression-Free Fixes (ZERO-TOLERANCE)" and the committed `agent-operating-manual.md` for the full rule.

**Summary for implementation:** A "fix X" request is narrowly scoped to X only. Do not use it as an excuse to touch, refactor, or alter unrelated code, data, behavior, or tests. Verify blast radius (CRG + tests + manual) and ask before broadening. "Fixing the gallery" does not mean "also change how lists work" or "break auth for alerts."

## Python OOP & Documentation Standards (mandatory for apps/api-fastapi)

**All Python code** written or modified under `apps/api-fastapi/` **MUST** be implemented using strict object-oriented programming and must be comprehensively documented. This is a ZERO-TOLERANCE rule, extending the precedent established by the `ingestion-oop` phase (STREAM 2 PHASE 4.1).

### OOP Requirements
- **Core logic is always OOP.** Domain behavior, business rules, state machines, pipelines, evaluators, scrapers, enrichment, notification engines, and orchestration **must** live inside classes. Large free functions, procedural scripts, or "god modules" of top-level functions are not allowed for production logic.
- Use **inheritance** for is-a relationships and shared implementation (e.g. `BaseDriver`, `AllBlueBaseModel`).
- Use **composition** and delegation for has-a / uses-a relationships (orchestrators own sessions, drivers, and services rather than inheriting everything).
- Define **interfaces** explicitly using `abc.ABC` or `typing.Protocol` when multiple implementations exist or are expected in the future.
- **Encapsulate state.** Keep mutable state inside class instances. Avoid module-level mutable singletons, globals, or passing raw dicts/JSON around when a proper model, dataclass, or value object provides better encapsulation and validation.
- **Routers, CLI scripts, and `main.py` are thin.** They perform dependency wiring, request parsing, and delegation only. All interesting behavior lives in service/orchestrator/engine classes.
- When extending behavior (new match strategies, notification channels, scraper drivers, etc.), introduce new classes or use the Strategy / Template Method / Factory patterns instead of growing long conditional blocks inside existing functions.
- Small pure helper functions are permitted **only** if they are:
  - Private (`_prefixed`)
  - Trivially testable in isolation
  - Called exclusively from within a class method
- The `search_match_engine`, `property_list_service`, `sync_service`, scraper drivers, and all future engines/services must be class-based (or provide a clear class façade) even when they expose a simple function entry point for convenience.

### Documentation Requirements (PEP 257 — mandatory on every edit)
- **Module docstring** (required for every non-`__init__.py` file): Describe the module's responsibility, the primary classes it exports, the public API surface, thread-safety / background usage notes, and integration points (e.g. "Invoked by `IngestionOrchestrator` immediately after a successful chunk commit for newly inserted rows.").
- **Class docstrings** (every class): Must cover:
  - Purpose and single responsibility
  - Lifecycle (construction, usage, cleanup)
  - Thread / concurrency / transaction safety notes (critical for ingestion background threads)
  - Key collaborators and dependencies
  - Any important invariants or side effects
- **Public method and `__init__` docstrings**: Document parameters, return type/value, exceptions that can be raised, and observable side effects. Include "Raises:", "Returns:", and "Side effects:" sections where applicable.
- **Private methods** (`_foo`): Add a docstring whenever the implementation or contract is non-obvious.
- **Inline comments**: Extremely sparing. Use only to explain *why* for non-obvious business rules (price derivation, portal quirks, security boundaries, retry semantics, etc.). Never explain what the next line of code does.
- **Accuracy on change**: Every edit that changes behavior **must** update or delete the corresponding docstrings and comments in the same change. Stale documentation is a defect.
- Style: Follow PEP 257. Within a single file or package, be internally consistent (Google-style and NumPy-style are both acceptable if the file doesn't mix them).

Spec-kit, feature READMEs, and this document do **not** replace in-code documentation. Maintainers must be able to understand a class or module from its docstrings alone.

Violations of the OOP or documentation rules are treated with the same severity as security or Spec-Kit violations: the change is incomplete until fixed.

## Monitoring Internal Framework Creep with CRG

The OOP mandate is causing the project to grow a rich internal application architecture on top of FastAPI (IngestionOrchestrator + Driver ABC + Factory, SearchMatchEngine, RealtimeBroadcaster, DocusignOrchestrator, PostExecutionPipeline, various *Service classes, observability hooks, schema layers, etc.). This is valuable for the complexity of background workers, pluggable scrapers, faceted matching, signing pipelines, and realtime sync.

However, we must **not** let this become an accidental custom framework without conscious decision.

**Agent duty (ongoing):** Use the CRG index as an objective sensor for when the layer is maturing into something that deserves formalization (base classes, dedicated package, architecture docs).

**CRG-based monitoring protocol (execute on relevant triggers):**
1. Always run `C:\Python313\python.exe -m code_review_graph update` after touching services/, scrapers/, models, or adding orchestration logic (already required).
2. Immediately after, or when starting work on new pipelines/engines, invoke MCP tools (first `search_tool` for schema if needed):
   - `get_minimal_context_tool` with task describing "assess oop framework layer / orchestrator engine growth".
   - `query_graph_tool` with patterns such as `children_of` (target a services/*.py or scrapers/drivers/base_driver.py), `inheritors_of` (target BaseDriver or similar).
   - `get_impact_radius_tool` on key files like sync_service.py, search_match_engine.py, driver_factory.py.
3. Also run CLI `code_review_graph status` and observe node/edge growth in the services + scrapers communities.
4. Look specifically for:
   - Rising count of classes whose names contain Orchestrator|Engine|Pipeline|Base|Factory|Registry.
   - Similar structural patterns (session in __init__, lifecycle methods, ensure_* calls, commit isolation).
   - High fan-in/fan-out from a small set of core classes.
   - New features copying structure from existing orchestrators/engines.

**Assessment & escalation triggers:**
- When adding the Nth similar abstraction (roughly when you have 4–6 independent *Orchestrator/*Engine classes with overlapping concerns).
- When the agent finds itself wanting to extract a shared base "just for this one" or when copy-paste of lifecycle/session handling appears.
- At the start of any new STREAM that involves background/async coordination or saved-state + matching (like Phase 3 saved-searches-alerts).
- When CRG communities or impact graphs start showing a distinct "orchestration core" separate from domain models and HTTP routers.

**What to do when the signal is strong:**
- Do **not** create BaseOrchestrator / core/ package yet.
- Document the current state (using CRG data + file list) in your reasoning.
- Propose formalization to the user (e.g. "CRG now shows 7 orchestration-style classes with duplicated session + lifecycle patterns. Time to assess extracting a small internal framework?").
- If approved ("Go"), then:
  - Create a design for the minimal core (base classes, common utilities, package layout).
  - Update this section, the Python OOP directive, and Agents.md.
  - Refactor incrementally (one orchestrator/engine at a time).
  - Add the new structure to .spec-kit if it affects a feature.
- Until then, continue with explicit classes following the OOP rules, but keep them project-specific rather than "framework-ready".

**Goal:** Deliberate, user-approved evolution into (or away from) a small internal framework. CRG provides the data-driven early warning instead of relying on the agent's subjective feeling.

Update this section whenever a formalization decision is made.

## Spec-Kit enforcement (mandatory for every feature)

Ground truth for architecture lives in **`.spec-kit/specs/`**, not only in `docs/features/*/README.md`.

| When | Agent action |
|------|----------------|
| **New feature requested** | Create `.spec-kit/specs/<area>/<feature>.spec.md` from [`.spec-kit/templates/feature.spec.template.md`](../../.spec-kit/templates/feature.spec.template.md) **before** writing production code. Set `Status: DRAFT` and correct `STREAM X PHASE X.X`. |
| **Existing feature without spec** | Backfill spec to match shipped code on `develop`; set `Status: SHIPPED` after tests pass. |
| **Implementation changes design** | Update the spec in the same PR as the code change. |
| **Feature complete** | Spec lists verification gates (pytest paths); README stays problem/outcomes-only. |
| **Index** | Register the spec in [`.spec-kit/README.md`](../../.spec-kit/README.md). |

**README vs spec:** `docs/features/<slug>/README.md` = why/outcomes (no API secrets). `.spec-kit` spec = routes, models, state machine, tests, security boundaries.

## Security — OWASP-aligned development (mandatory)

All new and changed code in **All Blue Core** MUST follow [OWASP Top 10](https://owasp.org/www-project-top-ten/) thinking across **API, storefront, storage, and ops**. Security is not a post-merge pass; it is part of every feature design and review.

### A01 — Broken access control

- **Never** trust client-supplied IDs for authorization alone (`property_id`, `transaction_id`, `remote_id`). Resolve resources server-side; return **404** (not 403) when a row does not exist to avoid enumeration leaks where appropriate.
- Transaction and contract endpoints MUST verify the session/contract belongs to the intended workflow (future: tenant/user binding). Do not expose admin routes (`/api/admin/*`) on public CORS without auth when hardening production.
- Storefront MUST NOT expose internal paths, raw `file_path` from the DB, or storage roots to the browser—use API streaming endpoints (`/contract/pdf`) only.

### A02 — Cryptographic failures

- **Secrets:** `DATABASE_URL`, API keys, and signing secrets only via `.env` / `.env.local` (gitignored). Never commit credentials or log them.
- **Phase 5 ledger:** PDF tamper evidence uses **SHA-256 of PDF bytes** (`document_hash`). Re-verify hash on disk before `execute-signature`. Do not confuse `version_hash` (markdown) with `document_hash` (PDF).
- **Signing records:** `signing_hash` binds role, transaction id, document hash, timestamp, IP, and User-Agent—do not strip telemetry fields when extending signatures.
- **Transport:** Assume HTTPS in production; do not send PII over mixed content.

### A03 — Injection

- **SQL:** SQLModel/ORM only; no f-string SQL. Raw `text()` DDL in `database.py` is migration-only, never with user input.
- **Commands:** No `os.system` / shell interpolation with portal URLs or user strings.
- **Templates:** Contract markdown uses safe `format_map` / controlled templates—never `eval` or Jinja2 with untrusted template sources.

### A04 — Insecure design

- State machines (`TransactionSessionStatus`) MUST reject invalid transitions (e.g. sign before PDF seal, double-sign same role).
- Fail closed on hash mismatch (**409**), missing PDF (**400**), or unknown transaction (**404**).
- Prefer idempotent, explicit endpoints (`generate-pdf`, `execute-signature`) over ambiguous combined actions.

### A05 — Security misconfiguration

- **CORS:** `CORS_ORIGINS` env allowlist only; do not use `*` with credentials in production.
- **Debug:** Do not enable FastAPI debug tracebacks or Next.js verbose error pages in production builds.
- **Dependencies:** Pin versions in `requirements.txt` / `package-lock.json`; run updates deliberately after tests.

### A06 — Vulnerable and outdated components

- Before adding packages (`reportlab`, playwright, etc.), justify need and scan for known CVEs when upgrading.
- Keep Python/Node runtimes on supported LTS versions in deployment docs.

### A07 — Identification and authentication failures

- Today, signing endpoints are **internal-trust** (no JWT). When auth lands, **every** `POST` mutating transactions/signatures MUST require authenticated context; rate-limit signature attempts.
- Do not store passwords in `signature_telemetry`; store only audit metadata defined in schema.

### A08 — Software and data integrity failures

- Treat `document_hash` as immutable after seal; regenerating PDF MUST produce a new hash and invalidate prior signature intent (document version bump or explicit reset policy).
- **Small, atomic chunked git commits only** after tests pass (see Agents.md "Small commits rule"). Never large monolithic commits. No unsigned artifact commits of `storage/` binaries.

### A09 — Security logging and monitoring failures

- Log signature events at **INFO** with `transaction_id` and role—**never** log full cédula/RNC, tokens, or PDF bytes.
- Scraper telemetry (`ScraperErrorLog`) must not persist secrets from portal HTML.

### A10 — Server-side request forgery (SSRF)

- Portal fetch/scrape URLs MUST be validated against allowed hosts (`remaxrd.com`, known patterns). Reject arbitrary `portal_url` overrides pointing at internal IPs (`127.0.0.1`, `169.254.*`, metadata endpoints).

### Storefront (Next.js) — companion rules

- **XSS:** Prefer React text binding; avoid `dangerouslySetInnerHTML` except for controlled contract preview—and sanitize or restrict to generated markdown pipeline output.
- **CSRF:** When cookies/session auth is added, use SameSite and anti-CSRF tokens on mutating routes.
- **Env:** Only `NEXT_PUBLIC_*` in client bundles; API secrets stay server-side.
- **Zod:** Validate all form payloads client-side **and** rely on FastAPI/Pydantic server-side (never client-only validation).

### Agent checklist (every PR / feature)

1. Threat model the feature in one paragraph (assets, trust boundaries, attackers).
2. Confirm input validation on API + UI.
3. Confirm no new secrets or storage paths leak to git or client.
4. Confirm OWASP-relevant tests (pytest for auth boundaries, hash tamper, invalid state) where applicable.
5. Note known gaps explicitly in feature README **Out of scope** (e.g. “no JWT yet”) rather than silent omission.