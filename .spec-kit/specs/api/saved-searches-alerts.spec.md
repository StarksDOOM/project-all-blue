# Spec: Saved Searches & Asynchronous Property Match Notification Engine

## Status: SHIPPED
**Roadmap:** STREAM 5 PHASE 3.0  
**Branch:** `feat/stream-5-phase-3-saved-searches-alerts` ← `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/saved-searches-alerts/README.md`

---

## 1. Objective

Persist the exact URL-driven faceted filter matrix (price, sector, beds, baths, type, agency, keyword, portal) as a "Saved Search Alert" owned by a user. On every ingestion pipeline completion for newly inserted PropertyListing rows, synchronously evaluate the new property against all active alerts using the serialized `filters_json` (re-using the same predicate semantics as the Phase 2 faceted engine). Persist structured `SavedSearchMatch` rows for downstream notification (email/SSE etc. future).

**In scope**
- `SavedSearchAlert` SQLModel (id, user_id, title, filters_json JSONB, is_active, timestamps).
- `SavedSearchMatch` SQLModel for audit/matches (alert_id, property_id, matched_at, match_details JSONB).
- `services/search_match_engine.py`: pure `evaluate_property_against_alerts(property: PropertyListing) -> list[SavedSearchMatch]` (or side-effecting write).
- Call site inside `IngestionOrchestrator._bulk_upsert_chunks` (or post-chunk) **only for inserted** rows, after commit.
- POST `/api/v1/saved-searches` + minimal GET/DELETE/PATCH (user_id supplied by client for now).
- Pydantic schema validation mirroring `PropertyFilterParams` (sanitized).
- Storefront: "Guardar Alerta de Búsqueda" button (Bell icon) in `PropertyFilterPanel` — only rendered when `appliedFilters` differ from `DEFAULT_PROPERTY_FILTERS` (active matrix).
- `useCreateSearchAlert.ts` (TanStack useMutation): reads live state via `useFilterParams`, opens shadcn `<Dialog>` for title, POSTs canonical subset, invalidates list query.
- `/dashboard/alerts/page.tsx`: cards per alert showing humanized filter chips (from `filters_json`), is_active toggle (PATCH), delete.
- Schema DDL via `ensure_saved_searches_schema()` (additive, idempotent).
- Python predicate re-implementation for match (no SQL per-property in hot path; consistent with `compile_property_filters`).

**Out of scope**
- Real delivery (email, push, SSE notification fan-out) — only persistence of matches.
- Ownership/authz enforcement (no JWT; client provides `user_id`; document gap per A07).
- Deduplication of duplicate matches for same (alert, property).
- Rate limits, title uniqueness, max alerts per user.
- UI for viewing match history or "new matches" badge (future).
- Backfill of matches for pre-existing properties.
- Changes to Phase 2 filter compilation or indices.

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/saved-searches` | Body: `{user_id, title, filters: PropertyFilterParamsSubset}`. Returns 201 with alert. Server re-validates `filters` via `PropertyFilterParams`. |
| GET | `/api/v1/saved-searches?user_id=...` | Returns `{data: SavedSearchAlert[]}` (include inactive; order created_at desc). |
| PATCH | `/api/v1/saved-searches/{id}` | Body: `{is_active?: bool, title?: str}` (owner trust via user_id). |
| DELETE | `/api/v1/saved-searches/{id}` | Hard delete (or soft). |

**Models / tables (real_estate schema):**

```python
class SavedSearchAlert(SQLModel, table=True):
    __tablename__ = "saved_search_alerts"
    __table_args__ = {"schema": "real_estate"}

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(index=True)  # UUID string; placeholder until auth
    title: str = Field(max_length=80)
    filters_json: Dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    last_matched_at: Optional[datetime] = Field(default=None, nullable=True)

