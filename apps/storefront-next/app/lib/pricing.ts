import { PropertyListing } from "./types";

/** Fallback USD→DOP rate when portal omits `price_dop` (matches ingestion heuristic). */
export const USD_TO_DOP_RATE = 59.5;

function rentalSuffix(property: PropertyListing): string {
  return property.business_type === "alquiler" ? " / mes" : "";
}

function resolveDisplayAmount(property: PropertyListing): number | null {
  if (property.list_price != null && property.list_price > 0) {
    return property.list_price;
  }
  if (property.price_raw > 0) {
    return property.price_raw;
  }
  return null;
}

export function formatPrimaryPrice(property: PropertyListing): string {
  const amount = resolveDisplayAmount(property);
  if (amount == null || amount <= 0) {
    return "Precio no disponible";
  }
  if (property.currency === "DOP") {
    return `RD$${amount.toLocaleString("en-US", { maximumFractionDigits: 0 })}${rentalSuffix(property)}`;
  }
  return `$${amount.toLocaleString("en-US", { maximumFractionDigits: 0 })} USD${rentalSuffix(property)}`;
}

export function hasPortalListPrice(property: PropertyListing): boolean {
  const amount = resolveDisplayAmount(property);
  return amount != null && amount > 0;
}

/** Secondary line only when portal provided an explicit mirror on the API row. */
export function formatSecondaryPrice(property: PropertyListing): string | null {
  if (!hasPortalListPrice(property)) {
    return null;
  }
  const suffix = rentalSuffix(property);
  if (property.currency === "DOP") {
    if (property.price_usd == null || property.price_usd <= 0) {
      return null;
    }
    return `≈ $${property.price_usd.toLocaleString("en-US", {
      maximumFractionDigits: 0,
    })} USD${suffix}`;
  }
  if (property.price_dop == null || property.price_dop <= 0) {
    return null;
  }
  return `≈ RD$${property.price_dop.toLocaleString("en-US", {
    maximumFractionDigits: 0,
  })}${suffix}`;
}

