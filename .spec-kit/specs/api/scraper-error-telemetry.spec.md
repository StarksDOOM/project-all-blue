# Spec: Scraper Error Telemetry & Listing Data Integrity

## Status: SHIPPED
**Roadmap:** STREAM 2 PHASE 3.9  
**Branch:** `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/scraper-error-telemetry/README.md`

---

## 1. Objective

Persist RE/MAX scrape/enrichment failures for operator visibility; keep property detail usable when live portal refresh fails; align bathroom KPIs with listing text when structured fields are empty.

**In scope**
- `ScraperErrorLog` table + `observability/scraper_errors.py` (`scraper_error_scope`, `persist_scraper_error_record`)
- `GET /api/admin/scraper-errors` for unresolved rows
- Property detail fail-graceful (`portal_refresh_failed` signal) on `GET /api/v1/properties/{id}?refresh_from_portal=true`
- Bathroom display normalization on storefront

**Out of scope**
- Public consumer-facing scraper status
- Email/Slack alerting
- Portal parsing “secret sauce” in public READMEs

---

## 2. API contracts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/admin/scraper-errors` | Query: `resolved`, `limit` |
| GET | `/api/v1/properties/{id}` | Optional `refresh_from_portal=true`; cached fallback |

**Table:** `real_estate.scraper_error_logs` — see `models.ScraperErrorLog`

---

## 3. Storefront

- Admin scraper error matrix (internal)
- Property detail warning when refresh fails

---

## 4. Security

- Admin routes are internal tooling — document lack of JWT until auth phase ships
- No stack traces or internal paths in public READMEs

---

## 5. Verification gates

| Gate | Command |
|------|---------|
| API | `pytest tests/test_scraper_error_telemetry.py` |
| Manual | Listing refresh failure shows cached data + admin row |

---

## 6. Drift policy

Swappable error sink via `register_scraper_error_sink` — document in spec if production sink changes.