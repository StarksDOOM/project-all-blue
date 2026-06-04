# Transaction & Legal Document Engine (Phase 4)

**Branch:** `feat/phase-4-transaction-legal-engine`  
**Status:** Merged into `develop`  
**Scope:** `apps/api-fastapi` (FastAPI / SQLModel) + `apps/storefront-next` (Next.js 15)

This document describes **why** this work exists and **what problems it addresses**. Operational runbooks and step-by-step usage are intentionally out of scope here.

---

## Context

All Blue Core already ingests and enriches RE/MAX (`remaxrd`) listings into `real_estate.properties` with portal-accurate price, specs, and descriptions. Agents and internal users browse that inventory on the Next.js storefront.

Closing a deal requires a **regulated draft**—a Dominican **Promesa de Venta**—that binds real listing fields (title, sector, land area, bathrooms, list price) to **negotiated terms** (buyer/seller identity, cédula/RNC, agreed price, currency). That step was not modeled in the database or product UI; only a legacy SRL contract drawer (`/api/v1/contracts/*`) existed for a different workflow.

Phase 4 introduces a **transaction session** lifecycle and an isolated **markdown compilation engine**, without third-party document SaaS.

---

## Current Problems (Before This Branch)

### 1. No first-class transaction record

There was no `TransactionSession` row tracking buyer/seller parties, agreed price, currency, or status between “browsing a listing” and “having a contract.” Deal terms lived outside the system.

### 2. Promesa text assembled manually

Agents copied portal copy into Word or email. Stale `bathrooms`, `sqm_land`, or list price on the contract was a recurring integrity risk.

### 3. Property resolution inconsistent for numeric IDs

Portal `remote_id` values (e.g. `222598`) must resolve to `properties.id` (Blu PK). Detail GET supported this; contract initialization paths needed the same lookup order to avoid 404s on create.

### 4. No storefront path from listing → legal draft

The property dashboard and detail page could not start a Promesa workflow. “Generate Contract” referred to legacy SRL flows, not Promesa de Venta tied to enriched inventory.

### 5. No persisted legal artifact version

Even if text was generated in memory, there was no `LegalContract` row with `version_hash`, markdown body, and file path for audit.

---

## What This Branch Solves

### A. Transaction and legal data model (backend)

| Piece | Role |
|--------|------|
| `TransactionSession` | UUID session, FK to `properties.id`, parties, `agreed_price`, `currency`, status enum (`DRAFT` → `REVIEW` → `GENERATED` → `EXECUTED`) |
| `LegalContract` | FK to session, `document_body`, markdown `version_hash`, optional `.md` under `storage/legal_contracts/` |
| `ensure_transaction_schema()` | Additive DDL on startup for existing Postgres |

### B. Isolated document compilation (backend)

| Piece | Role |
|--------|------|
| `services/contract_generator.py` | Promesa de Venta markdown template; safe `format_map` interpolation from `PropertyListing` + `TransactionSession` |
| `services/transaction_service.py` | Create session, compile markdown, persist contract; boundary layer only—no PDF logic (Phase 5) |

### C. Transaction API (backend)

| Method | Path |
|--------|------|
| `POST` | `/api/v1/transactions` |
| `POST` | `/api/v1/transactions/{id}/generate` |
| `GET` | `/api/v1/transactions/{id}/contract` |
| `GET` | `/api/v1/transactions/{id}/contract/raw` |

Legacy **`/api/v1/contracts/*`** (SRL) remains unchanged.

### D. Storefront initiation and preview (Next.js)

- **Generar Contrato** — shadcn Dialog, `react-hook-form` + Zod (`transaction-schema.ts`) on dashboard table and property detail.
- **`/dashboard/transactions/[id]`** — prose preview, print, download `.md`.
- API client: `createTransaction`, `generateTransactionContract`, `getTransactionContract`.

---

## Problem → Solution Map

| Symptom | Root cause | Mitigation on this branch |
|---------|------------|---------------------------|
| “Can’t start a sale from a listing” | No transaction model | `POST /api/v1/transactions` |
| Promesa missing portal metrics | Manual copy | `contract_generator` pulls DB fields |
| `222598` 404 on create | Wrong property lookup | `remote_id` then `id` resolution in `resolve_property` |
| No contract preview in product | No route | `/dashboard/transactions/[id]` |
| No audit trail for draft text | No `LegalContract` row | Persist body + `version_hash` |

---

## Architectural Boundaries

**In scope**

- Markdown Promesa de Venta for Dominican sale use case  
- Transaction session CRUD and generate/fetch contract endpoints  
- Storefront modal + preview route  

**Out of scope (this branch)**

- PDF compilation and SHA-256 tamper ledger → **Phase 5**  
- Multi-party digital signatures → **Phase 5**  
- External e-sign (DocuSign, Adobe Sign)  
- Notarial filing, government registry integration  
- Usage/runbook documentation (deferred deliberately)  

**Runtime**

- Contract generation is on-demand per API call, not part of ingestion cron.  
- Markdown files under `storage/legal_contracts/` are gitignored runtime artifacts.  

---

## Commits on `feat/phase-4-transaction-legal-engine` (Overview)

1. `feat(api): Phase 4 transaction sessions and Promesa de Venta generator`  
2. `feat(storefront): Generar Contrato modal and transaction contract preview route`  
3. `test(api): property 222598 transaction QA and FK-safe DB cleanup`  
4. `test(storefront): extract transaction Zod schema and add vitest coverage`  

(Base branch: `develop`, including scraper telemetry and RE/MAX enrichment.)

---

## Verification Posture

- **Automated:** `pytest` — `test_transactions.py`, `test_transactions_property_222598.py` (when listing `222598` exists in DB).  
- **Automated:** `npm run test` — `transaction-schema.test.ts` (Zod).  
- **Manual:** Operator-confirmed create → generate → preview on live API (`222598`, `222492`). Usage steps are not documented here.  

---

## Untracked / Gitignored Runtime (Not in Git)

| Path | Purpose | Commit? |
|------|---------|--------|
| `apps/api-fastapi/storage/legal_contracts/` | Generated markdown contracts | **No** — gitignored |
| `apps/api-fastapi/scripts/qa_*.json` | Local curl QA payloads | **No** — gitignored |

---

## Relationship to Broader All Blue Goals

Phase 4 is the legal **draft** layer on top of trustworthy listing ingestion (STREAM 2 / RE/MAX detail). Phase 5 seals PDFs and captures signatures. Code Review Graph (CRG) and `.spec-kit/` specs remain the architectural ground truth for reviews; this README is the feature-level problem/solution record for operators and future agents.

---

*Last updated: merged via `develop` (Phase 4); extended on `feat/phase-5-secure-pdf-signatures` for doc parity only.*