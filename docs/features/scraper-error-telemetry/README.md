# Scraper Error Telemetry & Listing Data Integrity

**Status:** Shipped on `develop`  
**Scope:** Listing ingestion pipeline and storefront presentation

This document describes **why** this work exists and **what user-visible problems it addresses**. It does **not** document ingestion mechanics, portal parsing strategies, internal APIs, or operator runbooks.

---

## Context

All Blue Core syncs third-party real estate listings into a central inventory and presents them on an internal storefront. Portal data changes frequently; the product must stay usable even when live sync fails for a single listing.

---

## Problems addressed

1. **Silent data pipeline failures** — Scrape or enrichment errors were hard to see in aggregate; operations could not quickly tell which listings were unhealthy.

2. **Bad experience when live refresh fails** — Property detail could error or feel broken instead of showing last-known good data with a clear warning.

3. **Incorrect or empty bathroom counts** — Dashboard and detail KPIs sometimes disagreed with what the listing description already stated.

4. **No in-product health view** — Engineering relied on logs; there was no simple internal surface to review unresolved sync issues.

---

## Outcomes (what improved)

- Durable tracking of listing sync failures for internal review.
- Property detail **fails gracefully**: cached data remains available with an explicit “live sync failed” signal.
- More consistent **bathroom** display aligned with listing content when structured fields are missing.
- Internal admin view of unresolved scraper-related issues (operators only).

---

## Out of scope

- Public-facing scraper status on consumer pages.
- Automated alerting to email/Slack.
- Step-by-step usage or debugging guides in this repo.
- Documentation of portal-specific extraction or investigation tooling.

---

## Verification

- Automated test suite passes on `apps/api-fastapi`.
- Manual operator confirmation on representative listings before merge.

---

*Problem/solution summary only. Implementation details remain in private engineering notes and code review, not in this file.*