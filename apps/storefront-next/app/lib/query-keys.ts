/** TanStack Query cache tokens — single source of truth for prefetch, hydrate, SSE invalidation. */

export const transactionKeys = {
  all: ["transaction-contract"] as const,
  contract: (transactionId: string) =>
    [...transactionKeys.all, transactionId] as const,
};

export const signingKeys = {
  config: () => ["signing-config"] as const,
};