import type { BusinessTypeFilter } from "@/lib/types";

/** Storefront + API shared facet shape (query param mapping in api.ts). */
export interface PropertyFilterParams {
  source_portal?: string;
  sector?: string;
  keyword?: string;
  price_min?: number;
  price_max?: number;
  bedrooms_min?: number;
  bathrooms_min?: number;
  property_type?: BusinessTypeFilter;
  agency?: string;
  page?: number;
}

export const DEFAULT_PROPERTY_FILTERS: PropertyFilterParams = {
  source_portal: "remaxrd",
  page: 1,
};

export function filtersFingerprint(filters: PropertyFilterParams): string {
  const normalized = {
    source_portal: filters.source_portal ?? "",
    sector: filters.sector ?? "",
    keyword: filters.keyword ?? "",
    price_min: filters.price_min ?? "",
    price_max: filters.price_max ?? "",
    bedrooms_min: filters.bedrooms_min ?? "",
    bathrooms_min: filters.bathrooms_min ?? "",
    property_type: filters.property_type ?? "",
    agency: filters.agency ?? "",
  };
  return JSON.stringify(normalized);
}

export function parseFiltersFromSearchParams(
  params: URLSearchParams
): PropertyFilterParams {
  const parseNum = (key: string) => {
    const raw = params.get(key);
    if (!raw) return undefined;
    const value = Number(raw);
    return Number.isFinite(value) ? value : undefined;
  };

  const type = params.get("type");
  const property_type: BusinessTypeFilter =
    type === "venta" || type === "alquiler" ? type : "";

  return {
    source_portal: params.get("source_portal") ?? DEFAULT_PROPERTY_FILTERS.source_portal,
    sector: params.get("sector") ?? undefined,
    keyword: params.get("q") ?? undefined,
    price_min: parseNum("price_min"),
    price_max: parseNum("price_max"),
    bedrooms_min: parseNum("beds"),
    bathrooms_min: parseNum("baths"),
    property_type,
    agency: params.get("agency") ?? undefined,
    page: parseNum("page") ?? 1,
  };
}

export function filtersToSearchParams(filters: PropertyFilterParams): URLSearchParams {
  const search = new URLSearchParams();
  if (filters.source_portal) search.set("source_portal", filters.source_portal);
  if (filters.sector) search.set("sector", filters.sector);
  if (filters.keyword) search.set("q", filters.keyword);
  if (filters.price_min != null) search.set("price_min", String(filters.price_min));
  if (filters.price_max != null) search.set("price_max", String(filters.price_max));
  if (filters.bedrooms_min != null) search.set("beds", String(filters.bedrooms_min));
  if (filters.bathrooms_min != null) search.set("baths", String(filters.bathrooms_min));
  if (filters.property_type) search.set("type", filters.property_type);
  if (filters.agency) search.set("agency", filters.agency);
  if (filters.page != null && filters.page > 1) search.set("page", String(filters.page));
  return search;
}