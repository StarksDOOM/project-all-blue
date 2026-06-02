import {
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
    remote_id: row.remote_id,
    title: row.title,
    price_raw,
    currency,
    price_usd: row.price_usd,
    sector: row.sector,
    business_type: parseBusinessType(row.raw_description, row.title),
    beds: toNullableMetric(row.bedrooms),
    baths: toNullableMetric(row.bathrooms),
    area_mt2: toNullableMetric(row.square_meters),
    url: row.url,
    source_portal: row.source_portal,
    is_active: row.is_active,
    scraped_at: new Date(row.last_modified).toISOString(),
  };
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
};