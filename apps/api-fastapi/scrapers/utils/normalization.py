"""
DRY helpers for listing normalization across portal drivers.

Centralizes price/currency math and safe parsing so RemaxRdDriver (and future
RealtorDriver) never duplicate conversion logic.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

# Macro rate when RE/MAX returns DOP; keep aligned with business operations.
DOP_TO_USD_RATE = 59.50

# Fallback UA when harvested headers omit User-Agent (curl_cffi + chrome120 impersonate).
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def safe_int(value: Any, default: int = 0) -> int:
    """
    Coerce API values to int without raising on bad portal payloads.

    Args:
        value: Raw JSON field (may be None or non-numeric).
        default: Returned when value is missing or invalid.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Coerce API values to float without raising on bad portal payloads.

    Args:
        value: Raw JSON field (may be None or non-numeric).
        default: Returned when value is missing or invalid.
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def combine_bathrooms(full_baths: Any, half_baths: Any) -> float:
    """
    Merge RE/MAX full + half bath counts into one float for PropertyListing.bathrooms.

    Half baths count as 0.5 per legacy RemaxRDScraper behavior.
    """
    return safe_float(full_baths) + (0.5 * safe_float(half_baths))


def title_case_label(value: Any, fallback: str) -> str:
    """
    Normalize city/sector labels for consistent display and filtering.

    Args:
        value: Raw string from API.
        fallback: Used when value is empty after strip.
    """
    text = str(value or fallback).strip()
    return text.title() if text else fallback


def resolve_prices_usd_dop(
    price_raw: Any,
    currency_iso: str,
    *,
    dop_to_usd_rate: float = DOP_TO_USD_RATE,
) -> Tuple[float, Optional[float]]:
    """
    Normalize list price to USD (required column) and optional DOP mirror.

    Args:
        price_raw: Portal list price field.
        currency_iso: ISO code from portal currency block (e.g. USD, DOP).
        dop_to_usd_rate: Conversion constant for DOP-listed properties.

    Returns:
        (price_usd, price_dop) — price_dop is None when list price is zero/missing.
    """
    amount = safe_float(price_raw, default=0.0)
    if amount <= 0:
        return 0.0, None

    iso = (currency_iso or "USD").upper()
    if iso == "DOP":
        # Store native DOP and derive USD for contracts/storefront USD display.
        price_dop = round(amount, 2)
        price_usd = round(amount / dop_to_usd_rate, 2)
        return price_usd, price_dop

    # USD (or treated as USD): store USD as primary, derive DOP for dual-currency UI.
    price_usd = round(amount, 2)
    price_dop = round(amount * dop_to_usd_rate, 2)
    return price_usd, price_dop