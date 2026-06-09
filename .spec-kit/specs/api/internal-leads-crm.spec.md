# Spec: Internal Leads CRM Feed

## Status: SHIPPED
**Roadmap:** STREAM 6 PHASE 1.7.1
**Branch:** `feat/stream-6-phase-1.7.1-internal-leads-crm` ← `develop`
**Apps:** `apps/api-fastapi/` | `apps/storefront-next/`
**Feature README:** `docs/features/internal-leads-crm/README.md`

---

## 1. Objective

Expose the captured lead magnet data (from Phase 1.7) to the internal sales team via a
secure paginated REST endpoint and a high-density CRM data grid inside the agent dashboard.

**In scope**
- Backend: `GET /api/v1/leads` endpoint — paginated list of `LeadCapture` records sorted newest first.
- Backend: `LeadCaptureRow` and `LeadCaptureListResponse` Pydantic schemas.
- Frontend: `api.getLeads()` fetch wrapper in `api.ts`.
- Frontend: `leadKeys` cache token in `query-keys.ts`.
- Frontend: `LeadCaptureRecord` and `LeadsListResponse` TypeScript types in `types.ts`.
- Frontend: Internal agent dashboard route `app/dashboard/leads/page.tsx`.
- Frontend: `LeadsDataGrid.tsx` high-density client component.

**Out of scope**
- RBAC auth guard on `GET /api/v1/leads` (deferred to Phase 5.0 RBAC infrastructure).
- Lead status management, CRM pipeline stages, or external CRM sync.
- Email outreach from the dashboard.

---

## 2. API / Data Contracts

### Endpoint: `GET /api/v1/leads`

- **Query Params**: `skip: int = 0`, `limit: int = 100` (max 500)
- **Response Status**: `200 OK`
- **Response JSON**:
```json
{
  "data": [
    {
      "id": "uuid-string",
      "email": "investor@example.com",
      "location_slug": "punta-cana",
      "traffic_source": "fb-ad",
      "simulated_purchase_price": 285000.0,
      "simulated_nightly_rate": 180.0,
      "simulated_occupancy": 0.65,
      "simulated_maintenance": 220.0,
      "created_at": "2026-06-09T04:00:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```
- **Ordering**: `created_at DESC` (newest first).
- **Auth**: No guard at this stage — consistent with `GET /api/v1/contracts` pattern.

---

## 3. Storefront (if applicable)

### Route: `/dashboard/leads`
- Role-gated client component (agent or admin only, mirrors `/dashboard/contracts` pattern).
- Header with page title, Refresh button, and Volver button.
- Renders `<LeadsDataGrid />` with loaded lead records.

### LeadsDataGrid Columns
| Column | Content |
|--------|---------|
| Date Captured | `created_at` formatted with `es-DO` locale |
| Email | Monospace, selectable |
| Landing Context | `/invest/{location_slug}` + Source badge |
| Simulation State | Purchase price · Nightly rate · Occupancy pills |

---

## 4. Security & Boundaries

- No PII exposed beyond what agents already access in the dashboard.
- Auth guard deferred to Phase 5.0; endpoint is internal-convention-only for now.
- `limit` capped server-side at 500 to prevent unbounded queries.

---

## 5. Verification Gates

| Gate | Command / Check |
|------|----------------|
| Lead list tests | `pytest tests/test_lead_capture.py -v` |
| Full suite | `pytest -q --tb=short` |
| Storefront types | `npx tsc --noEmit` |

---

## 6. Drift Policy

If implementation diverges from this spec, update spec or code in the same PR — never silent drift.
