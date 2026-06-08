# Airbnb ROI & Pitch Engine

## Problem

Agents selling Dominican Republic properties to U.S. cash buyers currently rely on manual spreadsheet calculations to estimate Short-Term Rental (STR) yields and Cash-on-Cash returns. This creates friction in the sales pitch and introduces calculation errors.

## Outcomes

- **Agents** can instantly generate STR yield projections (6-month, 1-year, 3-year) directly from the property detail page.
- **Cash buyers** receive a professional, data-driven pitch showing Net Operating Income and Cash-on-Cash Return percentages.
- **No new infrastructure** — extends the existing `WholesalePricingEngine` and wholesale analytics API endpoint.
- **Interactive controls** — sliders for nightly rate, occupancy, and HOA allow real-time scenario modelling.

## Architecture

The STR metrics are computed server-side by the stateless `WholesalePricingEngine` using caller-supplied assumptions (nightly rate, occupancy, HOA). No new database tables or external API calls are required.

The frontend `CashBuyerPitchDashboard` component renders below the existing "Guía de Oferta" wholesale card on the property detail page.

## Spec Reference

Full API contracts and formula definitions: [`.spec-kit/specs/api/airbnb-roi-engine.spec.md`](../../../.spec-kit/specs/api/airbnb-roi-engine.spec.md)
