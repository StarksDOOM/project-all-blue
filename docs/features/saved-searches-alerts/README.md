# Saved Searches & Asynchronous Property Match Notification Engine (STREAM 5 PHASE 3.0)

## Problem
Users invest in building precise multi-variable faceted queries via the URL-driven filter matrix (Phase 2) but have no durable way to "watch" that state. New inventory arrives continuously through the async ingestion orchestrator; without persisted alerts, users must manually re-apply filters or miss opportunities.

## Outcomes
- High-visibility "Guardar Alerta de Búsqueda" (with Bell icon) appears in the main PropertyFilterPanel **only** when non-default filters are active.
- Friendly title dialog + TanStack mutation captures the *exact* live `useFilterParams` state (post-debounce) and POSTs a canonical JSON matrix.
- Server persists `SavedSearchAlert` (filters_json + is_active). Background match engine in ingestion thread evaluates every newly-inserted `PropertyListing` against active alerts using Python predicates consistent with the Phase 2 SQL compiler.
- Structured `SavedSearchMatch` rows written for each hit (ready for future notifier).
- Dedicated management surface at `/dashboard/alerts` listing cards with filter dimension chips + mute/delete controls.
- All contracts, schemas, and evaluation rules live in the canonical spec; implementation matches it.

**Spec:** [.spec-kit/specs/api/saved-searches-alerts.spec.md](../../.spec-kit/specs/api/saved-searches-alerts.spec.md)

**Status:** Implementation follows DRAFT spec; SHIPPED only after gates + manual success on develop.

Out of scope (documented per directives): real notifications, JWT authz (user_id client-supplied for now).
