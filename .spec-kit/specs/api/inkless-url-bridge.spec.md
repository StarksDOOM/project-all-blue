# Spec: Inkless Signature URL Bridge

## Status: SHIPPED
**Roadmap:** STREAM 6 PHASE 1.8.2  
**Branch:** `feat/stream-6-phase-1.8.2-inkless-url-bridge` ← `develop`  
**Apps:** `apps/api-fastapi/` | `apps/storefront-next/`  
**Feature README:** `docs/features/inkless-integration/README.md`

---

## 1. Objective

This phase deprecates the legacy DocuSign/DocuSeal webhook integrations and shifts the signing flow to a state-driven hybrid workflow using external Inkless redirect links. The system compiles the contract PDF, and an admin manually configures the envelope in Inkless and pastes the resulting URL into the database. The client detail dashboard action bar must adapt dynamically to this contract state, removing legacy direct buttons and replacing them with a state-driven redirect.

**In scope**
- Database column `signing_url` (nullable string) on `LegalContract` model.
- Startup database migration logic in `database.py` to add `signing_url` to `legal_contracts` table without data loss.
- Serialization of `signing_url` in `LegalContractResponse` and direct endpoint mapping.
- GET `/api/v1/contracts/property/{property_id}` endpoint returning the latest contract for a property.
- Removal of the legacy "DocuSign Directo" button and related logic on the storefront property details page.
- State-Driven UI logic on the Property Detail page action bar:
  - No contract exists: Render "Generar Contrato".
  - Contract exists, `signing_url` is null: Render disabled button "Contract Generated - Pending Signature Setup".
  - Contract exists, `signing_url` is not null: Render active "Review and Sign Contract" external redirect link.

**Out of scope**
- Automated envelope creation in the Inkless API.
- Admin panel interface for pasting/saving the `signing_url` directly (handled directly via DB or seed for now).

---

## 2. API / Data contracts

### New / Modified Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/contracts/property/{property_id}` | Retrieve the latest legal contract record for a property (returns `LegalContractResponse` or `null`). |

**Models / tables:**
- `LegalContract` (`real_estate.legal_contracts` table):
  - Add `signing_url` column: `VARCHAR` (nullable, default `NULL`).

**Pydantic schemas:**
- `LegalContractResponse`:
  - `transaction_session_id`: Change type to `str | None` to allow compatibility with direct contracts.
  - `transaction`: Change type to `Optional[TransactionResponse]` (default `None`).
  - Add `signing_url: Optional[str] = None`.

---

## 3. Storefront

- **Component**: `PropertyDetailClient.tsx`
  - Remove `generateDirectContract` mutation and `isGenerating` state variables.
  - Remove the "DocuSign Directo" button.
  - Add a React Query hook querying `/api/v1/contracts/property/{property_id}`.
  - State-Driven Action Bar Buttons:
    1. If `contract` does not exist: Show active "Generar Contrato" button (opens the transaction generation modal).
    2. If `contract` exists but `contract.signing_url` is null: Show disabled button "Contract Generated - Pending Signature Setup".
    3. If `contract` exists and `contract.signing_url` is not null: Show active premium "Review and Sign Contract" button pointing to `contract.signing_url` with `target="_blank"`.

---

## 4. Security & boundaries

- Validation of `signing_url` format (must be a valid absolute HTTP/HTTPS URL when updated).
- Auth requirements: GET `/api/v1/contracts/property/{property_id}` is accessible to authenticated agents/admins.

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `pytest tests/test_inkless_bridge.py` |
| Storefront | `npx tsc --noEmit` |
| Manual | Verify toggle functionality and property filtering |

---

## 6. Drift policy

If implementation diverges from this spec, update spec **or** code in the same PR — never silent drift.
