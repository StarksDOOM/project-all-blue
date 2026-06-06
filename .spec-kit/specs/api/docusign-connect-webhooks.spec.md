# Spec: DocuSign Connect Webhooks & HMAC Signature Validation

## Status: SHIPPED
**Roadmap:** STREAM 6 PHASE 1.1  
**Branch:** `feat/stream-6-phase-1.1-docusign-connect-webhooks` ← `develop`  
**Apps:** `apps/api-fastapi/`  
**Feature README:** `docs/features/docusign-connect-webhooks/README.md`

---

## 1. Objective

Provide a secure, unauthenticated webhook endpoint to receive notifications from DocuSign Connect when standalone listing contracts are completed or declined. Payload integrity must be verified cryptographically using HMAC-SHA256 before updating database contract states and triggering outbound execution notifications.

**In scope**
- `DocuSignWebhookValidator`: A stateless security class verifying the request HMAC signature using the SHA-256 algorithm and a constant-time comparison helper.
- `ContractLifecycleManager`: A stateless manager updating standalone `LegalContract` rows based on webhook envelope IDs and status codes.
- `NotificationDispatcher` integration: Sending email notifications on execution completion.
- Endpoint `POST /api/v1/contracts/webhooks/docusign` returning `200 OK` on success.
- Comprehensive isolated unit tests in `tests/test_docusign_webhooks.py`.

**Out of scope**
- XML payload support (only JSON is in scope).
- Automated email transport retries (handled at Resend/SES provider levels).
- Interactive user actions/screens (this is a backend-only callback pipeline).

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/contracts/webhooks/docusign` | Unauthenticated endpoint for DocuSign Connect callback. Returns `200 OK` on processing success. |

**Expected Payload structure (DocuSign Connect JSON format):**
```json
{
  "envelopeId": "string-guid",
  "status": "completed"
}
```

**Models / tables:**
- Reads and updates `real_estate.legal_contracts` table:
  - `docusign_status`: updated from `sent` to `completed` or `declined`.
  - `user_id`: referenced to retrieve the agent's context for notifications.
- Reads `real_estate.properties` table:
  - Retrieves the sector/province/price metadata for outbound emails.

---

## 3. Storefront (if applicable)

Not applicable (backend only).

---

## 4. Security & boundaries

- **HMAC Verification**: Standard `X-DocuSign-Signature-1` header validation with `DOCUSIGN_HMAC_SECRET` (falling back to `DOCUSIGN_WEBHOOK_SECRET` for environment compatibility) over the raw body bytes.
- **Constant-Time Comparison**: Prevents timing attacks on signature strings using `hmac.compare_digest`.
- **SSRF / SQL Injection**: Parameter binding via SQLModel session query using the extracted `envelopeId` parameter.

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `pytest apps/api-fastapi/tests/test_docusign_webhooks.py` |
| Full pytest gate | `cd apps/api-fastapi; .\.venv\Scripts\python.exe -m pytest -q --tb=no` |

**No** memory/session file updates until Manual Success.

---

## 6. Drift policy

If implementation diverges from this spec, update spec **or** code in the same PR — never silent drift.
All new classes must maintain 100% PEP 257 docstring compliance.
