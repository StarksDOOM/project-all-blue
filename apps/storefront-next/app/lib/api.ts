import {
  ContractRecord,
  InitializeContractPayload,
  PaginatedPropertiesResponse,
  PropertiesQueryParams,
  PropertyListing,
  PropertyListingApiRow,
  PropertyDetailResult,
  ScraperErrorListResponse,
} from "./types";
import { resolveBathsForDisplay } from "./bathrooms";
import { ensureRemaxPortalUrl } from "./portal-url";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

/** Portal list currency from enriched raw_description (not the derived DOP mirror). */
function parseCurrencyFromMeta(rawDescription: string): string | null {
  const match = rawDescription.match(/currency=([A-Z]{3})/i);
  return match?.[1]?.toUpperCase() ?? null;
}

function parseImageUrls(value: PropertyListingApiRow["image_urls"]): string[] {
  if (Array.isArray(value)) {
    return value.filter((url) => typeof url === "string" && url.length > 0);
  }
  if (typeof value === "string" && value.trim().startsWith("[")) {
    try {
      const parsed = JSON.parse(value) as unknown;
      if (Array.isArray(parsed)) {
        return parsed.filter((url): url is string => typeof url === "string" && url.length > 0);
      }
    } catch {
      return [];
    }
  }
  return [];
}

/**
 * Portal list price: prefer explicit ``list_price`` (detail enrichment), else the
 * sync column that matches ``listing_currency`` (price_usd for USD, price_dop for DOP).
 */
function resolveListingPrice(row: PropertyListingApiRow): {
  currency: string;
  price_raw: number;
  list_price: number | null;
} {
  const currency = (
    row.listing_currency ||
    parseCurrencyFromMeta(row.raw_description) ||
    "USD"
  ).toUpperCase();

  const explicitList =
    row.list_price != null && row.list_price > 0 ? row.list_price : null;
  if (explicitList) {
    return { currency, price_raw: explicitList, list_price: explicitList };
  }

  if (currency === "DOP") {
    const dop =
      row.price_dop != null && row.price_dop > 0 ? row.price_dop : null;
    if (dop) {
      return { currency: "DOP", price_raw: dop, list_price: dop };
    }
  } else if (row.price_usd > 0) {
    return { currency: "USD", price_raw: row.price_usd, list_price: row.price_usd };
  }

  return { currency, price_raw: 0, list_price: null };
}

function parseBusinessType(rawDescription: string, title: string): string {
  const typed = rawDescription.match(/business_type=([a-z]+)/i);
  if (typed?.[1]) {
    return typed[1].toLowerCase();
  }

  const segments = rawDescription.split("|").map((part) => part.trim().toLowerCase());
  const typeSegment = segments.find(
    (segment) => segment.includes("alquiler") || segment.includes("venta")
  );

  if (typeSegment?.includes("alquiler")) {
    return "alquiler";
  }
  if (typeSegment?.includes("venta")) {
    return "venta";
  }

  const loweredTitle = title.toLowerCase();
  if (loweredTitle.includes("alquiler")) {
    return "alquiler";
  }
  return "venta";
}

function toNullableMetric(value: number): number | null {
  return value > 0 ? value : null;
}

export function mapPropertyListing(row: PropertyListingApiRow): PropertyListing {
  const { currency, price_raw, list_price } = resolveListingPrice(row);

  const numericId = Number.parseInt(row.remote_id, 10);

  return {
    id: Number.isFinite(numericId) ? numericId : 0,
    blu_id: row.id,
    remote_id: row.remote_id,
    title: row.title,
    price_raw,
    currency,
    price_usd: row.price_usd,
    price_dop: row.price_dop ?? null,
    list_price,
    image_urls: parseImageUrls(row.image_urls),
    sector: row.sector,
    province: row.province,
    business_type: parseBusinessType(row.raw_description, row.title),
    beds: toNullableMetric(row.bedrooms),
    baths: resolveBathsForDisplay(row.bathrooms, row.raw_description),
    area_mt2: toNullableMetric(row.square_meters),
    sqm_land: toNullableMetric(row.sqm_land ?? null),
    agent_name: row.agent_name ?? null,
    agent_phone: row.agent_phone ?? null,
    agent_email: row.agent_email ?? null,
    agent_whatsapp: row.agent_whatsapp ?? null,
    agent_agency: row.agent_agency ?? null,
    raw_description: row.raw_description,
    url: row.url,
    portal_url: ensureRemaxPortalUrl(row.url, row.remote_id),
    source_portal: row.source_portal,
    is_active: row.is_active,
    scraped_at: new Date(row.last_modified).toISOString(),
  };
}

