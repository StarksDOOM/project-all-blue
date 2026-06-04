# Secure PDF & Multi-Party Signatures (Phase 5)

**Status:** Shipped on `develop`  
**Scope:** Sealed PDF, integrity checks, in-app buyer/seller execution

This document describes **why** this work exists and **what problems it addresses**. It does **not** document hash algorithms, file paths, or signing wire formats.

---

## Context

Phase 4 produces a markdown legal draft. For audit and closing, the business needs a **non-editable PDF**, proof the file was not altered after sealing, and **recorded** buyer/seller execution—without mandating a third-party e-sign SaaS.

---

## Problems addressed

1. **Markdown alone is not a sealed record** — No binary artifact or integrity fingerprint at seal time.

2. **No tamper check at signing** — Signatures could not be tied to a verified document state.

3. **No multi-party execution trail** — Buyer and seller attestation was not timestamped in the system.

4. **UI still implied editable terms** — After draft generation, users needed a clear “locked” experience.

---

## Outcomes

- PDF artifact generated from the approved draft.
- Integrity fingerprint stored when the PDF is sealed; signing blocked if verification fails.
- Buyer and seller execution captured in-product; deal marked **executed** when both complete.
- Storefront lockout messaging and disabled fields after cryptographic freeze.

---

## Out of scope

- Legally qualified electronic signature under local law (requires legal review).
- External trust providers (HSM, timestamp authority, DocuSign).
- Usage/runbook documentation in this file.

---

## Verification

- Automated tests pass on API signing and PDF pipeline.
- Manual dual-signature flow confirmed before merge.

---

*Problem/solution summary only.*