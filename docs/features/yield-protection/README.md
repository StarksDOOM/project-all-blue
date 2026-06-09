# Yield Protection & UI State Fix (STREAM 6 PHASE 1.8.1)

## Problem Statement
1. **Dirty Scraper Data**: Occasionally, scraped property data carries incorrect square footage (e.g. lot size instead of interior construction size). When calculating default monthly maintenance assumptions (`square_meters * 2.50`), this results in artificially bloated monthly fees (e.g. $800+/mo), rendering default STR and LTR NOI projections negative on the storefront.
2. **Broken Toggle State**: The LTR / STR toggle on the storefront's cash buyer dashboard was unresponsive to clicks, failing to swap between long-term rental and short-term rental calculators.
3. **Toxic Deals**: Properties that exhibit negative default yield projections under both STR and LTR calculations clutter the retail consumer feed and distract potential investors.

## Solution
1. **Sanity Cap**: Enforce a database/Python level monthly maintenance sanity cap of `$400.00` (computed as `min(square_meters * 2.50, 400.0)`).
2. **Toggle Fix**: Correctly wire the local tab state using `activeTab` to swap slider inputs and recalculate underwriting metrics seamlessly on the storefront.
3. **Smart Strategy Pivot**: Calculate default NOI for both strategies on mount. If the default STR NOI is negative but the LTR NOI is positive, automatically pivot the dashboard tab to "Long-Term (LTR)" upon load.
4. **Toxic Deal Filter**: Automatically hide any listing from the storefront list query that yields negative default NOI across both STR and LTR strategies.

## Outcomes
- Normalizes maintenance costs to realistic ranges.
- Restores interactive toggling capabilities to the Cash Buyer Pitch Dashboard.
- Highlights LTR strategy automatically when Airbnb metrics are unfavorable.
- Purges low-yielding or broken deals from the primary investor storefront catalog.