class SavedSearchMatch(SQLModel, table=True):
    __tablename__ = "saved_search_matches"
    __table_args__ = {"schema": "real_estate"}

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    saved_search_alert_id: str = Field(foreign_key="real_estate.saved_search_alerts.id", index=True)
    property_id: str = Field(foreign_key="real_estate.properties.id", index=True)
    matched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    match_details: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
```

**filters_json serialization payload (example):**
```json
{
  "source_portal": "remaxrd",
  "sector": "Piantini",
  "price_min": 180000,
  "price_max": 450000,
  "bedrooms_min": 2,
  "bathrooms_min": 1.5,
  "property_type": "venta",
  "agency": "Remax Premium",
  "keyword": "piscina"
}
```
- Page, limit, and transient UI state **never** stored.
- Server must accept + re-validate against `PropertyFilterParams` model (reuse validators for strip, price_max >= min).

**Match evaluation criteria (python equivalent of Phase 2 SQL):**
- All non-null filter fields must match with AND semantics.
- `keyword`: ilike substring on title OR raw_description (case-insensitive).
- `property_type`: special case "venta" / "alquiler" via description/title patterns (see `compile...`).
- Effective price: `COALESCE(list_price, price_usd)`.
- Always only consider `is_active=true` alerts + `deleted_at IS NULL` properties (though new props are active).
- On match: write one `SavedSearchMatch` with `match_details = {"matched_on": ["sector", "price_min", ...], "snapshot": {"price": ..., "sector": ...}}`.

---

## 3. Storefront (if applicable)

- **Components / pages:**
  - `app/hooks/useCreateSearchAlert.ts`
  - `app/components/properties/PropertyFilterPanel.tsx` (add button in actions row)
  - `app/components/properties/PropertyTable.tsx` (consume hook + forward `onSaveAlert` prop)
  - `app/dashboard/alerts/page.tsx` (new; uses cards + `useQuery` + mutations)
- **React Query keys:** extend `savedSearchKeys` in `lib/query-keys.ts`
- **API client:** add `createSavedSearchAlert`, `listSavedSearchAlerts`, `updateSavedSearchAlert`, `deleteSavedSearchAlert` in `lib/api.ts` (or `api.properties.ts`)
- **Types:** `SavedSearchAlert`, `SavedSearchMatch` (light), `CreateSavedSearchPayload` in `lib/types.ts`
- **Dialog:** Controlled shadcn `Dialog` + `Input` + `Button` for title (no heavy RHF needed for single field). On success: toast (if available) or simple UI, invalidate `savedSearchKeys.all`.

**Active filter detection (for button visibility):**
```ts
const hasActiveFilters = 
  filters.sector ||
  filters.keyword ||
  filters.price_min != null ||
  filters.price_max != null ||
  filters.bedrooms_min != null ||
  filters.bathrooms_min != null ||
  filters.property_type ||
  filters.agency;
