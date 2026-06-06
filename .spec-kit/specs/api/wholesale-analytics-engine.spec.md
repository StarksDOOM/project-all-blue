# Spec: Wholesale Pricing & Analytics Engine

## Status: DRAFT
**Roadmap:** STREAM 6 PHASE 1.3  
**Branch:** `feat/stream-6-phase-1.3-wholesale-analytics-engine` ← `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Abstraction delta:** 15 → 16 (adds `WholesalePricingEngine`)

---

## Problem

Agents need a fast, automated deal analysis to determine if a property qualifies for a
wholesale assignment and at what price. Manual calculation is error-prone and inconsistent.
The system must derive ARV from live sector data and compute MAO/pitch price using
hardcoded wholesale heuristics — without exposing the assignment margin to Agents.

---

## Outcomes

1. `WholesalePricingEngine` computes ARV, Repairs, MAO, Assignment Fee, and Pitch Price
   deterministically from DB sector averages and fixed multipliers.
2. `GET /api/v1/analytics/wholesale/{property_id}` is guarded by RBAC (AGENT + ADMIN only).
3. Frontend property detail page renders a role-gated "Guía de Wholesaling" card:
   - AGENT: sees MAO + Pitch Price only (no margin disclosed).
   - ADMIN: sees full breakdown including sector median, ARV, repairs, and assignment fee.
4. All existing 87 tests pass with 0 regressions; 10 new assertions added.

---

## Engine Interface Contract

### Class: `WholesalePricingEngine`

**Module:** `apps/api-fastapi/services/wholesale_pricing_engine.py`  
**Pattern:** Stateless domain service (no instance state, no constructor args).

#### Method: `calculate_deal_metrics`

```
calculate_deal_metrics(property_id: str, session: Session) -> WholesaleDealMetrics
```

**Algorithm (invariants — must not drift):**

| Step | Formula | Raises |
|---|---|---|
| Load target | `SELECT * FROM propertylisting WHERE id = property_id` | `404` if not found or `is_active = false` |
| Sector peers | `SELECT price_usd, square_meters FROM propertylisting WHERE sector = target.sector AND is_active = true` | `422` if zero peers |
| `sector_median_price_per_sqm` | `median(price_usd / square_meters)` for all active peers (target included) | — |
| `auto_arv` | `sector_median_price_per_sqm × target.square_meters` | — |
| `estimated_repairs` | `target.square_meters × 150.0` | — |
| `mao` | `(auto_arv × 0.70) − estimated_repairs` | — |
| `assignment_fee` | `max(auto_arv × 0.05, 5000.0)` | — |
| `pitch_price` | `mao + assignment_fee` | — |

**Thread-safety:** Stateless; each call receives its own `session`. Safe for concurrent use.  
**Side effects:** None (read-only queries only).

---

## API Contract

### `GET /api/v1/analytics/wholesale/{property_id}`

**Auth:** `Depends(RoleChecker([UserRole.AGENT, UserRole.ADMIN]))` — CLIENT returns 403.

**200 Response:**
```json
{
  "property_id": "string",
  "sector": "string",
  "sector_median_price_per_sqm": 1234.56,
  "auto_arv": 98765.43,
  "estimated_repairs": 12000.00,
  "mao": 57135.80,
  "assignment_fee": 5000.00,
  "pitch_price": 62135.80
}
```

**Error codes:**
- `403` — CLIENT role (or unauthenticated).
- `404` — `property_id` not found or inactive.
- `422` — Sector has zero active peers (insufficient data).

---

## Frontend Contract

**File:** `apps/storefront-next/app/components/properties/PropertyDetailClient.tsx`  
**Component added:** `WholesaleGuideCard` (inline or extracted client component)

### AGENT view (role === "agent")
- Label: **Guía de Wholesaling**
- Shows: "Oferta Máxima al Vendedor" (MAO) + "Precio para Inversionista" (Pitch Price)
- Hides: sector median, ARV, repairs, assignment fee

### ADMIN view (role === "admin")
- Label: **Guía de Wholesaling — Desglose Completo**
- Shows: all 7 fields (sector, median $/m², ARV, repairs, MAO, assignment fee, pitch price)

### CLIENT / unauthenticated
- Card not rendered; `useQuery` not triggered.

---

## Test Matrix

| Test | Assertion |
|---|---|
| `test_engine_arv_calculation` | `auto_arv == median × sqm` with ≥2 real DB peers |
| `test_engine_mao_formula` | `mao == (arv × 0.70) − repairs` |
| `test_engine_assignment_fee_percentage` | Fee = `arv × 0.05` when result ≥ $5000 |
| `test_engine_assignment_fee_floor` | Fee = `5000.0` when `arv × 0.05 < 5000` |
| `test_engine_pitch_price` | `pitch_price == mao + assignment_fee` |
| `test_route_agent_200` | AGENT JWT → 200, correct JSON keys |
| `test_route_admin_200` | ADMIN JWT → 200, correct JSON keys |
| `test_route_client_403` | CLIENT JWT → 403 |
| `test_route_unknown_property_404` | Non-existent property_id → 404 |
| `test_engine_single_sector_peer` | 1 active sector listing → no crash, valid result |

**Zero mocks** (integration tests). Unit-style engine tests create real `PropertyListing` rows.

---

## Drift Policy

- Formula constants (0.70, 150.0, 0.05, 5000.0) are hardcoded invariants. Any change requires a spec update and user approval.
- Field source: `price_usd` (always populated) used for sector median. `list_price` is ignored.
- Zero-peer behaviour: `422 Unprocessable Entity` — no silent fallback.
