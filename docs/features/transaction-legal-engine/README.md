# Transaction & Legal Document Engine (Phase 4)

**Status:** Shipped on `develop`  
**Scope:** Deal workflow from listing to Promesa de Venta draft

This document describes **why** this work exists and **what problems it addresses**. It does **not** document template logic, storage layout, or API contracts.

---

## Context

After listings are in inventory, agents need to capture buyer/seller terms and produce a standard **Promesa de Venta** draft tied to that listing—without copying portal fields by hand.

---

## Problems addressed

1. **No transaction record** — Deal parties and agreed price were not modeled in the system.

2. **Manual contract assembly** — High risk of stale or wrong property facts on legal drafts.

3. **No product path from listing to contract** — The storefront could browse inventory but not start a regulated document flow.

---

## Outcomes

- Structured **transaction sessions** linked to listings.
- Generated **Promesa de Venta** draft text stored as a versioned legal artifact.
- Storefront **“Generar Contrato”** flow and contract preview for agents.

---

## Out of scope (Phase 4)

- Sealed PDF and cryptographic execution (Phase 5).
- External e-sign providers.
- Usage/runbook documentation in this file.

---

## Verification

- Automated tests pass on API and storefront form validation.
- Manual operator confirmation on live listings before merge.

---

*Problem/solution summary only.*

**Spec-Kit:** `.spec-kit/specs/api/transaction-legal-engine.spec.md`