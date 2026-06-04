# DocuSign Embedded Signing

**Status:** Feature branch `feat/docusign-embedded-signing`  
**Scope:** Production e-sign for Promesa de Venta PDFs via DocuSign JWT Grant

---

## Context

Phase 5 sealed PDFs with internal placeholder signatures. The business requires legally recognized execution through DocuSign Embedded Signing inside the storefront dashboard.

---

## Problems addressed

1. **Non-qualified internal signatures** — Placeholder execution is not sufficient for closing.
2. **No in-dashboard ceremony** — Users had to leave the product for external signing.
3. **No envelope audit trail** — No provider-backed envelope lifecycle in the database.

---

## Outcomes

- JWT Grant machine authentication to DocuSign demo/production.
- Envelope created from the tamper-sealed PDF; buyer and seller embedded ceremonies.
- Connect webhook updates envelope status and marks transactions **EXECUTED** when completed.
- Legacy internal `execute-signature` disabled when DocuSign provider is active.

---

## Out of scope

- PKCS/HSM, qualified timestamps, or legal advice on enforceability.
- Implementation details in this README (see private runbooks and code review).

---

## Verification

- `pytest` suite including `tests/test_docusign.py` (mocked DocuSign API).
- Manual sandbox ceremony with RSA key in `storage/certs/` (gitignored).

**Spec-Kit:** `.spec-kit/specs/api/docusign-embedded-signing.spec.md`