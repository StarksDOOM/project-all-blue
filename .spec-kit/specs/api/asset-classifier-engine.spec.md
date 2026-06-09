# Spec: Asset Classifier & Multi-Yield Engine

## Status: DRAFT
**Roadmap:** STREAM 6 PHASE 1.8  
**Branch:** `feat/stream-6-phase-1.8-asset-classifier-engine` ← `develop`  
**Apps:** `apps/api-fastapi/` | `apps/storefront-next/`  
**Feature README:** `docs/features/asset-classifier/README.md`

---

## 1. Objective

This phase introduces automated asset classification to categorize scraped real estate listings by Listing Type (FOR_SALE, FOR_RENT) and Property Type (RESIDENTIAL, COMMERCIAL) upon ingestion. It filters out rental listings from the storefront retail feed (reserving them for acquisition operations) and provides dynamic alternative underwriting calculators (Cap Rates) for LTR (Long-Term Rental) corporate leases and Commercial properties.

**In scope**
- Schema updates in `PropertyListing` (FastAPI/SQLModel) to support `listing_type` and `property_type`.
- Centralized NLP keyword classifier service (`asset_classifier.py`) running during ingestion.
- Centralized database schema migrations via `database.py`.
- Extension of `WholesalePricingEngine` to perform Commercial Cap Rate and LTR Cap Rate calculations.
- Nested response schemas in `WholesaleDealMetrics` for alternative calculations.
- Storefront listing filter to exclude `FOR_RENT` properties.
- Dynamic storefront components: `CommercialYieldDashboard.tsx` for Commercial and segmented toggle within `CashBuyerPitchDashboard.tsx` for LTR/STR Residential.

**Out of scope**
- Automated machine learning classifications beyond robust case-insensitive keyword rules.
- Scraper-level site classification logic (centralized at ingestion layer instead).

---

## 2. API / Data contracts

### Schema Extensions (SQLModel)
Two fields added to `PropertyListing`:
* `listing_type`: `str` (enforced values: `FOR_SALE`, `FOR_RENT`; default: `FOR_SALE`)
* `property_type`: `str` (enforced values: `RESIDENTIAL`, `COMMERCIAL`; default: `RESIDENTIAL`)

### Endpoint: `GET /api/v1/analytics/wholesale/{property_id}`
#### Query Parameters (Additional)
* `monthly_rent_per_sqm`: `float | None` (for Commercial)
* `comm_vacancy_rate`: `float | None` (default: `0.10`)
* `annual_taxes_insurance`: `float | None` (default: `0.0`)
* `monthly_rent`: `float | None` (for LTR)
* `ltr_vacancy_rate`: `float | None` (default: `0.05`)
* `ltr_pm_fee_pct`: `float | None` (default: `0.10`)

#### Response JSON structure extension (Nested objects)
Inside `WholesaleDealMetrics`:
```json
{
  "property_id": "uuid-string",
  "sector": "punta-cana",
  "sector_median_price_per_sqm": 2200.0,
  "auto_emv": 220000.0,
  "mao": 176000.0,
  "assignment_fee": 11000.0,
  "pitch_price": 187000.0,
  "recommended_str_assumptions": {
    "nightly_rate": 169.0,
    "occupancy_pct": 0.45,
    "monthly_maintenance": 150.0
  },
  "str_monthly_gross": 2281.5,
  "str_pm_cost": 456.3,
  "str_monthly_net": 1525.2,
  "str_annual_noi": 18302.4,
  "str_cash_on_cash_pct": 9.79,
  "str_projection_6mo": 9151.2,
  "str_projection_1yr": 18302.4,
  "str_projection_3yr": 54907.2,
  
  "commercial_metrics": {
    "annual_gross_rent": 24000.0,
    "effective_gross_income": 21600.0,
    "annual_noi": 20000.0,
    "cap_rate_pct": 10.7
  },
  
  "ltr_metrics": {
    "annual_gross_rent": 14400.0,
    "effective_gross_rent": 13680.0,
    "operating_expenses": 3240.0,
    "annual_noi": 10440.0,
    "cap_rate_pct": 5.58
  }
}
```

---

## 3. Storefront (if applicable)

- **Feed Filter**: Frontend ignores properties with `listing_type === "FOR_RENT"`.
- **Commercial Dashboard**: Renders `<CommercialYieldDashboard />` when `property_type === "COMMERCIAL"`. Interactive sliders:
  - Expected Rent per SqM
  - Vacancy Rate %
  - Fixed Annual Expenses (Taxes/Insurance)
- **LTR/STR Residential Toggle**: Renders segmented control at the top of `<CashBuyerPitchDashboard />` when `property_type === "RESIDENTIAL"`. Hot-swaps view, state, and formulas between LTR corporate leases and short-term rentals.

---

## 4. Security & boundaries

- Input Validation: Pydantic constraints on query params (`vacancy_rate` between 0.0 and 1.0, positive numeric price inputs).
- Bypassed authentication for local debugging until JWT authentication is fully operational in Phase 5.0.

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| Classifier tests | `pytest tests/test_asset_classifier.py -v` |
| Pricing updates | `pytest tests/test_wholesale_analytics.py -v` |
| Full suite | `pytest -q --tb=short` |
| Storefront check | `npx tsc --noEmit` |

---

## 6. Drift policy

If implementation diverges from this spec, update spec **or** code in the same PR — never silent drift.
