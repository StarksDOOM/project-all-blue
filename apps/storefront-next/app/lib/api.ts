import {
  AlertMatchesResponse,
  ContractRecord,
  CreateSavedSearchPayload,
  InitializeContractPayload,
  LegalContractRecord,
  PaginatedPropertiesResponse,
  PropertiesQueryParams,
  PropertyListing,
  PropertyListingApiRow,
  PropertyDetailResult,
  SavedSearchAlert,
  SavedSearchListResponse,
  ScraperErrorListResponse,
  TransactionCreatePayload,
  TransactionRecord,
  ContractGenerateResponse,
  DashboardContract,
} from "./types";

/**
 * Phase 5.0: fetch Supabase session token for protected route calls.
 * In a full app this would be:
 *   const { data: { session } } = await supabase.auth.getSession();
 *   return session?.access_token ?? null;
 * Here we support a conventional localStorage key (set by auth UI) so the
 * React Query hooks can seamlessly inject Authorization: Bearer <JWT>.
 */
function getBearerToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("supabase-access-token");
}
import type { SignatureRole } from "./transaction-types";
import { resolveBathsForDisplay } from "./bathrooms";
import { ensureRemaxPortalUrl } from "./portal-url";

const DEFAULT_API_PORT = "8000";

/** Align API host with the storefront origin to prevent CORS / connection failures in dev. */
export function resolveApiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (typeof window !== "undefined") {
    const { hostname, protocol } = window.location;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return `${protocol}//${hostname}:${DEFAULT_API_PORT}`;
    }
  }
  return fromEnv || `http://127.0.0.1:${DEFAULT_API_PORT}`;
}



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
    sqm_land: row.sqm_land != null && row.sqm_land > 0 ? row.sqm_land : null,
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
function formatFetchError(error: unknown, url: string): Error {
  if (error instanceof Error) {
    if (error.name === "AbortError") {
      return new Error(
        "Property detail request timed out. Try again without live portal sync, or ensure FastAPI is running."
      );
    }
    if (error.message === "Failed to fetch") {
      return new Error(
        `Cannot reach the API at ${resolveApiBaseUrl()}. Start FastAPI (port 8000) and use the same host as the storefront (localhost vs 127.0.0.1).`
      );
    }
    return error;
  }
  return new Error(`Failed to fetch property detail (${url}): ${String(error)}`);
}

