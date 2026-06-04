# Spec: <Feature Title>

## Status: DRAFT | IN_PROGRESS | SHIPPED
**Roadmap:** STREAM X PHASE X.X  
**Branch:** `feat/<slug>` ← `develop`  
**Apps:** `apps/api-fastapi/` | `apps/storefront-next/`  
**Feature README:** `docs/features/<slug>/README.md`

---

## 1. Objective

<One paragraph — what problem this solves.>

**In scope**
- …

**Out of scope**
- …

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| | | |

**Models / tables:** …

---

## 3. Storefront (if applicable)

- Routes / components: …
- React Query keys: …

---

## 4. Security & boundaries

- Server-side validation: …
- Auth (current): document gaps in Out of scope until JWT ships

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `pytest tests/test_<feature>.py` |
| Storefront | `npm test` (if touched) |
| Manual | Operator confirms on `develop` before SHIPPED |

**No** memory/session file updates until Manual Success.

---

## 6. Drift policy

If implementation diverges from this spec, update spec **or** code in the same PR — never silent drift.