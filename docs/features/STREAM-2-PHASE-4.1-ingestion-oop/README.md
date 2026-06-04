# Ingestion OOP Architecture

**Status:** Shipped on `develop`  
**Scope:** Portal drivers, orchestrator, property upsert pipeline

---

## Context

Listing inventory must scale to multiple portals without copying crawl orchestration for each integration.

---

## Outcomes

- `BaseDriver` + `DriverFactory` + `IngestionOrchestrator`
- RE/MAX driver with bulk upsert on `(source_portal, remote_id)`
- `POST /api/v1/properties/trigger-crawl`

---

## Out of scope

- Realtor.com parser (STREAM 2 PHASE 4.2)
- Implementation/class diagrams in this README

**Spec-Kit:** `.spec-kit/specs/api/ingestion-oop.spec.md`  
**Artifacts:** `implementation_plan.md`, `task.md`, `walkthrough.md` in this folder.