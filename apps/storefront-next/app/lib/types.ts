/** Normalized listing shape used across the storefront UI. */
export interface PropertyListing {
  id: number;
  remote_id: string;
  title: string;
  price_raw: number;
  currency: string;
  price_usd: number;
  sector: string;
  business_type: string;
  beds: number | null;
  baths: number | null;
  area_mt2: number | null;
  url: string;
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
  province: string;
  sector: string;
  bedrooms: number;
  bathrooms: number;
  square_meters: number;
  raw_description: string;
  is_active: boolean;
  last_modified: number;
  tenant_id?: string;
  server_version?: number;
  deleted_at?: string | null;
}

export interface PropertiesQueryParams {
  page?: number;
  limit?: number;
  source_portal?: string;
  sector?: string;
}

export interface PropertiesPageMetadata {
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface PaginatedPropertiesResponse {
  metadata: PropertiesPageMetadata;
  data: PropertyListingApiRow[];
}

export type BusinessTypeFilter = "" | "alquiler" | "venta";