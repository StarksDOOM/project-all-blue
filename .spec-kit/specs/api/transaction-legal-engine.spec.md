# Spec: Transaction & Legal Document Engine

## Status: SHIPPED
**Roadmap:** STREAM 4 PHASE 4.0  
**Branch:** `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/transaction-legal-engine/README.md`

---

## 1. Objective

Model buyer/seller deal terms per listing and generate a versioned **Promesa de Venta** markdown artifact with storefront initiation and preview.

**In scope**
- `TransactionSession`, `LegalContract` models
- `services/contract_generator.py`, `services/transaction_service.py`
- Routes under `/api/v1/transactions`
- Storefront: Generar Contrato modal, `/dashboard/transactions/[id]` preview

**Out of scope (this phase)**
- Sealed PDF / signatures (STREAM 4 PHASE 5.0)
- DocuSign (STREAM 4 PHASE 5.1)

---

## 2. API contracts

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/transactions` | Create session |
| POST | `/api/v1/transactions/{id}/generate` | Compile markdown contract |
| GET | `/api/v1/transactions/{id}/contract` | Latest artifact + transaction |
| GET | `/api/v1/transactions/{id}/contract/raw` | Plain markdown |

**Status enum:** `DRAFT` → `GENERATED` (after generate)

**State guards:** Property must resolve via `resolve_property` (Blu id or `remote_id`)

---

## 3. Storefront

- `TransactionContractModal`, Zod schema `transaction-schema.ts`
- React Query: `transaction-contract` key on detail page

---

## 4. Security

- Validate all inputs with Pydantic; prices `gt=0`
- No contract generation without bound `property_id` ownership check when auth ships

---

## 5. Verification gates

| Gate | Command |
|------|---------|
| API | `pytest tests/test_transactions.py` |
| Storefront | `npm test` — `transaction-schema.test.ts` |
| Manual | Property 222598 / 222492 create → generate → preview |

---

## 6. Drift policy

Template interpolation lives in `contract_generator` — spec must list new template variables when added.