export async function getPropertyDetail(
  id: string | number,
  options?: { portalUrl?: string; refreshFromPortal?: boolean; timeoutMs?: number }
): Promise<PropertyDetailResult> {
  const trimmedId = String(id).trim();
  if (!trimmedId) {
    throw new Error("Property id is required.");
  }

  const refreshFromPortal = options?.refreshFromPortal ?? false;
  const timeoutMs = options?.timeoutMs ?? (refreshFromPortal ? 120_000 : 30_000);
  const resolvedId = encodeURIComponent(trimmedId);
  const search = new URLSearchParams({
    refresh_from_portal: String(refreshFromPortal),
  });
  if (options?.portalUrl) {
    search.set("portal_url", options.portalUrl);
  }
  const url = `${resolveApiBaseUrl()}/api/v1/properties/${resolvedId}?${search.toString()}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });

    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Failed to fetch property detail: ${response.status} ${response.statusText}`
      );
      console.error(
        "[getPropertyDetail] HTTP error",
        trimmedId,
        response.status,
        message,
        url
      );
      throw new Error(message);
    }

    let row: PropertyListingApiRow;
    try {
      row = (await response.json()) as PropertyListingApiRow;
    } catch {
      throw new Error("Property detail response was not valid JSON.");
    }

    return {
      property: mapPropertyListing(row),
      portalRefreshFailed: Boolean(row.portal_refresh_failed),
      portalRefreshMessage: row.portal_refresh_message ?? null,
    };
  } catch (error) {
    const wrapped = formatFetchError(error, url);
    console.error(
      "[getPropertyDetail] request failed",
      trimmedId,
      wrapped.message,
      url
    );
    throw wrapped;
  } finally {
    clearTimeout(timeout);
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
  if (params.keyword) search.set("q", params.keyword);
  if (params.price_min != null) search.set("price_min", String(params.price_min));
  if (params.price_max != null) search.set("price_max", String(params.price_max));
  if (params.bedrooms_min != null) search.set("beds", String(params.bedrooms_min));
  if (params.bathrooms_min != null) search.set("baths", String(params.bathrooms_min));
  if (params.property_type) search.set("type", params.property_type);
  if (params.agency) search.set("agency", params.agency);
  if (params.include_total != null) {
    search.set("include_total", String(params.include_total));
  }

  const query = search.toString();
  return `${resolveApiBaseUrl()}/api/v1/properties${query ? `?${query}` : ""}`;
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
      `${resolveApiBaseUrl()}/api/admin/scraper-errors?${search.toString()}`,
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

  // STREAM 5 PHASE 3.0+ saved search alert endpoints (real auth via JWT token; no hardcoded test/demo user ids)
  createSavedSearchAlert: async (payload: CreateSavedSearchPayload): Promise<SavedSearchAlert> => {
    const token = getBearerToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    // do not send user_id; server sets from JWT (removes test/demo user id dependency)
    const { user_id, ...rest } = payload as any;
    const response = await fetch(`${resolveApiBaseUrl()}/api/v1/saved-searches`, {
      method: "POST",
      headers,
      body: JSON.stringify(rest),
    });
    if (!response.ok) {
      const message = await parseErrorMessage(response, `Failed to save search alert: ${response.statusText}`);
      throw new Error(message);
    }
    return response.json();
  },

  listSavedSearchAlerts: async (): Promise<SavedSearchListResponse> => {
    const token = getBearerToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    // server derives user from JWT token for scoping (no user_id query needed)
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/saved-searches`,
      { method: "GET", headers, cache: "no-store" }
    );
    if (!response.ok) {
      throw new Error(`Failed to load saved searches: ${response.statusText}`);
    }
    return response.json();
  },

  updateSavedSearchAlert: async (
    id: string,
    patch: Partial<Pick<SavedSearchAlert, "title" | "is_active">>
  ): Promise<SavedSearchAlert> => {
    const token = getBearerToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const response = await fetch(`${resolveApiBaseUrl()}/api/v1/saved-searches/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify(patch),
    });
    if (!response.ok) {
      const message = await parseErrorMessage(response, `Failed to update alert: ${response.statusText}`);
      throw new Error(message);
    }
    return response.json();
  },

  deleteSavedSearchAlert: async (id: string): Promise<void> => {
    const token = getBearerToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const response = await fetch(`${resolveApiBaseUrl()}/api/v1/saved-searches/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers,
    });
    if (!response.ok) {
      const message = await parseErrorMessage(response, `Failed to delete alert: ${response.statusText}`);
      throw new Error(message);
    }
  },

  // Phase 4.0/5.0: fetch match history + delivery status for a saved alert (token injected)
  listMatchesForAlert: async (alertId: string): Promise<AlertMatchesResponse> => {
    const token = getBearerToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    // server derives user from JWT for scoping (no user_id query)
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/saved-searches/${encodeURIComponent(alertId)}/matches`,
      { method: "GET", headers, cache: "no-store" }
    );
    if (!response.ok) {
      throw new Error(`Failed to load matches for alert: ${response.statusText}`);
    }
    return response.json();
  },

  initializeContract: async (
    propertyId: string | number,
    payload: InitializeContractPayload
  ): Promise<ContractRecord> => {
    const resolvedId = resolvePropertyId(propertyId);
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/contracts/initialize/${encodeURIComponent(resolvedId)}`,
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

  createTransaction: async (
    payload: TransactionCreatePayload
  ): Promise<TransactionRecord> => {
    const response = await fetch(`${resolveApiBaseUrl()}/api/v1/transactions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Transaction creation failed: ${response.statusText}`
      );
      throw new Error(message);
    }
    return response.json();
  },

  generateTransactionContract: async (
    transactionId: string
  ): Promise<LegalContractRecord> => {
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/transactions/${encodeURIComponent(transactionId)}/generate`,
      { method: "POST", headers: { "Content-Type": "application/json" } }
    );
    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Contract generation failed: ${response.statusText}`
      );
      throw new Error(message);
    }
    return response.json();
  },

  getTransactionContract: async (
    transactionId: string
  ): Promise<LegalContractRecord> => {
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/transactions/${encodeURIComponent(transactionId)}/contract`,
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
      }
    );
    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Failed to fetch transaction contract: ${response.statusText}`
      );
      throw new Error(message);
    }
    return response.json();
  },

  generateTransactionPdf: async (transactionId: string): Promise<LegalContractRecord> => {
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/transactions/${encodeURIComponent(transactionId)}/generate-pdf`,
      { method: "POST", headers: { "Content-Type": "application/json" } }
    );
    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `PDF generation failed: ${response.statusText}`
      );
      throw new Error(message);
    }
    return response.json();
  },

  auditCertificateDownloadUrl: (transactionId: string): string =>
    `${resolveApiBaseUrl()}/api/v1/transactions/${encodeURIComponent(transactionId)}/audit-certificate`,

  getSigningConfig: async (): Promise<{
    provider: "docusign" | "internal";
    docusign_configured: boolean;
  }> => {
    const response = await fetch(`${resolveApiBaseUrl()}/api/v1/signing/config`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
    if (!response.ok) {
      return { provider: "internal", docusign_configured: false };
    }
    return response.json();
  },

  createDocusignEnvelope: async (
    transactionId: string
  ): Promise<{ envelope_id: string; docusign_status: string; transaction_id: string }> => {
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/transactions/${encodeURIComponent(transactionId)}/docusign/envelope`,
      { method: "POST", headers: { "Content-Type": "application/json" } }
    );
    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `DocuSign envelope failed: ${response.statusText}`
      );
      throw new Error(message);
    }
    return response.json();
  },

  getDocusignSigningUrl: async (
    transactionId: string,
    role: SignatureRole,
    returnUrl: string
  ): Promise<{ signing_url: string; role: string; envelope_id: string }> => {
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/transactions/${encodeURIComponent(transactionId)}/docusign/signing-url`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, return_url: returnUrl }),
      }
    );
    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `DocuSign signing URL failed: ${response.statusText}`
      );
      throw new Error(message);
    }
    return response.json();
  },

  executeTransactionSignature: async (
    transactionId: string,
    role: SignatureRole
  ): Promise<LegalContractRecord> => {
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/transactions/${encodeURIComponent(transactionId)}/execute-signature`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      }
    );
    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Signature execution failed: ${response.statusText}`
      );
      throw new Error(message);
    }
    return response.json();
  },

  getContract: async (contractId: string): Promise<ContractRecord> => {
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/contracts/${encodeURIComponent(contractId)}`,
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

  generateContract: async (
    propertyId: string | number
  ): Promise<ContractGenerateResponse> => {
    const token = getBearerToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const response = await fetch(
      `${resolveApiBaseUrl()}/api/v1/contracts/generate`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({ property_id: propertyId }),
      }
    );

    if (!response.ok) {
      const message = await parseErrorMessage(
        response,
        `Contract generation failed: ${response.statusText}`
      );
      throw new Error(message);
    }

    return response.json();
  },

  listContracts: async (): Promise<DashboardContract[]> => {
    const token = getBearerToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const response = await fetch(`${resolveApiBaseUrl()}/api/v1/contracts`, {
      method: "GET",
      headers,
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`Failed to load contracts: ${response.statusText}`);
    }
    return response.json();
  },
};