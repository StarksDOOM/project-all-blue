# Multi-Source Lead Magnet Engine

## Problem
We have a highly accurate, dynamic STR ROI projection calculator on the storefront that leverages local 2026 Dominican Republic rental assumptions. However, this tool is gated behind agent/admin login. To drive organic and paid traffic and convert visitors into high-intent investor leads, we need to expose a public-facing version of the calculator on specific location pages, capturing investor interest without initial signup barriers.

## Outcomes
- **Dynamic Public Landing Pages**: High-converting dynamic landing pages (`/invest/[location]`) highlighting local market potential.
- **Traffic Attribution**: Automatically track and attribute leads to traffic sources (such as Facebook ads, newsletters, or social channels) using URL queries (`?src=...`).
- **Interactive Visual Blur Gate**: Allow users to dynamically interact with sliders and view high-level metrics, but apply a visual lock/blur over final net profit projections.
- **Email Capture Conversion**: Un-blur the advanced projection cards immediately when the user provides their email, registering them directly in Postgres as investor leads.
- **STATISTICS / DATA**: Captured parameters (prices, nightly rates, occupancy, maintenance) represent the exact interest profile of the lead for future personalized outreach.

## Related Specifications
- [Multi-Source Lead Magnet Engine Spec](../../../.spec-kit/specs/api/lead-magnet-engine.spec.md)
