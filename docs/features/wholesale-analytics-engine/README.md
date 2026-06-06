# Wholesale Pricing & Analytics Engine

**Stream:** STREAM 6 PHASE 1.3  
**Status:** DRAFT  

## Problem

Agents need an automated deal analyzer to determine if a property qualifies for a wholesale
assignment. Manual calculation is error-prone and leaks margin data to Agents who should only
see target prices, not the business model behind them.

## Outcomes

- Automated ARV derived from live sector median price-per-square-meter data.
- MAO, Assignment Fee, and Pitch Price computed deterministically with hardcoded heuristics.
- Role-gated UI: Agents see a pitch-ready script; Admins see the full financial breakdown.
- Backend route guarded by RBAC — CLIENT roles blocked at the API layer.

## Out of Scope

- Manual ARV override by users.
- Configurable formula constants (constants are hardcoded invariants per spec).
- Comps sourced from external data providers (sector DB average only).
- JWT/tenant binding (pending future auth hardening phase).
