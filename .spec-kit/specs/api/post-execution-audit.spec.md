# Spec: Post-Execution Audit Certificate & Notifications

## Status: SHIPPED
**Roadmap:** STREAM 4 PHASE 6.0  
**Branch:** `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/post-execution-audit/README.md`

---

## 1. Objective

After `EXECUTED`, automatically ingest DocuSign certified PDF, emit audit certificate PDF, structured logs, and email stub.

**In scope**
- `services/post_execution_pipeline.py` (BackgroundTasks from webhook + internal sign completion)
- `services/audit_certificate_generator.py` → `storage/secure_pdfs/audit_receipts/{txn}_certificate.pdf`
- `services/notification_service.py` — JSON audit log + `send_execution_summary_email` stub
- `services/docusign/document_download.py` — combined PDF overwrite
- `GET /api/v1/transactions/{id}/audit-certificate`
- `TransactionAuditActions`, `TransactionExecutionTimeline`

**Out of scope**
- Live SES/Resend integration (stub only)

---

## 2. API contracts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/transactions/{id}/audit-certificate` | 404 unless `EXECUTED` + cert exists |

**Column:** `LegalContract.audit_certificate_path`

**Pipeline order (after EXECUTED commit)**
1. Download DocuSign combined PDF (if envelope id + provider enabled)
2. Refresh `document_hash`
3. Write audit certificate
4. Notifications
5. SSE broadcast (Phase 7)

---

## 3. Storefront

- Timeline steps: Draft → PDF Sealed → Envelope → Executed & Certified
- Audit download button when `status === EXECUTED`

---

## 4. Security

- Certificate exposes transaction/envelope/hash metadata — internal dashboard only
- Email stub must not log recipient secrets

---

## 5. Verification gates

| Gate | Command |
|------|---------|
| API | `pytest tests/test_phase6_post_execution.py` |

---

## 6. Drift policy

Certificate layout changes are cosmetic; hash/envelope fields are contractual — update spec if renamed.