# Spec: Secure PDF & Multi-Party Internal Signatures

## Status: SHIPPED
**Roadmap:** STREAM 4 PHASE 5.0  
**Branch:** `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/secure-pdf-signatures/README.md`

---

## 1. Objective

Seal generated markdown as a ReportLab PDF with SHA-256 tamper evidence; record buyer/seller internal execution telemetry until both parties sign.

**In scope**
- `services/pdf_renderer.py` → `storage/secure_pdfs/`
- `services/signature_service.py` — hash verify before sign
- `LegalContract.document_hash`, `pdf_file_path`
- `TransactionSession.buyer_signed_at`, `seller_signed_at`, `signature_telemetry`
- Routes: `generate-pdf`, `execute-signature`, `contract/pdf`
- `TransactionSigningPanel` (internal provider)

**Out of scope**
- Legally qualified e-sign (DocuSign phase)
- PKCS / HSM

---

## 2. API contracts

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/transactions/{id}/generate-pdf` | Requires `GENERATED` markdown |
| POST | `/api/v1/transactions/{id}/execute-signature` | Body: `{ "role": "BUYER" \| "SELLER" }` |
| GET | `/api/v1/transactions/{id}/contract/pdf` | Binary stream |

**State machine**
- Sign only when `status == GENERATED` and PDF hash matches disk
- `EXECUTED` when both `buyer_signed_at` and `seller_signed_at` set

**When `DOCUSIGN_PROVIDER=docusign`:** `execute-signature` returns **409** (see docusign spec)

---

## 3. Storefront

- Lockout UI when `GENERATED` / `EXECUTED`
- `transaction-types.ts`, signing panel mutations

---

## 4. Security (mandatory)

- Fail closed on `document_hash` mismatch (409)
- No signature without prior PDF generation
- One signature per role

---

## 5. Verification gates

| Gate | Command |
|------|---------|
| API | `pytest tests/test_phase5_pdf_signatures.py` |

---

## 6. Drift policy

PDF renderer is ReportLab-only; changing engine requires spec update + migration note for hash parity.