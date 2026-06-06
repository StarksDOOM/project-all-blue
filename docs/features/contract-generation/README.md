# Contract Generation Engine & DocuSign E2E (STREAM 6 PHASE 1.0)

## Problem
Currently, there is a gap between listing browsing on the storefront and starting a transaction with signed legal contracts. Property listings cannot easily be mapped into DocuSign envelopes for signature, and agents must manually coordinate the contracts. Furthermore, we need a reliable Machine-to-Machine JWT Grant authentication mechanism to interact with DocuSign's API securely without requiring agents to log in interactively.

## Outcomes
- **Stateless DocuSign JWT Authentication**: Expose client-side token acquisition to the backend server by exchanging integration keys and private keys with DocuSign's oauth server.
- **Envelope Generation & Dispatching**: Map listing data from a `PropertyListing` schema to a DocuSign envelope and dispatch it directly to buyers/sellers, creating a tracking `LegalContract` record.
- **Storefront Quick Action**: Integrate a "Generar Contrato" action button on the Property Detail view that makes a single-click API request.
- **Isolated Unit Testing**: High-density tests that fully verify the envelope builder and route logic without touching public DocuSign sandboxes.

**Spec:** [.spec-kit/specs/api/contract-generation-docusign.spec.md](../../../.spec-kit/specs/api/contract-generation-docusign.spec.md)

**Baseline:** 12 abstractions at start of phase.

Status: DRAFT
