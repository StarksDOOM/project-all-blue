# Spec: DocuSign Embedded Signing (JWT Grant)

## Status: SHIPPED
**Roadmap:** STREAM 4 PHASE 5.1  
**Branch:** `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/docusign-embedded-signing/README.md`

---

## 1. Objective

Replace internal placeholder signatures with DocuSign Embedded Signing using JWT Grant (machine auth) and Connect webhooks.

**In scope**
- `config/docusign_settings.py`, `services/docusign/*` (client, envelope, embedded, webhook)
- `services/docusign_orchestrator.py`
- Routes: envelope create, signing URL, Connect webhook, `GET /signing/config`
- `DocuSignEmbeddedSigning.tsx` iframe ceremony
- Env: `DOCUSIGN_*` in `.env.example` (no private key in git)

**Out of scope**
- Qualified electronic signature legal opinion
- Production Connect without HMAC secret

---

## 2. API contracts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/signing/config` | `provider`: docusign \| internal |
| POST | `/api/v1/transactions/{id}/docusign/envelope` | After sealed PDF |
| POST | `/api/v1/transactions/{id}/docusign/signing-url` | Body: `role`, `return_url` |
| POST | `/api/v1/docusign/connect/webhook` | HMAC `X-DocuSign-Signature-1` |

**Columns:** `LegalContract.docusign_envelope_id`, `docusign_status`

**Webhook:** `completed` → `TransactionSession.status = EXECUTED` → triggers post-execution pipeline (Phase 6)

---

## 3. Storefront

- `useSigningConfig` via `api.getSigningConfig()`
- Embedded iframe + return URL to transaction detail

---

## 4. Security

- JWT private key path gitignored under `storage/certs/`
- Webhook HMAC required in production (`DOCUSIGN_WEBHOOK_SECRET`)
- Sandbox IDs only in `.env.example`, not committed secrets

---

## 5. Verification gates

| Gate | Command |
|------|---------|
| API | `pytest tests/test_docusign.py` |
| Manual | RSA key + consent URL + sandbox ceremony |

---

## 6. Drift policy

DocuSign SDK upgrades must re-verify `create_recipient_view` and combined PDF download APIs.