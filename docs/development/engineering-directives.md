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

## Code comments (required where necessary)

When writing or changing production code in this repo:

- Add **module-level** docstrings for packages and orchestration entry points (`services/`, `scrapers/drivers/`, routers).
- Add **class and public method** docstrings (purpose, inputs, outputs, raised errors, side effects).
- Add **inline comments** only for non-obvious logic: business rules (e.g. DOP/USD, portal keys), concurrency, retries, idempotency/upsert keys, security boundaries, and integration quirks (AdsPower, pagination fields).
- Do **not** narrate obvious code (`# increment i`). Prefer clearer names over comments when that suffices.
- Keep comments accurate when behavior changes; remove stale comments in the same edit.
- Match existing file style (Python: PEP 257; TypeScript: JSDoc on exported APIs).

Spec-kit and walkthroughs do not replace in-code documentation for maintainers.

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
- Chunked git commits only after tests pass; no unsigned artifact commits of `storage/` binaries.

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