/**
 * Fetch a single property by internal Blu id or portal remote_id.
 */
export async function getPropertyDetail(
  id: string | number,
  options?: { portalUrl?: string; refreshFromPortal?: boolean }
): Promise<PropertyDetailResult> {
  const resolvedId = encodeURIComponent(String(id).trim());
  const search = new URLSearchParams({
    refresh_from_portal: String(options?.refreshFromPortal ?? true),
  });
  if (options?.portalUrl) {
    search.set("portal_url", options.portalUrl);
  }
  const url = `${BASE_URL}/api/v1/properties/${resolvedId}?${search.toString()}`;

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });

    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Failed to fetch property detail: ${response.status} ${response.statusText}`
      );
      console.error("[getPropertyDetail]", { id, status: response.status, message, url });
      throw new Error(message);
    }

    const row: PropertyListingApiRow = await response.json();
    return {
      property: mapPropertyListing(row),
      portalRefreshFailed: Boolean(row.portal_refresh_failed),
      portalRefreshMessage: row.portal_refresh_message ?? null,
    };
  } catch (error) {
    if (error instanceof Error) {
      console.error("[getPropertyDetail] request failed", { id, message: error.message, url });
      throw error;
    }
    console.error("[getPropertyDetail] unknown failure", { id, url });
    throw new Error("Failed to fetch property detail due to an unexpected error.");
  }
}

function buildPropertiesUrl(params: PropertiesQueryParams): string {
  const search = new URLSearchParams();

  if (params.page != null) {
    search.set("page", String(params.page));
  }
  if (params.limit != null) {
    search.set("limit", String(params.limit));
  }
  if (params.source_portal) {
    search.set("source_portal", params.source_portal);
  }
  if (params.sector) {
    search.set("sector", params.sector);
  }

  const query = search.toString();
  return `${BASE_URL}/api/v1/properties${query ? `?${query}` : ""}`;
}

function resolvePropertyId(propertyId: string | number): string {
  return String(propertyId);
}

async function parseErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      return body.detail.map((item: { msg?: string }) => item.msg ?? "Validation error").join(", ");
    }
  } catch {
    // ignore JSON parse failures
  }
  return fallback;
}

export const api = {
  getScraperErrors: async (params?: {
    resolved?: boolean;
    limit?: number;
  }): Promise<ScraperErrorListResponse> => {
    const search = new URLSearchParams();
    search.set("resolved", String(params?.resolved ?? false));
    if (params?.limit != null) {
      search.set("limit", String(params.limit));
    }
    const response = await fetch(
      `${BASE_URL}/api/admin/scraper-errors?${search.toString()}`,
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
      }
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch scraper errors: ${response.statusText}`);
    }
    return response.json();
  },

  getPropertiesPage: async (
    params: PropertiesQueryParams = {}
  ): Promise<{ metadata: PaginatedPropertiesResponse["metadata"]; data: PropertyListing[] }> => {
    const response = await fetch(buildPropertiesUrl(params), {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch properties: ${response.statusText}`);
    }

    const result: PaginatedPropertiesResponse = await response.json();

    return {
      metadata: result.metadata,
      data: result.data.map(mapPropertyListing),
    };
  },

  initializeContract: async (
    propertyId: string | number,
    payload: InitializeContractPayload
  ): Promise<ContractRecord> => {
    const resolvedId = resolvePropertyId(propertyId);
    const response = await fetch(
      `${BASE_URL}/api/v1/contracts/initialize/${encodeURIComponent(resolvedId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Contract initialization failed: ${response.statusText}`
      );
      throw new Error(message);
    }

    return response.json();
  },

  getContract: async (contractId: string): Promise<ContractRecord> => {
    const response = await fetch(
      `${BASE_URL}/api/v1/contracts/${encodeURIComponent(contractId)}`,
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Failed to fetch contract: ${response.statusText}`
      );
      throw new Error(message);
    }

    return response.json();
  },
};