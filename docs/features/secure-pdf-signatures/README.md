# Secure PDF Compilation, Tamper Evidence & Multi-Party Signatures (Phase 5)

**Branch:** `feat/phase-5-secure-pdf-signatures`  
**Status:** Implemented locally; not yet merged into `develop`  
**Scope:** `apps/api-fastapi` (FastAPI / SQLModel) + `apps/storefront-next` (Next.js 15)

This document describes **why** this work exists and **what problems it addresses**. Operational runbooks and step-by-step usage are intentionally out of scope here.

---

## Context

Phase 4 on `develop` produces a **markdown** Promesa de Venta, persists `LegalContract.document_body`, and moves `TransactionSession` to `GENERATED`. That is sufficient for drafting but not for **audit-grade execution**: agents and compliance need a **locked PDF**, an **immutable fingerprint** at seal time, and **in-app** buyer/seller attestation without routing through external e-sign SaaS.

Phase 5 adds PDF rendering (ReportLab), SHA-256 `document_hash` on the binary artifact, JSONB `signature_telemetry`, and storefront UI lockout once terms are cryptographically frozen.

---

## Current Problems (Before This Branch)

### 1. Markdown alone is not a sealed record

Markdown under `storage/legal_contracts/` is editable after generation. There was no PDF binary or hash proving what was presented at signing time.

### 2. No tamper check before signature

Nothing recomputed SHA-256 of the on-disk PDF against a stored ledger field before accepting a party signature.

### 3. No multi-party execution state

`TransactionSession` did not track `buyer_signed_at`, `seller_signed_at`, or structured telemetry (IP, User-Agent, per-role signing hash).

### 4. Status machine stopped at GENERATED

There was no transition to `EXECUTED` when both parties signed, and no API to record role-specific execution.

### 5. Storefront allowed ambiguous edit semantics

After markdown generation, users could still perceive editable deal terms unless the UI explicitly disabled fields and displayed a cryptographic lock warning.

### 6. WeasyPrint-style deps avoided

Heavy HTML→PDF stacks (WeasyPrint) complicate Windows dev machines. The product needed a portable PDF path (ReportLab) with acceptable typography for legal prose.

---

## What This Branch Solves

### A. Secure PDF render service (backend)

| Piece | Role |
|--------|------|
| `services/pdf_renderer.py` | Markdown → PDF via ReportLab; writes `storage/secure_pdfs/` (gitignored) |
| `sha256_bytes` / `sha256_file` | Fingerprint at write time |
| `POST .../generate-pdf` | Compiles PDF, sets `LegalContract.document_hash` + `pdf_file_path` |

`version_hash` remains the **markdown** body hash from Phase 4; `document_hash` is the **PDF** ledger field.

### B. Multi-party execution (backend)

| Piece | Role |
|--------|------|
| `TransactionSession.buyer_signed_at` / `seller_signed_at` | Atomic timestamps per role |
| `signature_telemetry` (JSONB) | Append-only `signatures[]` with IP, User-Agent, `signing_hash`, `document_hash` |
| `services/signature_service.py` | Tamper check, telemetry, `EXECUTED` when both signed |
| `POST .../execute-signature` | Payload `{ "role": "BUYER" \| "SELLER" }` |
| `GET .../contract/pdf` | Stream sealed binary |

### C. Storefront execution panel (Next.js)

| Piece | Role |
|--------|------|
| `TransactionSigningPanel` | Generar PDF seguro, Firmar como Comprador/Vendedor, download PDF |
| Disabled inputs + badge | *Documento bloqueado criptográficamente - No se permiten modificaciones post-firma* when `GENERATED` or `EXECUTED` |
| `transaction-types.ts` | TypeScript DTOs for API shapes (Python remains source of truth) |

TypeScript here is **contract typing for the UI**, not a second implementation of hash or PDF logic.

### D. Schema migration (backend)

`ensure_phase5_schema()` — additive columns on startup for existing databases.

---

## Problem → Solution Map

| Symptom | Root cause | Mitigation on this branch |
|---------|------------|---------------------------|
| “We only have .md, not PDF” | No renderer | `pdf_renderer` + `generate-pdf` |
| “PDF changed after signing” | No hash | `document_hash` + verify before sign |
| “Who signed when?” | No telemetry | JSONB + timestamps |
| “Deal still looks editable” | No UI lock | `is_locked` + disabled fields + badge |
| PDF stack won’t run on Windows | WeasyPrint deps | ReportLab |

---

## Architectural Boundaries

**In scope**

- PDF generation from existing `document_body`  
- SHA-256 tamper evidence on PDF bytes  
- BUYER/SELLER execution without external e-sign API  
- Internal signing telemetry (IP, User-Agent)  

**Out of scope (this branch)**

- Qualified electronic signature under Dominican law (legal review required)  
- HSM, external timestamp authority, blockchain anchoring  
- Email delivery of signed PDFs  
- Resolving/ACKing signatures via admin workflow  
- Usage/runbook documentation (deferred deliberately)  

**Runtime**

- PDF generation is on-demand per `generate-pdf` call.  
- `storage/secure_pdfs/` is gitignored.  
- Signing requires PDF exists and hash matches file on disk.  

---

## Commits on `feat/phase-5-secure-pdf-signatures` (Overview)

1. `feat(api): Phase 5 secure PDF, SHA-256 ledger, and multi-party signatures`  
2. `feat(storefront): digital signing panel and cryptographic document lockout`  
3. `chore: document maintenance scripts and ignore one-off rewrite helper`  
4. `docs: Phase 4 transaction legal engine and Phase 5 secure PDF READMEs` (this file + Phase 4 README parity)  

(Base branch: `develop`, including Phase 4 transaction engine.)

---

## Verification Posture

- **Automated:** `pytest` — `test_phase5_pdf_signatures.py`; full suite 28 tests.  
- **Automated:** `tsc --noEmit` on storefront.  
- **Manual:** Create → generate markdown → generate PDF → dual signature → download PDF. Usage steps are not documented here.  

---

## Untracked / Gitignored Runtime (Not in Git)

| Path | Purpose | Commit? |
|------|---------|--------|
| `apps/api-fastapi/storage/secure_pdfs/` | Sealed PDF binaries | **No** — gitignored |
| `scripts/rewrite-git-emails.sh` | One-off git history rewrite | **No** — gitignored; see `scripts/README.md` |

---

## Relationship to Broader All Blue Goals

Phase 5 closes the loop from **ingestion truth** (STREAM 2) → **legal draft** (Phase 4) → **sealed execution record** (this branch). It does not replace CRG or Graphify adoption under `docs/development/`. External APM for signature fraud detection remains a future sink; today Postgres JSONB is the telemetry store (same pattern as scraper error telemetry).

---

*Last updated: feature branch `feat/phase-5-secure-pdf-signatures` (pre-merge).*