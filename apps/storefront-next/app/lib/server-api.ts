/**
 * Server-only FastAPI fetch helpers (RSC prefetch). Do not import from client components.
 */

import { mapPropertyListing } from "@/lib/api";
import type {
  LegalContractRecord,
  PaginatedPropertiesResponse,
  PropertiesQueryParams,
  PropertyDetailResult,
  PropertyListing,
  PropertyListingApiRow,
} from "@/lib/types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type SigningConfigRecord = {
  provider: "docusign" | "internal";
  docusign_configured: boolean;
};

async function parseErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function fetchTransactionContract(
  transactionId: string
): Promise<LegalContractRecord> {
  const response = await fetch(
    `${API_BASE}/api/v1/transactions/${encodeURIComponent(transactionId)}/contract`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    }
  );
  if (!response.ok) {
    throw new Error(
      await parseErrorMessage(response, `Failed to fetch transaction contract: ${response.status}`)
    );
  }
  return response.json() as Promise<LegalContractRecord>;
}

export async function fetchPropertiesPage(
  params: PropertiesQueryParams = {}
): Promise<{ metadata: PaginatedPropertiesResponse["metadata"]; data: PropertyListing[] }> {
  const search = new URLSearchParams();
  if (params.page != null) search.set("page", String(params.page));
  if (params.limit != null) search.set("limit", String(params.limit));
  if (params.source_portal) search.set("source_portal", params.source_portal);
  if (params.sector) search.set("sector", params.sector);
  if (params.include_total != null) {
    search.set("include_total", String(params.include_total));
  }

  const query = search.toString();
  const response = await fetch(
    `${API_BASE}/api/v1/properties${query ? `?${query}` : ""}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    }
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch properties: ${response.status}`);
  }
  const result = (await response.json()) as PaginatedPropertiesResponse;
  return {
    metadata: result.metadata,
    data: result.data.map(mapPropertyListing),
  };
}

export async function fetchPropertyDetail(
  id: string,
  options?: { refreshFromPortal?: boolean }
): Promise<PropertyDetailResult> {
  const refreshFromPortal = options?.refreshFromPortal ?? false;
  const search = new URLSearchParams({
    refresh_from_portal: String(refreshFromPortal),
  });
  const response = await fetch(
    `${API_BASE}/api/v1/properties/${encodeURIComponent(id.trim())}?${search.toString()}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    }
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch property detail: ${response.status}`);
  }
  const row = (await response.json()) as PropertyListingApiRow;
  return {
    property: mapPropertyListing(row),
    portalRefreshFailed: Boolean(row.portal_refresh_failed),
    portalRefreshMessage: row.portal_refresh_message ?? null,
  };
}

export async function fetchSigningConfig(): Promise<SigningConfigRecord> {
  const response = await fetch(`${API_BASE}/api/v1/signing/config`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    return { provider: "internal", docusign_configured: false };
  }
  return response.json() as Promise<SigningConfigRecord>;
}