```
Only show if `hasActiveFilters && onSaveAlert`.

**URL state remains source of truth:** save captures `appliedFilters` at click time (post-debounce).

---

## 4. Security & boundaries

- **Server-side validation (Pydantic + SQLModel):** All inbound `filters` re-parsed through `PropertyFilterParams` (sanitizes strings, enforces ranges, price order). Reject invalid with 400. `filters_json` stored as-is after validation.
- **Auth gap (documented):** `user_id` is blindly trusted from client payload / query. No row-level ownership check on GET/PATCH/DELETE. **Out of scope until JWT/tenant binding (A07).** Return 404 not 403 on not-found to avoid enum.
- **No injection:** No user strings in SQL for matching (python predicate only). `JSONB` used safely via SQLModel.
- **Ingestion thread safety:** Evaluator runs after chunk commit in the background thread (no long tx). Use fresh `Session` or passed session for alert reads + match writes. Keep fast (assume <100 active alerts total in v1).
- **Data minimization:** `match_details` stores only matched criteria + minimal snapshot (price/sector); no raw PII.
- **Storefront:** Zod not primary — server Pydantic is authoritative. No secrets in `NEXT_PUBLIC_*`.
- **OWASP notes:** A01 (authz gap noted), A03 (no SQLi via predicates), A07 (gap noted in README), A08 (immutable match rows).

---

## 5. File layout & code changes (blueprint)

**New files:**
- `.spec-kit/specs/api/saved-searches-alerts.spec.md` (this)
- `docs/features/saved-searches-alerts/README.md`
- `apps/api-fastapi/schemas/saved_searches.py`
- `apps/api-fastapi/services/search_match_engine.py`
- `apps/api-fastapi/routers/saved_searches.py`
- `apps/storefront-next/app/hooks/useCreateSearchAlert.ts`
- `apps/storefront-next/app/dashboard/alerts/page.tsx`
- `apps/storefront-next/app/dashboard/alerts/layout.tsx` (optional minimal)

**Modified files:**
- `apps/api-fastapi/models.py` — add two SQLModel classes + imports (uuid, JSONB, datetime)
- `apps/api-fastapi/database.py` — add `ensure_saved_searches_schema()` + tables/indexes; update docstring
- `apps/api-fastapi/main.py` — call ensure_ in lifespan; `from routers import ... saved_searches`
- `apps/api-fastapi/services/sync_service.py` — import engine; after inserted rows in `_bulk_upsert_chunks` / `_upsert_chunk` success path, for each inserted listing: `evaluate_property_against_alerts(listing, db_session)`
- `apps/api-fastapi/routers/properties.py` (optional minor if sharing filter types)
- `apps/api-fastapi/tests/conftest.py` — ensure call for test DB (additive)
- `apps/storefront-next/app/lib/types.ts` — add interfaces
- `apps/storefront-next/app/lib/query-keys.ts` — `savedSearchKeys`
- `apps/storefront-next/app/lib/api.ts` — add 4 client fns + types
- `apps/storefront-next/app/components/properties/PropertyFilterPanel.tsx` — add prop `onSaveAlert?: () => void`; render high-vis Button + Bell in actions div when active
- `apps/storefront-next/app/components/properties/PropertyTable.tsx` — import+call useCreate..., pass prop down to all 3 panel usages
- `.spec-kit/README.md` — register new row + extend STREAM 5 roadmap

**Test additions (recommended for gate):**
- `apps/api-fastapi/tests/test_saved_searches_alerts.py` (model roundtrip, evaluate matches on sample prop, endpoint 201/400)
- Storefront: vitest for hook if pure (or build covers)

---

## 6. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `cd apps/api-fastapi; .\.venv\Scripts\python.exe -m pytest tests/test_property_filters.py tests/test_saved_searches_alerts.py -q --tb=no` (or full) |
| Storefront | `cd apps/storefront-next; npm test -- --run && npm run build` |
| Ingestion integration | Manual: trigger-crawl a portal that yields a new property whose attrs fall inside an active saved alert → inspect `saved_search_matches` row created with correct details |
| Manual success | 1. Apply 2+ filters on / → "Guardar Alerta..." appears → click → title prompt → save succeeds. 2. Visit /dashboard/alerts → card shows chips for sector/price/beds + toggle works + delete works. 3. Reproduce match via ingestion. |
| CRG | `C:\Python313\python.exe -m code_review_graph update` (post-edit) |

**No** memory/session file updates until Manual Success + all gates green.

**Pre-merge:** clean tree (`git status --porcelain` empty), tests zero-fail in same session, user "Go" for staging.

---

## 7. Drift policy

If implementation diverges from this spec (e.g. different table names, calling evaluate on *updated* rows too, client-only filter storage, new endpoints), update spec **or** code in same change — never silent drift. New filter dimension requires update to `PropertyFilterParams`, predicate in match engine, serialization in hook, and this spec table.

Phase 3 builds directly on Phase 2 `PropertyFilterParams` + `useFilterParams` + `compile_property_filters` semantics — any change to those must propagate here.
