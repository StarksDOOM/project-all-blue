# Internal Leads CRM Feed

**Feature README** | STREAM 6 PHASE 1.7.1 | All Blue Core

## Problem

After Phase 1.7 deployed the public lead magnet calculator at `/invest/[location]`, captured leads
(email, simulation state, traffic source) are stored in Postgres but completely invisible to the
internal sales team. There is no UI surface for agents to see who submitted a lead or what
investment scenario they were running when they unlocked the blur gate.

## Outcomes

- Sales agents can access `/dashboard/leads` to view all inbound leads in a high-density CRM table.
- Each row surfaces the exact simulation context (purchase price, nightly rate, occupancy) the
  investor was modelling — enabling personalized follow-up conversations.
- Leads are sorted newest first so agents can action the hottest inbound traffic immediately.

## Spec

API contracts, endpoint signatures, and verification gates:
→ [`.spec-kit/specs/api/internal-leads-crm.spec.md`](../../../.spec-kit/specs/api/internal-leads-crm.spec.md)

## Out of Scope

- RBAC auth guard on the list endpoint (Phase 5.0).
- Lead status management or CRM pipeline stages.
- External CRM sync or email outreach.
