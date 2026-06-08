import type { PropertyFilterParams } from "./property-filters";

/** Normalized listing shape used across the storefront UI. */
export interface PropertyListing {
  /** Numeric convenience id (parsed from remote_id when possible). */
  id: number;
  /** Internal database primary key (Blu id, e.g. #BLU-A1B2C3D4). */
  blu_id: string;
  remote_id: string;
  title: string;
  price_raw: number;
  currency: string;
  price_usd: number;
  price_dop: number | null;
  list_price: number | null;
  image_urls: string[];
  sector: string;
  province: string;
  business_type: string;
  beds: number | null;
  baths: number | null;
  area_mt2: number | null;
  sqm_land: number | null;
  agent_name: string | null;
  agent_phone: string | null;
  agent_email: string | null;
  agent_whatsapp: string | null;
  agent_agency: string | null;
  raw_description: string;
  url: string;
  /** Absolute https URL for RE/MAX storefront (derived from url + remote_id). */
  portal_url: string;
  source_portal: string;
  is_active: boolean;
  scraped_at: string;
}

/** Raw row returned by FastAPI /api/v1/properties (SQLModel serialization). */
export interface PropertyListingApiRow {
  id: string;
  remote_id: string;
  source_portal: string;
  url: string;
  title: string;
  price_usd: number;
  price_dop?: number | null;
  list_price?: number | null;
  image_urls?: string[] | string | null;
  province: string;
  sector: string;
  bedrooms: number;
  bathrooms: number;
  square_meters: number;
  sqm_land?: number | null;
  listing_currency?: string | null;
  agent_name?: string | null;
  agent_phone?: string | null;
  agent_email?: string | null;
  agent_whatsapp?: string | null;
  agent_agency?: string | null;
  raw_description: string;
  is_active: boolean;
  last_modified: number;
  tenant_id?: string;
  server_version?: number;
  deleted_at?: string | null;
  portal_refresh_failed?: boolean;
  portal_refresh_message?: string | null;
}

export interface ScraperErrorLogRow {
  id: string;
  remote_id: string | null;
  url: string | null;
  scraper_method: string;
  error_type: string;
  stack_trace: string;
  resolved: boolean;
  created_at: string;
}

export interface ScraperErrorListResponse {
  data: ScraperErrorLogRow[];
  total: number;
}

export interface PropertyDetailResult {
  property: PropertyListing;
  portalRefreshFailed: boolean;
  portalRefreshMessage: string | null;
}

export interface PropertiesQueryParams {
  page?: number;
  limit?: number;
  source_portal?: string;
  sector?: string;
  keyword?: string;
  price_min?: number;
  price_max?: number;
  bedrooms_min?: number;
  bathrooms_min?: number;
  property_type?: BusinessTypeFilter;
  agency?: string;
  /** When false, API skips COUNT(*) and uses has_next (faster page changes). */
  include_total?: boolean;
}

export interface PropertiesPageMetadata {
  total: number | null;
  page: number;
  limit: number;
  pages: number | null;
  has_next?: boolean;
}

export interface PaginatedPropertiesResponse {
  metadata: PropertiesPageMetadata;
  data: PropertyListingApiRow[];
}

export type BusinessTypeFilter = "" | "alquiler" | "venta";

export type ContractType = "RENTAL" | "PURCHASE_RESERVATION" | "MANAGEMENT";
export type ContractStatus = "DRAFT" | "SIGNED" | "ESCROW_HOLD" | "COMPLETED";

export interface InitializeContractPayload {
  buyer_name: string;
  buyer_id: string;
  seller_name: string;
  seller_id: string;
}

export type TransactionSessionStatus = "DRAFT" | "REVIEW" | "GENERATED" | "EXECUTED";

export interface TransactionCreatePayload {
  property_id: string;
  buyer_name: string;
  buyer_id_doc: string;
  seller_name: string;
  seller_id_doc: string;
  agreed_price: number;
  currency: string;
}

export interface TransactionRecord {
  id: string;
  property_id: string;
  property_remote_id?: string | null;
  property_title?: string | null;
  buyer_name: string;
  buyer_id_doc: string;
  seller_name: string;
  seller_id_doc: string;
  agreed_price: number;
  currency: string;
  status: TransactionSessionStatus;
  created_at: string;
  updated_at: string;
  buyer_signed_at?: string | null;
  seller_signed_at?: string | null;
  signature_telemetry?: Record<string, unknown>;
  is_locked?: boolean;
}

export interface LegalContractRecord {
  id: string;
  transaction_session_id: string;
  file_path: string | null;
  storage_url: string | null;
  document_body: string;
  generated_at: string;
  version_hash: string;
  document_hash?: string | null;
  pdf_file_path?: string | null;
  has_secure_pdf?: boolean;
  docusign_envelope_id?: string | null;
  docusign_status?: string | null;
  has_audit_certificate?: boolean;
  audit_certificate_path?: string | null;
  transaction: TransactionRecord;
  property: {
    id: string;
    remote_id: string;
    title: string;
    sector: string;
    province: string;
    bathrooms: number;
    bedrooms: number;
    square_meters: number;
    sqm_land: number | null;
  };
}

export interface ContractRecord {
  id: string;
  contract_number: string;
  property_id: string;
  property_remote_id: string;
  property_title: string;
  business_type: string;
  contract_type: ContractType;
  status: ContractStatus;
  client_name: string;
  client_rnc_or_cedula: string;
  buyer_name: string;
  buyer_id: string;
  seller_name: string;
  seller_id: string;
  total_value_usd: number;
  earnest_deposit_usd: number;
  execution_date: string;
  document_body: string;
  last_modified: number;
  server_version: number;
}

/** STREAM 5 PHASE 3.0 Saved Search Alert (filters_json mirrors PropertyFilterParams shape) */
export interface SavedSearchAlert {
  id: string;
  user_id: string;
  title: string;
  filters_json: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  last_matched_at?: string | null;
}

export interface SavedSearchListResponse {
  data: SavedSearchAlert[];
}

export interface CreateSavedSearchPayload {
  user_id?: string; // optional/ignored; server uses authenticated user from JWT (Phase 5.0+)
  title: string;
  filters: Partial<PropertyFilterParams>; // subset without page
}

/** Phase 4.0 match with delivery status for history ledger */
export interface SavedSearchMatchWithDelivery {
  id: string;
  property_id: string;
  matched_at: string;
  match_details: Record<string, unknown>;
  delivery_status: "pending" | "sent" | "failed";
  sent_at?: string | null;
  retry_count: number;
}

export interface AlertMatchesResponse {
  alert_id: string;
  matches: SavedSearchMatchWithDelivery[];
}

export interface ContractGenerateResponse {
  envelope_id: string;
  status: string;
  contract_id: string;
}

export interface DashboardContractProperty {
  title: string;
  price_usd: number;
}

export interface DashboardContract {
  id: string;
  created_at: string;
  status: string | null;
  property: DashboardContractProperty | null;
}

/** Wholesale deal metrics returned by GET /api/v1/analytics/wholesale/{property_id}. */
export interface WholesaleDealMetrics {
  property_id: string;
  sector: string;
  sector_median_price_per_sqm: number;
  auto_emv: number;
  mao: number;
  assignment_fee: number;
  pitch_price: number;
}
