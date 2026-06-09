# Feature: Asset Classifier & Multi-Yield Engine

This feature implements automated asset classification at the property ingestion layer. By determining the **Listing Type** (For Sale vs For Rent) and **Property Type** (Residential vs Commercial) of scraped listings on the fly, the system improves target underwriting precision and optimizes customer-facing feeds.

## Business Problem & Outcomes

### The Problem
* The backend pricing engine (`WholesalePricingEngine` and `StrDefaultPredictor`) assumes all incoming properties are for sale and evaluated strictly under Short-Term Rental (STR/Airbnb) calculations.
* Ingesting raw commercial spaces or monthly rental listings breaks the underwriting math (e.g. calculating Airbnb ROI on an office space is financially meaningless).
* Standard storefront feeds get cluttered with rental properties, which are intended exclusively for internal acquisition campaigns and acquisition-driven cold outreach.

### Expected Outcomes
1. **Automated Keyword Classifier**: Properties are scanned upon ingestion using NLP rules (checking keywords in descriptions and titles) to tag their Listing Type and Property Type.
2. **Clean Storefront Feeds**: Rental properties (`FOR_RENT`) are automatically filtered out from the retail customer property feed.
3. **Underwriting Flexibility**:
   * **Commercial Properties**: Underwritten using Capitalization Rates (Cap Rates) based on size, monthly rent per square meter, vacancy, and fixed operating expenses (taxes/insurance).
   * **LTR Corporate Leases**: Evaluated using corporate lease long-term rental (LTR) parameters (vacancy, PM fee, monthly maintenance) inside the residential dashboard.
4. **Adaptive Storefront Dashboards**: The property details analytics pane seamlessly swaps calculations and controls depending on the property classification.

## Underwriting Models

### 1. Commercial Cap Rate
Calculated for properties classified as `COMMERCIAL`:
* **Annual Gross Rent** = `(size_sqm × monthly_rent_per_sqm) × 12`
* **Effective Gross Income (EGI)** = `Annual Gross Rent × (1 − vacancy_rate)`
* **Annual NOI** = `EGI − annual_taxes_insurance`
* **Cap Rate %** = `(Annual NOI / pitch_price) × 100`

### 2. Long-Term Rental (LTR) Cap Rate
Calculated for residential properties when evaluated for corporate/long-term leasing:
* **Annual Gross Rent** = `monthly_rent × 12`
* **Effective Gross Rent** = `Annual Gross Rent × (1 − vacancy_rate)`
* **Operating Expenses** = `(Annual Gross Rent × pm_fee_pct) + (monthly_maintenance × 12)`
* **Annual NOI** = `Effective Gross Rent − Operating Expenses`
* **Cap Rate %** = `(Annual NOI / pitch_price) × 100`
