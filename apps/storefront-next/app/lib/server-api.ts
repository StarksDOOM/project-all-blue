/**
 * Server-only FastAPI fetch helpers (RSC prefetch). Do not import from client components.
 */

import type { LegalContractRecord } from "@/lib/types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

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