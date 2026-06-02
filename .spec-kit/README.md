# All Blue — Spec-Kit Index

Architectural ground truth for **All Blue Core**. Implementation must match these specs before a feature is marked final.

| Spec | Roadmap | Status |
|------|---------|--------|
| [api/ingestion-oop.spec.md](specs/api/ingestion-oop.spec.md) | STREAM 2 PHASE 4.1 | DRAFT — OOP refactor target |

## Conventions

- **File naming:** `<domain>-<feature>.spec.md` under `specs/<area>/`
- **Phases:** Use `STREAM X PHASE X.X` in every spec header
- **Verification:** Each spec ends with test gates; no memory/session updates until Manual Success
- **Drift:** If code diverges from spec, fix code or update spec first — never ship silent drift