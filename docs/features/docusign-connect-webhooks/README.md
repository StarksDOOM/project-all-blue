# DocuSign Connect Webhooks & HMAC Validation (STREAM 6 PHASE 1.1)

## Problem
After an agent or admin triggers standalone contract generation on the storefront, the DocuSign envelope is sent to the client and agent for signature. However, the system currently has no way to automatically track when the signing ceremony is completed or if it gets declined. Agents must manually check the DocuSign dashboard. We need a secure, automated callback pipeline to listen to DocuSign Connect events and update contract status in real-time.

## Outcomes
- **Payload Validation Middleware**: Cryptographically verify that incoming webhooks originate from DocuSign by validating the SHA-256 HMAC signature.
- **Automated Lifecycle Processing**: Standalone contracts are automatically updated to `completed` or `declined` based on Connect webhook notifications.
- **Outbound Notification integration**: Upon successful contract execution, notify the respective agent and client immediately via email.
- **Isolated Unit Testing**: High-density tests verifying security gates and lifecycle status updates.

**Spec:** [.spec-kit/specs/api/docusign-connect-webhooks.spec.md](../../../.spec-kit/specs/api/docusign-connect-webhooks.spec.md)

**Baseline:** 12 abstractions at start of phase.

Status: DRAFT
