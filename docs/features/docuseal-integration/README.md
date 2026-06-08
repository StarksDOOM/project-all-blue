# DocuSeal E-Sign Integration

**Stream:** STREAM 6 PHASE 1.5  
**Status:** DRAFT  
**Spec Link:** [docuseal-provider-swap.spec.md](../../../.spec-kit/specs/api/docuseal-provider-swap.spec.md)

## Problem

The previous DocuSign integration requires M2M JWT negotiation and has significant API pricing overhead. To eliminate API costs, the business has decided to pivot to the open-source, self-hosted DocuSeal platform. The backend must be modified to use DocuSeal's submission API and webhook validation mechanism while maintaining the database schema of the `LegalContract` tracking table.

## Outcomes

- Complete removal of DocuSign JWT Authenticator, Envelope Builder, and Envelope Dispatcher.
- Implementation of `DocuSealDispatcher` submitting template-based signature requests using `DOCUSEAL_API_KEY`.
- Implementation of `DocuSealWebhookValidator` executing HMAC-SHA256 signature verification over incoming webhook request payloads.
- Integration of `/api/v1/contracts/generate` and `/api/v1/contracts/webhooks/esign` endpoints in the contracts router.
- Clean database mapping where DocuSeal submission ID and status map directly onto `LegalContract` columns.

## Out of Scope

- Next.js storefront user interface updates or layouts.
- Database schema changes or migrations.
- Support for multiple template configurations per route.
