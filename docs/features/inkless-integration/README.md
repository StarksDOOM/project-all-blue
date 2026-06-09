# Inkless Signature URL Bridge (STREAM 6 PHASE 1.8.2)

## Problem Statement
1. **Deprecated Integrations**: In previous phases, DocuSign and DocuSeal integrations were introduced. The client has directed that all legacy third-party webhook integrations be deprecated and their UI elements purged to simplify the signing flow.
2. **Inkless Redirection Flow**: The signing process is being shifted to a state-driven hybrid workflow. In this model, the system compiles and generates the PDF contract record. An admin then manually uploads/sets up the signing envelope in the external Inkless service, retrieves the signing URL, and updates the database record. The buyer must then be presented with a clean external redirect link to sign the contract.
3. **State-Driven UI Actions**: On the storefront property detail page, the action bar must dynamically reflect the contract's actual status (not generated, generated but pending setup, or generated and ready for signature redirect) rather than displaying static legacy actions.

## Outcomes
- **Clean UI Purge**: All legacy DocuSign and iframe modal components are completely removed from the storefront.
- **Inkless Integration**: Added a database column `signing_url` on `LegalContract` to hold the external signing URL.
- **State-Driven UI Action Bar**:
  - If no contract exists for the property listing: Render the "Generar Contrato" button.
  - If a contract has been generated but its `signing_url` is null: Render a disabled button/badge indicating the contract is generated but signature setup is pending.
  - If the contract exists and has a non-null `signing_url`: Render a premium high-visibility "Review and Sign Contract" button redirecting to the external URL in a new tab.
- **Clean API Serialization**: Serialized the new `signing_url` field to Next.js clients.
- **Robust Database Column Migration**: Ensured the database column is safely added to the `legal_contracts` table on startup without dropping any existing records.
