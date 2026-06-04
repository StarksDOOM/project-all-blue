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
  list: (page: number, sector: string, businessType: string) =>
    [...propertyKeys.all, page, sector, businessType] as const,
  total: (sector: string) => ["properties-total", sector] as const,
  detail: (id: string, mode: "cached" | "portal") =>
    ["property-detail", id, mode] as const,
};