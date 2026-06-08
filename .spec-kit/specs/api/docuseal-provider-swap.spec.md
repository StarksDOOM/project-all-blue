# Spec: E-Sign Provider Swap: DocuSeal

## Status: SHIPPED
**Roadmap:** STREAM 6 PHASE 1.5  
**Branch:** `feat/stream-6-phase-1.5-docuseal-swap` ← `develop`  
**Apps:** `apps/api-fastapi/`  
**Feature README:** `docs/features/docuseal-integration/README.md`

---

## 1. Objective

Pivot e-signature provider from DocuSign to DocuSeal. Remove the DocuSign specific authentication and envelope building abstractions. Implement the stateless `DocuSealDispatcher` to submit signature requests using template-based REST API calls, and the stateless `DocuSealWebhookValidator` to verify incoming signing status callbacks securely via HMAC-SHA256 signatures. Preserve the schema and tracking capabilities of the `LegalContract` database table.

**In scope**
- `DocuSealSettings`: Loader for API key, template ID, base URL, and webhook secret.
- `DocuSealDispatcher`: Stateless dispatcher constructing DocuSeal submissions.
- `DocuSealWebhookValidator`: Stateless validator verifying `X-Docuseal-Signature` (`timestamp.signature`) headers.
- Route updates in `routers/contracts.py`:
  - `POST /api/v1/contracts/generate` - triggers DocuSeal dispatch.
  - `POST /api/v1/contracts/webhooks/esign` - unauthenticated webhook endpoint for DocuSeal callbacks.
- Complete replacement and renaming of DocuSign tests to DocuSeal contracts and webhooks tests.

**Out of scope**
- Database schema changes (the existing columns `docusign_envelope_id` and `docusign_status` in `LegalContract` are reused).
- Storefront UI visual updates (API interface endpoints remain functionally identical).

---

## 2. API / Data contracts

### Method: `POST /api/v1/contracts/generate`
**Request Payload:**
```json
{
  "property_id": "string"
}
```

**Response Payload:**
```json
{
  "envelope_id": "string",
  "status": "sent",
  "contract_id": "string"
}
```

### Method: `POST /api/v1/contracts/webhooks/esign`
**Authentication:** Unauthenticated callback. Relies on `X-Docuseal-Signature` header.
**Payload:**
```json
{
  "event": "submission.completed",
  "data": {
    "id": 12345,
    "status": "completed",
    "metadata": {
      "external_id": "your-internal-id"
    }
  }
}
```

**Models / tables:**
- Reads/updates `real_estate.legal_contracts`:
  - `docusign_envelope_id`: stores DocuSeal submission `id` (as string, e.g. `"12345"`).
  - `docusign_status`: maps to `sent` when dispatched, `executed` when webhook status is `completed`, or `declined`.

---

## 3. Security & boundaries

- **API Token Header**: `X-Auth-Token` containing the value of `DOCUSEAL_API_KEY` for outbound requests.
- **Webhook Verification**: Header `X-Docuseal-Signature` formatted as `[timestamp].[signature]`.
  - Extract `timestamp` and `signature` by splitting on `.`.
  - Compute expected signature as hex digest of HMAC-SHA256 over message: `[timestamp].[raw_body]`.
  - Perform constant-time digest comparison using `hmac.compare_digest`.
- **SSRF Mitigation**: Verify property listing exists and is active before creating a signature submission request.

---

## 4. Verification gates

| Gate | Command / check |
|------|-----------------|
| Contracts tests | `pytest apps/api-fastapi/tests/test_docuseal_contracts.py` |
| Webhooks tests | `pytest apps/api-fastapi/tests/test_docuseal_webhooks.py` |
| Full pytest gate | `cd apps/api-fastapi; .\.venv\Scripts\python.exe -m pytest -q --tb=no` |

---

## 5. Drift policy

Any deviation from this spec must be updated in the spec or code in the same change. All methods and classes must carry PEP 257 compliant docstrings.
