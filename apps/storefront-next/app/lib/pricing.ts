import { PropertyListing } from "./types";

/** Fallback USD→DOP rate when portal omits `price_dop` (matches ingestion heuristic). */
export const USD_TO_DOP_RATE = 59.5;

export function formatPrimaryPrice(property: PropertyListing): string {
  if (property.currency === "DOP") {
    return `RD$${property.price_raw.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  }
  return `$${property.price_raw.toLocaleString("en-US", { maximumFractionDigits: 0 })} USD`;
}

export function resolveDopAmount(property: PropertyListing): number {
  if (property.price_dop != null && property.price_dop > 0) {
    return property.price_dop;
  }
  const usdBase = property.currency === "USD" ? property.price_raw : property.price_usd;
  return usdBase * USD_TO_DOP_RATE;
}

export function resolveUsdAmount(property: PropertyListing): number {
  if (property.currency === "DOP") {
    return property.price_usd;
  }
  return property.price_raw;
}

/** Secondary line under primary: DOP listings → USD; USD listings → RD$. */
export function formatSecondaryPrice(property: PropertyListing): string {
  if (property.currency === "DOP") {
    return `≈ $${resolveUsdAmount(property).toLocaleString("en-US", {
      maximumFractionDigits: 0,
    })} USD`;
  }
  return `≈ RD$${resolveDopAmount(property).toLocaleString("en-US", {
    maximumFractionDigits: 0,
  })}`;
}

