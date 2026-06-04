# Spec: Outbound Notification Delivery Engine & Match History Pipeline

## Status: DRAFT
**Roadmap:** STREAM 5 PHASE 4.0  
**Branch:** `feat/stream-5-phase-4-outbound-notification-delivery` ← `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/outbound-notification-delivery/README.md`

**CRG Framework Baseline Note (per monitoring directive):** Architectural baseline remains at 7 tracked structural abstractions (IngestionOrchestrator, SearchMatchEngine, DriverFactory, BaseDriver + 2 concretes, BaseScraperDriver). Any new class introduced in this phase (e.g. NotificationCompiler, NotificationDispatcher) **must strictly avoid session-passing orchestrator creep** — no new long-lived stateful orchestrators that duplicate the pattern; use BackgroundTasks for dispatch, keep compilers pure/stateless where possible, prefer composition over inheritance for delivery concerns. Re-assess formalization only via CRG signals as documented in engineering-directives.md.

---

## 1. Objective

Extend the saved-search match pipeline (Phase 3) so that every successful write of a `SavedSearchMatch` automatically triggers an asynchronous, transactional email notification. The email must be a personalized, responsive HTML alert (via Jinja2) containing key property metadata, with reliable delivery status tracking, retry semantics, and a transparent history view in the dashboard — all without blocking the ingestion or match write transaction.

**In scope**
- Extend or pair `SavedSearchMatch` with delivery state tracking (status enum, sent_at, retry_count, error_message).
- `NotificationCompiler` class (Jinja2 rendering, currency, image fallbacks, secure templates).
- `NotificationDispatcher` class (BackgroundTasks integration, email client stub for SES/Resend, defensive try/except + log updates).
- New/ extended endpoint `GET /api/v1/saved-searches/{id}/matches` for history.
- Dashboard expansion on /dashboard/alerts with collapsible "Ver Propiedades Encontradas", quick-cards showing thumbnail/price/status badge + link to /properties/[id].
- Full adherence to Python OOP & PEP 257 Documentation Standards (encapsulated classes, comprehensive docstrings).
- CRG monitoring: log baseline, avoid creep.

**Out of scope**
- Actual production email provider credentials or live sending (stub + interface only).
- Push notifications or other channels (future).
- Full pagination/sorting on match history (basic list sufficient).
- Backfilling notifications for pre-existing matches.
- JWT auth for user_id (still documented gap).

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/saved-searches/{alert_id}/matches` | Returns list of matches + delivery status for the alert. Requires user_id query for now. |
| (internal) | N/A | Match write side-effect triggers BackgroundTasks for dispatch. |

**Models / tables:**

Extend `SavedSearchMatch` or add `NotificationDeliveryLog` (prefer clean related table or columns on match for simplicity per requirements):

- `delivery_status`: Enum "pending" | "sent" | "failed"
- `sent_at`: Optional[datetime]
- `retry_count`: int = 0
- `error_message`: Optional[str]

Optimized partial index on pending deliveries.

**Notification status enum:** "pending", "sent", "failed" (string enum in SQLModel/Pydantic).

**Class interfaces (OOP + docs required):**
- `class NotificationCompiler:` — __init__ with template env, compile(property_data: dict, alert_title: str) -> str (HTML)
- `class NotificationDispatcher:` — __init__ with email client, dispatch(rendered_html: str, recipient: str, match_id: str, session: Session) -> None ; uses BackgroundTasks.

Jinja2 template hierarchy: base_email.html (responsive layout, styles) + property_alert.html (extends, with blocks for image/price/location/button). Secure: no user-controlled templates, autoescape on, limited globals.

Error-handling retry thresholds: max 3 retries, backoff in dispatcher stub, log on fail.

---

## 3. Storefront (if applicable)

- Routes / components: Expand `app/dashboard/alerts/page.tsx` (or new sub component `MatchHistoryDrawer.tsx`); collapsible per alert card.
- New fetch: useQuery for matches per alert id.
- React Query keys: extend `savedSearchKeys` with `matches: (alertId: string) => ...`
- Dynamic cards: thumbnail (with fallback), price (formatted), status badge (color coded: green sent, amber pending, red failed), link to property detail.
- Typing: new `SavedSearchMatchWithDelivery` interface in types.ts.

---

## 4. Security & boundaries

- Server-side validation: Pydantic for any new payloads; SQLModel for status enum.
- Transaction perimeters: Match write + status init in one tx if possible; dispatch is fire-and-forget via BackgroundTasks (after commit). Never block ingestion.
- Email: No secrets in code; use env for provider keys. Jinja2 autoescape to prevent XSS in rendered HTML.
- Auth gap (documented): user_id still client-supplied; no ownership enforcement on match history yet.
- No new raw SQL; use SQLModel.
- Retry logic must not leak PII in error_message (truncate/sanitize).

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `cd apps/api-fastapi; .\.venv\Scripts\python.exe -m pytest tests/test_saved_searches_alerts.py tests/test_outbound_notifications.py -q` (add test for compiler, dispatcher stub, endpoint, status transitions) |
| Storefront | `cd apps/storefront-next; npm test -- --run && npm run build` |
| Manual | Apply filter -> save alert -> trigger ingestion that produces match -> verify email HTML rendered in log or stub, status "sent"/"pending" in dashboard, clickable card goes to property detail. Check no tx slowdown. |
| CRG / Framework | Re-run CRG update + minimal_context "assess oop framework layer" + count abstractions (must stay disciplined, no session-passing creep beyond baseline 7). |

**No** memory/session file updates until Manual Success.

---

## 6. Drift policy

If implementation diverges (e.g. new session-passing orchestrator class, missing PEP257 docs on new classes, different enum names, no Jinja2 compiler class, direct email calls in match write instead of BackgroundTasks), update spec or code in same change — never silent drift.

All new classes must be encapsulated OOP per the standing directive. Use CRG to monitor if this phase pushes abstraction count or patterns that trigger formalization assessment.

---

## 7. Implementation Notes (for agent)

- Create spec + feature README + register in index **before** writing any production code for phase4.
- Hook dispatch preferably after match commit in search_match_engine.evaluate (or via event in sync).
- Jinja2: use Environment(autoescape=True), load from package or templates/ dir.
- Email stub: interface like `class EmailClient: async def send(to: str, subject: str, html: str) -> bool`
- Update SavedSearchMatch model with new fields + index.
- Add to database ensure_ function.
- For history endpoint, join or query matches for alert, include delivery fields.
- Dashboard: use existing Card, Badge, perhaps Accordion or state for collapsible. Fetch on alert expand if possible.
- Comply with CRG monitoring: after edits, update CRG; in reasoning log baseline and confirm no creep.

This spec supersedes any prior description for zero-drift.