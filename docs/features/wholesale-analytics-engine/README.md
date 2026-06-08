# Wholesale Pricing & Analytics Engine (Turnkey Properties)

**Stream:** STREAM 6 PHASE 1.3  
**Status:** DRAFT  

## Problem

Agents need a fast, automated deal analysis for turnkey/new properties to determine if they qualify for a wholesale assignment and at what price. Manual calculation is error-prone and leaks margin data to Agents who should only see target prices, not the business model behind them.

## Outcomes

- Automated Estimated Market Value (EMV) derived from live sector median price-per-square-meter data.
- **NO repair calculations** (suitable for turnkey/new properties).
- MAO and Assignment Fee computed deterministically with hardcoded heuristics.
- Role-gated UI: Agents see a pitch-ready guide ("Guía de Oferta") with MAO and Pitch Price; Admins see the full financial breakdown including sector median, EMV, and assignment fee.
- Backend route guarded by RBAC — CLIENT roles blocked at the API layer.

## Out of Scope

- Manual EMV override by users.
- Configurable formula constants (constants are hardcoded invariants per spec).
- Comps sourced from external data providers (sector DB average only).
- JWT/tenant binding (pending future auth hardening phase).
