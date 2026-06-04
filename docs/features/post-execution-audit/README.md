# Post-Execution Audit Certificate (Phase 6)

**Status:** Feature branch  
**Scope:** Audit PDF receipt + async notifications after EXECUTED

---

## Context

DocuSign embedded signing (Phase 5) seals the Promesa de Venta. Operations need a downloadable audit artifact and coordinator alerts when a deal closes.

---

## Problems addressed

1. **No cryptographic receipt** — Executed deals lacked a one-page audit summary for compliance review.
2. **No post-close automation** — Certified PDF ingest and notifications were manual.
3. **No in-product evidence download** — Auditors could not fetch the certificate from the dashboard.

---

## Outcomes

- Auto-generated Certificado de Ejecución Digital PDF after EXECUTED.
- DocuSign combined PDF downloaded and local SHA-256 refreshed on webhook completion.
- Structured audit logs and email dispatch stub (SES/Resend ready).
- Storefront timeline + audit certificate download when certified.

---

## Out of scope

- Live email provider wiring (stub only).
- Implementation runbooks in this README.

**Spec-Kit:** `.spec-kit/specs/api/post-execution-audit.spec.md`