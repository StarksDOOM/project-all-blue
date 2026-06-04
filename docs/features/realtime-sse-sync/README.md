# Real-Time Transaction SSE Sync (Phase 7)

**Status:** Feature branch  
**Scope:** Live UI updates when post-execution pipeline completes

---

## Outcomes

- In-memory SSE broadcaster keyed by `transaction_id`.
- `GET /api/v1/transactions/{id}/stream` for dashboard subscribers.
- `TRANSACTION_UPDATED` event after audit certificate generation.
- React `useTransactionRealtime` hook invalidates React Query cache (no polling).

---

## Out of scope

- Redis Pub/Sub (swap broadcaster implementation for multi-instance).
- WebSockets (SSE chosen for one-way server push).

**Spec-Kit:** `.spec-kit/specs/api/realtime-sse-sync.spec.md`