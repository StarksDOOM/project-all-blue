# Spec: Multi-Source Lead Magnet Engine

## Status: SHIPPED
**Roadmap:** STREAM 6 PHASE 1.7  
**Branch:** `feat/stream-6-phase-1.7-lead-magnet-engine` ← `develop`  
**Apps:** `apps/api-fastapi/` | `apps/storefront-next/`  
**Feature README:** `docs/features/lead-magnet-engine/README.md`

---

## 1. Objective

Deploy the dynamic Airbnb ROI calculator as a public-facing, ungated lead magnet on dynamic Next.js routes. The engine tracks traffic sources (e.g. ad campaigns, social channels) and gates high-value profit projection metrics behind an email capture form, saving lead states to Postgres.

**In scope**
- Backend: `LeadCapture` database model and table (`real_estate.lead_captures`).
- Backend: stateless database insertion service `LeadDistributionService`.
- Backend: public capture endpoint `POST /api/v1/leads/capture`.
- Frontend: dynamic route `apps/storefront-next/app/invest/[location]/page.tsx`.
- Frontend: client-side search parameter tracking `LeadMagnetWrapper.tsx`.
- Frontend: visual blur gate over Net Profit Projections in `CashBuyerPitchDashboard.tsx` with email capture action.

**Out of scope**
- Active external CRM synchronization or email sending (stubbed out for future phases).
- Dynamic database lookups for sector comps directly on the lead capture model.

---

## 2. API / Data contracts

### Database Table: `real_estate.lead_captures`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` (or `VARCHAR`) | Primary Key | Lead identifier |
| `email` | `VARCHAR` | Non-nullable, Indexed | Captured email address |
| `location_slug` | `VARCHAR` | Non-nullable | Dynamic location slug parameter |
| `traffic_source` | `VARCHAR` | Non-nullable, default 'organic' | Tracking parameter source |
| `simulated_purchase_price` | `DOUBLE PRECISION` | Non-nullable | User slider purchase price |
| `simulated_nightly_rate` | `DOUBLE PRECISION` | Non-nullable | User slider nightly rate |
| `simulated_occupancy` | `DOUBLE PRECISION` | Non-nullable | User slider occupancy (0.0-1.0) |
| `simulated_maintenance` | `DOUBLE PRECISION` | Non-nullable | User slider monthly maintenance |
| `created_at` | `TIMESTAMPTZ` | Non-nullable, default NOW() | Lead timestamp |

### Endpoint: `POST /api/v1/leads/capture`

* **Request Headers**: `Content-Type: application/json`
* **Response Status**: `201 Created`
* **Request JSON Payload**:
```json
{
  "email": "user@example.com",
  "location_slug": "punta-cana",
  "traffic_source": "fb-ad",
  "simulated_purchase_price": 250000.0,
  "simulated_nightly_rate": 150.0,
  "simulated_occupancy": 0.65,
  "simulated_maintenance": 250.0
}
```
* **Response JSON Payload**:
```json
{
  "id": "generated-lead-uuid-string"
}
```

---

## 3. Storefront (if applicable)

### Dynamic Route `/invest/[location]`
- Maps location path parameter to comp search key (e.g. `punta-cana` -> search keyword `Punta Cana`).
- Resolves comps to initialize the dashboard and pass property id downstream.

### Interactive Blur Gate
- All sliders remain interactive.
- "Cash-on-Cash Return" and core metrics (Gross, PM Cost, Monthly Net, Annual NOI) are visible.
- "6 Months", "1 Year", and "3 Years" Net Profit metrics are hidden behind a CSS blur filter.
- Inline form/overlay: "Unlock Full ROI Projections & PDF Prospectus" with Email input.
- Successful submission clears the blur and saves the unlocked state in the session lifecycle (`sessionStorage`).

---

## 4. Security & boundaries

- Rate-limiting or verification stubs for the public capture route.
- Robust Pydantic email validation on the backend.
- State boundary: no authentication required to post to the public capture endpoint.

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `pytest tests/test_lead_capture.py` |
| Full suite | `pytest -q --tb=no` |
| Storefront | `npx tsc --noEmit` |

---

## 6. Drift policy

If implementation diverges from this spec, update spec or code in the same PR — never silent drift.
