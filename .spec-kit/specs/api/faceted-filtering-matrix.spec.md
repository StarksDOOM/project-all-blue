# Spec: Faceted Filtering Matrix & Query Indexing

## Status: SHIPPED
**Roadmap:** STREAM 5 PHASE 2.0  
**Branch:** `feat/stream-5-phase-2-faceted-filtering` ← `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`

---

## 1. Objective

Multi-variable property search (price, beds, baths, type, sector, agency, keyword) with **sub-100ms p95** list queries on indexed facets and **no client request storms** during typing.

---

## 2. Query parameters (GET `/api/v1/properties`)

| Param | Type | SQL boundary |
|-------|------|----------------|
| `source_portal` | string | `source_portal = :v` (indexed) |
| `sector` | string | `sector = :v` (indexed) |
| `keyword` | string | `title ILIKE %v% OR raw_description ILIKE %v%` |
| `price_min` | float | `COALESCE(list_price, price_usd) >= :v` |
| `price_max` | float | `COALESCE(list_price, price_usd) <= :v` |
| `bedrooms_min` | int | `bedrooms >= :v` |
| `bathrooms_min` | float | `bathrooms >= :v` |
| `property_type` | `venta` \| `alquiler` | `raw_description` / `title` patterns |
| `agency` | string | `agent_agency ILIKE %v%` |
| `page`, `limit`, `include_total` | (Phase 1) | unchanged |

**Hard rules:** parameterized SQLAlchemy only; `deleted_at IS NULL` always; single SELECT + optional COUNT; no N+1.

---

## 3. Index boundaries (Postgres)

| Index | Columns (partial `deleted_at IS NULL`) |
|-------|----------------------------------------|
| `ix_properties_faceted_core` | `(source_portal, sector, bedrooms, price_usd)` |
| `ix_properties_faceted_agency` | `(agent_agency, last_modified DESC)` |
| `ix_properties_portal_active_modified` | (Phase 1) retained |

Planner target: index scans on portal+sector+beds+price; agency filter uses agency index.

---

## 4. Storefront

| Module | Role |
|--------|------|
| `hooks/useFilterParams.ts` | URL ↔ filter state (`useSearchParams` + `router.replace`) |
| `hooks/useDebouncedValue.ts` | 300ms debounce for text/range inputs |
| `PropertyFilterPanel.tsx` | Filter UI |
| `PropertyTable.tsx` | Partial skeleton on `isFetching && data` |

**URL keys:** `sector`, `q`, `price_min`, `price_max`, `beds`, `baths`, `type`, `agency`, `page`

---

## 5. Verification

| Gate | Command |
|------|---------|
| API | `pytest tests/test_property_filters.py -q` |
| Build | `cd apps/storefront-next && npm run build` |
| Manual | Change filters → URL updates → one API call after debounce |

---

## 6. Drift policy

New filter fields require: spec table row, `PropertyFilterParams`, `compile_property_filters`, index review, `useFilterParams` serializer.