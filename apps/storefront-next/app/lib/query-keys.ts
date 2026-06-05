/** TanStack Query cache tokens — single source of truth for prefetch, hydrate, SSE invalidation. */

export const transactionKeys = {
  all: ["transaction-contract"] as const,
  contract: (transactionId: string) =>
    [...transactionKeys.all, transactionId] as const,
};

export const signingKeys = {
  config: () => ["signing-config"] as const,
};

export const propertyKeys = {
  all: ["properties"] as const,
  list: (page: number, fingerprint: string) =>
    [...propertyKeys.all, "list", page, fingerprint] as const,
  total: (fingerprint: string) => [...propertyKeys.all, "total", fingerprint] as const,
  detail: (id: string, mode: "cached" | "portal") =>
    ["property-detail", id, mode] as const,
};

export const savedSearchKeys = {
  all: ["saved-searches"] as const,
  list: () => [...savedSearchKeys.all, "list"] as const,
  matches: (alertId: string) => [...savedSearchKeys.all, "matches", alertId] as const,
};