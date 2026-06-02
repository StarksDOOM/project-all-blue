import {
  ContractRecord,
  InitializeContractPayload,
  PaginatedPropertiesResponse,
  PropertiesQueryParams,
  PropertyListing,
  PropertyListingApiRow,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function parseCurrency(
  rawDescription: string,
  priceUsd: number,
  priceDop?: number | null
): { currency: string; price_raw: number } {
  const currencyMatch = rawDescription.match(/currency=([A-Z]{3})/i);
  if (currencyMatch) {
    const currency = currencyMatch[1].toUpperCase();
    if (currency === "DOP") {
      return {
        currency: "DOP",
        price_raw: priceDop ?? priceUsd * 59.5,
      };
    }
    return { currency: "USD", price_raw: priceUsd };
  }

  if (priceDop != null && priceDop > priceUsd * 10) {
    return { currency: "DOP", price_raw: priceDop };
  }

  return { currency: "USD", price_raw: priceUsd };
}

function parseBusinessType(rawDescription: string, title: string): string {
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
  const { currency, price_raw } = parseCurrency(
    row.raw_description,
    row.price_usd,
    row.price_dop
  );

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
    sector: row.sector,
    province: row.province,
    business_type: parseBusinessType(row.raw_description, row.title),
    beds: toNullableMetric(row.bedrooms),
    baths: toNullableMetric(row.bathrooms),
    area_mt2: toNullableMetric(row.square_meters),
    raw_description: row.raw_description,
    url: row.url,
    source_portal: row.source_portal,
    is_active: row.is_active,
    scraped_at: new Date(row.last_modified).toISOString(),
  };
}

/**
 * Fetch a single property by internal Blu id or portal remote_id.
 */
export async function getPropertyDetail(id: string | number): Promise<PropertyListing> {
  const resolvedId = encodeURIComponent(String(id).trim());
  const url = `${BASE_URL}/api/v1/properties/${resolvedId}`;

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
    return mapPropertyListing(row);
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