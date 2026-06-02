# STREAM 2 PHASE 4.1 — Task Checklist

**Branch:** `feat/ingestion-oop-refactor`  
**Spec:** `.spec-kit/specs/api/ingestion-oop.spec.md`

---

## Phase A — Core abstractions

- [x] **A.1** Create `BaseDriver` with `initialize()` and `run_sync()`
- [x] **A.2** Create `DriverFactory` with registry `remaxrd`, `realtor`
- [x] **A.3** Create `IngestionOrchestrator` with `execute_sync_job`, `_bulk_upsert_chunks`
- [x] **A.4** Add `run_sync_for_portal` for background-safe sessions
- [x] **A.5** Update `services/__init__.py` exports

## Phase B — Driver migration

- [x] **B.1** Implement `RemaxRdDriver` (harvest, concurrent fetch, 429 backoff)
- [x] **B.2** Move DB upsert out of driver into orchestrator
- [x] **B.3** Scaffold `RealtorDriver` with `NotImplementedError` in `run_sync`
- [x] **B.4** Update `crawl_test.py` to use `run_portal_sync()`

## Phase C — API wiring

- [x] **C.1** Add `routers/properties.py` (`GET` list, `POST` trigger-crawl)
- [x] **C.2** Refactor `main.py` to include properties + contracts routers
- [x] **C.3** Map `ValueError` → HTTP 400, `RealtorDriver` → HTTP 501
- [x] **C.4** Background task uses `IngestionOrchestrator.run_sync_for_portal`

## Phase D — Verification & ship

- [ ] **D.1** Venv deps installed; import smoke passes
- [ ] **D.2** `python crawl_test.py --portal remaxrd` — Manual Success (full sync)
- [ ] **D.3** API: `POST /api/v1/properties/trigger-crawl?source_portal=remaxrd` → 202
- [ ] **D.4** API: `source_portal=realtor` → 501
- [ ] **D.5** API: `source_portal=badportal` → 400
- [ ] **D.6** DB: no duplicate `remaxrd` external_ids after sync
- [ ] **D.7** Write `walkthrough.md` with metrics (fetched/upserted/elapsed)
- [ ] **D.8** User says **Go** → chunked commits on `feat/ingestion-oop-refactor`
- [ ] **D.9** Merge `--no-ff` to `develop`; delete feature branch

## Phase E — Follow-on (separate feature: STREAM 2 PHASE 4.2)

- [ ] **E.1** Implement Realtor credential + parser in `RealtorDriver`
- [ ] **E.2** Remove `isinstance(RealtorDriver)` 501 guard when driver is ready
- [ ] **E.3** Deprecate / delete `scrapers/base.py` if unused

---

## Quick verification commands

```powershell
cd apps/api-fastapi
# imports (requires venv with requirements.txt)
python -c "from routers import properties; from scrapers.driver_factory import DriverFactory; print('ok')"

# CLI sync (AdsPower + network)
python crawl_test.py --portal remaxrd

# API (uvicorn main:app)
curl -X POST "http://127.0.0.1:8000/api/v1/properties/trigger-crawl?source_portal=remaxrd"
curl -X POST "http://127.0.0.1:8000/api/v1/properties/trigger-crawl?source_portal=realtor"
curl -X POST "http://127.0.0.1:8000/api/v1/properties/trigger-crawl?source_portal=badportal"
```