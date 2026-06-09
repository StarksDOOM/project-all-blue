# Spec: Yield Protection & UI State Fix

## Status: SHIPPED
**Roadmap:** STREAM 6 PHASE 1.8.1  
**Branch:** `feat/stream-6-phase-1.8.1-yield-protection-patch` ← `develop`  
**Apps:** `apps/api-fastapi/` | `apps/storefront-next/`  
**Feature README:** `docs/features/yield-protection/README.md`

---

## 1. Objective

This phase introduces normalization for predictive maintenance to prevent artificial negative default NOI projections caused by dirty scraper data, repairs the unresponsive LTR/STR toggle on the storefront cash buyer dashboard, implements a smart dashboard strategy pivot to auto-select the most profitable strategy, and filters out toxic deals (properties with negative default NOI across both STR and LTR) from the storefront feed.

**In scope**
- Predictive maintenance sanity cap of `$400.00` in `StrDefaultPredictor.predict_defaults()`.
- Baseline maintenance cap applying to both STR and LTR calculations.
- Responsive tab switching logic (`activeTab` state) in `CashBuyerPitchDashboard.tsx`.
- Initialization pivot logic to pre-select LTR if STR default NOI is negative and LTR is positive.
- Storefront feed filter in `list_properties_paginated` to exclude toxic deals.

**Out of scope**
- Modifying underlying scraped property fields on the database.
- Filtering toxic properties from admin CRM grids or direct ID page loads.

---

## 2. API / Data contracts

No changes to API payloads. The `WholesaleDealMetrics` schema is unchanged.

### Data Filtering logic (storefront list feed)
Exclude any `PropertyListing` where:
- Default STR NOI < 0 AND default LTR NOI < 0.
Where default calculations use predictions from `StrDefaultPredictor.predict_defaults()`.

---

## 3. Storefront (if applicable)

- Component: `CashBuyerPitchDashboard.tsx`
  - Fixed click handlers updating local state (`activeTab`).
  - Swapped slider inputs and bottom metrics correctly based on `activeTab`.
  - Smart strategy pivot setting initial `activeTab` to `"LTR"` if baseline STR NOI is negative and LTR is positive.

---

## 4. Security & boundaries

- Normalization is enforced server-side.
- State checks are validated using TypeScript on the frontend.

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `pytest tests/test_str_roi_engine.py` |
| Storefront | `npx tsc --noEmit` |
| Manual | Verify toggle functionality and property filtering |

---

## 6. Drift policy

If implementation diverges from this spec, update spec **or** code in the same PR — never silent drift.
