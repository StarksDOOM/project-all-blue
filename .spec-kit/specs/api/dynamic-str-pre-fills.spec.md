# Spec: Dynamic STR Pre-fills

## Status: DRAFT
**Roadmap:** STREAM 6 PHASE 1.6.1
**Branch:** `feat/stream-6-phase-1.6-airbnb-roi-engine` ← `develop`
**Apps:** `apps/api-fastapi/` | `apps/storefront-next/`
**Feature README:** `docs/features/airbnb-roi-engine/README.md`

---

## 1. Objective

Provide dynamic defaults for Short-Term Rental (STR) variables on the Cash Buyer Pitch Dashboard. Instead of forcing manual slider inputs on mount, automatically pre-fill Nightly Rate, Occupancy, and Maintenance based on the listing's province/sector text and square meters using 2026 DR market norms.

**In scope**
- Backend: `StrDefaultPredictor` class matching location strings and sizes to defaults.
- Backend: nested `recommended_str_assumptions` block inside `WholesaleDealMetrics` response.
- Frontend: hydration of React slider states on initial mount.

**Out of scope**
- Dynamic database lookups for sector-specific STR performance.

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/analytics/wholesale/{property_id}` | Return `recommended_str_assumptions` nested object |

### Schema structure (recommended_str_assumptions)

```json
"recommended_str_assumptions": {
  "nightly_rate": 120.0,
  "occupancy_pct": 0.40,
  "monthly_maintenance": 150.0
}
```

### Prediction rules (spec-locked)

1. **Maintenance (monthly_maintenance)**:
   - Formula: `square_meters × 2.50`
   - Fallback: `$150.00` if size <= 0 or None.
2. **ADR (nightly_rate) and Occupancy (occupancy_pct)** based on case-insensitive substring match of property `province` or `sector`:
   - `"punta cana"` or `"altagracia"` -> ADR `$169.00`, Occupancy `0.45` (45%)
   - `"las terrenas"` or `"samana"` -> ADR `$234.00`, Occupancy `0.40` (40%)
   - `"santo domingo"` -> ADR `$80.00`, Occupancy `0.40` (40%)
   - Fallback -> ADR `$120.00`, Occupancy `0.40` (40%)

---

## 3. Storefront (if applicable)

- **React state hydration**: Upon fetching `wholesaleData` for the property, initialize/update state hooks using `wholesaleData.recommended_str_assumptions`.
- Sliders and debounced query flow remain fully interactive (user edits override defaults).

---

## 4. Security & boundaries

- The values returned are purely read-only hints computed on-the-fly. No new write boundaries are introduced.

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `pytest tests/test_str_roi_engine.py` (verify predictor & endpoint shape) |
| Storefront | `npm run build` |
| Manual | Verify sliders pre-fill to Santo Domingo/Punta Cana defaults |

---

## 6. Drift policy

If implementation diverges from this spec, update spec **or** code in the same PR — never silent drift.
