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

export const contractKeys = {
  all: ["contracts"] as const,
  list: () => [...contractKeys.all, "list"] as const,
};

export const leadKeys = {
  all: ["leads"] as const,
  list: (skip?: number, limit?: number) => [...leadKeys.all, "list", skip, limit] as const,
};

export const analyticsKeys = {
  wholesale: (propertyId: string) =>
    ["analytics", "wholesale", propertyId] as const,
  wholesaleStr: (
    propertyId: string,
    nightly_rate: number,
    occupancy_pct: number,
    monthly_maintenance: number
  ) =>
    [
      "analytics",
      "wholesale",
      propertyId,
      "str",
      nightly_rate,
      occupancy_pct,
      monthly_maintenance,
    ] as const,
  wholesaleComm: (
    propertyId: string,
    monthly_rent_per_sqm: number,
    comm_vacancy_rate: number,
    annual_taxes_insurance: number
  ) =>
    [
      "analytics",
      "wholesale",
      propertyId,
      "commercial",
      monthly_rent_per_sqm,
      comm_vacancy_rate,
      annual_taxes_insurance,
    ] as const,
  wholesaleLtr: (
    propertyId: string,
    monthly_rent: number,
    ltr_vacancy_rate: number,
    ltr_pm_fee_pct: number,
    monthly_maintenance: number
  ) =>
    [
      "analytics",
      "wholesale",
      propertyId,
      "ltr",
      monthly_rent,
      ltr_vacancy_rate,
      ltr_pm_fee_pct,
      monthly_maintenance,
    ] as const,
};
