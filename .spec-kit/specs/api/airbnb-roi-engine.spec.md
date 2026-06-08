# Spec: Airbnb ROI & Pitch Engine

## Status: DRAFT
**Roadmap:** STREAM 6 PHASE 1.6
**Branch:** `feat/stream-6-phase-1.6-airbnb-roi-engine` ← `develop`
**Apps:** `apps/api-fastapi/` | `apps/storefront-next/`
**Feature README:** `docs/features/airbnb-roi-engine/README.md`

---

## 1. Objective

Extend the existing `WholesalePricingEngine` to calculate Short-Term Rental (STR) yields so that Agents can pitch "Cash-on-Cash Return" projections directly to U.S. cash buyers viewing Dominican Republic properties.

**In scope**
- Backend: new `calculate_str_metrics()` method on `WholesalePricingEngine`
- Backend: optional STR query params on `GET /api/v1/analytics/wholesale/{property_id}`
- Backend: extended `WholesaleDealMetrics` response schema (backwards-compatible optional fields)
- Frontend: interactive `CashBuyerPitchDashboard` component with sliders and projection cards
- Unit tests for STR formula correctness

**Out of scope**
- Historical Airbnb data ingestion or scraping
- Automated occupancy estimation from market data
- Multi-currency projections (all USD)
- Tax/depreciation modelling
- User-specific saved STR assumptions

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/analytics/wholesale/{property_id}` | Existing endpoint; add optional query params |

### New query parameters (all optional)

| Param | Type | Validation | Default | Description |
|-------|------|------------|---------|-------------|
| `nightly_rate` | `float` | `ge=0` | `None` | Average nightly STR rate (USD) |
| `occupancy_pct` | `float` | `ge=0, le=1.0` | `None` | Occupancy ratio 0.0–1.0 |
| `monthly_hoa` | `float` | `ge=0` | `None` | Monthly HOA/maintenance dues (USD) |

### Extended response fields (populated only when `nightly_rate` is supplied)

| Field | Type | Formula |
|-------|------|---------|
| `str_monthly_gross` | `float \| null` | `nightly_rate × 30 × occupancy_pct` |
| `str_pm_cost` | `float \| null` | `str_monthly_gross × 0.20` |
| `str_monthly_net` | `float \| null` | `str_monthly_gross − str_pm_cost − monthly_hoa − 150` |
| `str_annual_noi` | `float \| null` | `str_monthly_net × 12` |
| `str_cash_on_cash_pct` | `float \| null` | `(str_annual_noi / pitch_price) × 100` |
| `str_projection_6mo` | `float \| null` | `str_monthly_net × 6` |
| `str_projection_1yr` | `float \| null` | `str_monthly_net × 12` |
| `str_projection_3yr` | `float \| null` | `str_monthly_net × 36` |

### Spec-locked constants

| Constant | Value | Description |
|----------|-------|-------------|
| `_PM_FEE_RATIO` | `0.20` | Property management fee (20% of gross) |
| `_MAINTENANCE_RESERVE` | `150.0` | Monthly maintenance reserve (USD flat) |

**Models / tables:** No new tables or migrations. All STR metrics are computed on-the-fly from user-supplied query params.

---

## 3. Storefront (if applicable)

- **Component:** `CashBuyerPitchDashboard.tsx` — placed below existing "Guía de Oferta" card in `PropertyDetailClient.tsx`
- **Controls:** Nightly Rate slider ($0–$500), Occupancy slider (0%–100%), Monthly HOA input ($0–$2000)
- **Display:** Metric cards for Monthly Gross, Monthly Net, Annual NOI, Cash-on-Cash %, and 6mo/1yr/3yr projections
- **Behaviour:** Debounced onChange (300ms) re-fetches wholesale analytics with STR params
- **React Query keys:** `analyticsKeys.wholesale(propertyBluId)` — keyed with STR params to avoid stale cache

---

## 4. Security & boundaries

- Server-side validation: Pydantic `Query` constraints (`ge=0`, `le=1.0`) enforce non-negative inputs
- No new write operations or database mutations
- Auth (current): RBAC check (`AGENT`/`ADMIN`) on analytics endpoint — currently bypassed for QA (documented in Phase 1.3 spec as Out of scope until JWT ships)

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `pytest tests/test_str_roi_engine.py` |
| Full suite | `pytest -q --tb=short` (all ~100+ tests pass, 0 failures) |
| Backwards compat | Call endpoint without STR params → response unchanged from Phase 1.3 |
| Manual | Operator confirms STR dashboard renders and projections are mathematically correct on `develop` before SHIPPED |

**No** memory/session file updates until Manual Success.

---

## 6. Drift policy

If implementation diverges from this spec, update spec **or** code in the same PR — never silent drift.
