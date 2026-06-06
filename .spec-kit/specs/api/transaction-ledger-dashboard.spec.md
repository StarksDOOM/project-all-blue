# Spec: Transaction Ledger Dashboard

## Status: SHIPPED
**Roadmap:** STREAM 6 PHASE 1.2  
**Branch:** `feat/stream-6-phase-1.2-transaction-ledger-dashboard` ← `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/transaction-ledger-dashboard/README.md`

---

## 1. Objective

Provide a protected backend query service to retrieve contract data and build a secure Next.js dashboard view for Agents and Admins to monitor real-time transaction lifecycle states.

**In scope**
- `ContractQueryService`: A stateless domain service querying `LegalContract` records outer-joined with `PropertyListing` metadata, filtering by `user_id` when the caller is an `AGENT` and returning all contracts when the caller is an `ADMIN`.
- Endpoint `GET /api/v1/contracts` guarded strictly by `RoleChecker([UserRole.AGENT, UserRole.ADMIN])`.
- Storefront route: `/dashboard/contracts` to show the list of generated contracts.
- Responsive Next.js Data Table component listing: truncated Contract ID, Property Title, Deal Price, Date, and Status Badge.
- Color badges: `executed` (Emerald/Green), `pending_signature` (Amber/Yellow), and `declined` (Rose/Red).
- React Query integration fetching endpoints with authorization header injected.

**Out of scope**
- Bulk actions/deletions on contracts from the dashboard.
- Manual contract status override inputs (handled only by hook callbacks or physical workflows).
- Realtime SSE integration for dashboard list state (triggers only on page refresh/query stale refetch).

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/contracts` | Protected ledger endpoint. Returns `200 OK` with JSON array. Scoped to agent/admin. |

**Response Body (`List[DashboardContractResponse]`):**
```json
[
  {
    "id": "contract-guid",
    "created_at": "2026-06-06T00:00:00Z",
    "status": "executed",
    "property": {
      "title": "Apartamento en Naco",
      "price_usd": 150000.00
    }
  }
]
```

**Models / tables:**
- Reads from `real_estate.legal_contracts` table:
  - `id`: contract identifier.
  - `docusign_status`: mapped to response status.
  - `generated_at`: mapped to response created_at.
  - `property_id`: used to join with properties table.
  - `user_id`: used for agent scoping.
- Reads from `real_estate.properties` table:
  - `title`: property title.
  - `price_usd`: property pricing amount.

---

## 3. Storefront

- **Route**: `app/dashboard/contracts/page.tsx`
- **Component**: Responsive layout using `<Table>` from `@/components/ui/table` to display:
  - `Contract ID`: displayed truncated.
  - `Property Title`: title of the property.
  - `Deal Price`: formatted price (e.g. `US$150,000.00`).
  - `Creation Date`: formatted creation timestamp.
  - `Status`: Badge with custom CSS colors:
    - `executed`: Emerald/Green (`bg-emerald-500/10 text-emerald-500 border-emerald-500/20`)
    - `pending_signature`: Amber/Yellow (`bg-amber-500/10 text-amber-500 border-amber-500/20`)
    - `declined`: Rose/Red (`bg-rose-500/10 text-rose-500 border-rose-500/20`)
- **React Query Hook**: `useQuery` invoking `api.listContracts()` under cache key `['contracts', 'list']`.

---

## 4. Security & boundaries

- **RBAC**: Endpoint `GET /api/v1/contracts` is protected by `RoleChecker([UserRole.AGENT, UserRole.ADMIN])`. A `CLIENT` request must return `403 Forbidden`.
- **Tenant & Scopes**: `AGENT` role requests are scoped to only return contracts where `user_id == credentials.user_id`. `ADMIN` role requests retrieve all contracts.
- **SQL Injection**: Handled safely via SQLModel's ORM compiler (no raw SQL inputs).

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `pytest apps/api-fastapi/tests/test_transaction_ledger.py` |
| Full pytest gate | `cd apps/api-fastapi; .\.venv\Scripts\python.exe -m pytest -q --tb=no` |
| Storefront build | `cd apps/storefront-next; npm run build` |

---

## 6. Drift policy

If implementation diverges from this spec, update spec **or** code in the same PR — never silent drift.
All new classes/modules must maintain 100% PEP 257 docstring compliance.
