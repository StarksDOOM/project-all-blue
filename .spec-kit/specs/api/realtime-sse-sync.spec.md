# Spec: Real-Time Transaction SSE Sync

## Status: SHIPPED
**Roadmap:** STREAM 4 PHASE 7.0  
**Branch:** `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/realtime-sse-sync/README.md`

---

## 1. Objective

Push `TRANSACTION_UPDATED` to open dashboard clients when post-execution pipeline completes — no polling.

**In scope**
- `services/realtime_broadcaster.py` — in-memory queues per `transaction_id`
- `routers/realtime.py` — `GET /api/v1/transactions/{id}/stream` (`text/event-stream`)
- `bind_app_event_loop` in FastAPI lifespan
- `publish_sync` from `post_execution_pipeline` after cert written
- `hooks/useTransactionRealtime.ts` — EventSource + React Query invalidation

**Out of scope**
- Redis Pub/Sub (multi-instance) — swap broadcaster implementation later
- WebSockets

---

## 2. API contracts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/transactions/{id}/stream` | SSE; optional `?token=` if `TRANSACTION_STREAM_TOKEN` set |

**Event payload**
```json
{ "event": "TRANSACTION_UPDATED", "transaction_id": "UUID", "status": "EXECUTED", "has_audit_certificate": true }
```

**Keepalive:** `: keepalive` comment every 25s

---

## 3. Storefront

- Hook mounted on `/dashboard/transactions/[id]`
- Invalidates `["transaction-contract", transactionId]`
- `NEXT_PUBLIC_TRANSACTION_STREAM_TOKEN` when API token configured

---

## 4. Security

- Transaction must exist (404 otherwise)
- Optional shared secret for public API exposure
- CORS must allow storefront origin for EventSource GET

---

## 5. Verification gates

| Gate | Command |
|------|---------|
| API | `pytest tests/test_phase7_realtime.py` |
| Manual | Open detail → complete signing → UI updates without reload |

---

## 6. Drift policy

Horizontal scaling requires Redis-backed broadcaster — update this spec before multi-replica deploy.