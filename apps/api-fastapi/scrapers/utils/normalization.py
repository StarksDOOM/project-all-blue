"""
DRY helpers for listing normalization across portal drivers.

Centralizes price/currency math and safe parsing so RemaxRdDriver (and future
RealtorDriver) never duplicate conversion logic.
"""

from __future__ import annotations

import re
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


def _normalize_description_text(text: str) -> str:
    """Strip HTML and collapse whitespace for regex bath extraction."""
    plain = str(text).replace("\u00a0", " ").replace("&nbsp;", " ")
    plain = re.sub(r"<[^>]+>", " ", plain)
    return re.sub(r"\s+", " ", plain).strip().lower()


def parse_bathrooms_from_text(text: str) -> float:
    """
    Extract bath count from RE/MAX prose when structured API fields are empty.

    Handles Spanish portal copy (e.g. ``3 baños completos``, ``1 baño completo y 1 medio baño``)
    and simple English ``N bath(s)`` / ``half bath`` phrases.
    """
    if not text or not str(text).strip():
        return 0.0

    normalized = _normalize_description_text(str(text))
    if not normalized:
        return 0.0

    total = 0.0

    for match in re.finditer(
        r"(?:(\d+)\s*)?medio\s*ba[ñn]o",
        normalized,
    ):
        half_count = safe_int(match.group(1), default=1) if match.group(1) else 1
        total += 0.5 * half_count

    full_from_complete = [
        safe_float(match.group(1).replace(",", "."))
        for match in re.finditer(
            r"(\d+(?:[.,]\d+)?)\s*ba[ñn]os?\s+complet",
            normalized,
        )
    ]
    if full_from_complete:
        total += max(full_from_complete)

    generic_full = [
        safe_float(match.group(1).replace(",", "."))
        for match in re.finditer(
            r"(\d+(?:[.,]\d+)?)\s*ba[ñn]os?(?!\s+complet)(?!\s*medio)",
            normalized,
        )
    ]
    if generic_full and total == 0.0:
        total += max(generic_full)

    labeled = re.search(
        r"ba[ñn]os?\s*[:=]\s*(\d+(?:[.,]\d+)?)",
        normalized,
    )
    if labeled and total == 0.0:
        total += safe_float(labeled.group(1).replace(",", "."))

    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*half\s*baths?", normalized):
        total += 0.5 * safe_float(match.group(1))

    if total == 0.0:
        english_full = [
            safe_float(match.group(1))
            for match in re.finditer(
                r"(\d+(?:\.\d+)?)\s*baths?(?!\s*room)",
                normalized,
            )
        ]
        if english_full:
            total += max(english_full)

    return round(total, 2)


def resolve_bathroom_count(
    full_baths: Any,
    half_baths: Any,
    description: str | None = None,
) -> float:
    """
    Prefer structured RE/MAX fields; fall back to description prose for KPI display.
    """
    structured = combine_bathrooms(full_baths, half_baths)
    if structured > 0:
        return structured
    if description:
        return parse_bathrooms_from_text(description)
    return 0.0


def resolve_bathroom_count_from_specs(
    specs: dict[str, Any] | None,
    *,
    description_text: str | None = None,
    raw_description: str | None = None,
) -> float:
    """
    Resolve bath KPI from scraper specs + any available description copy.

    Order: ``bathroom_count`` (pre-merged) → raw ``bathrooms``/``half_bathrooms`` → prose.
    """
    specs = specs or {}

    merged = safe_float(specs.get("bathroom_count"), default=0.0)
    if merged > 0:
        return merged

    from_payload = combine_bathrooms(specs.get("bathrooms"), specs.get("half_bathrooms"))
    if from_payload > 0:
        return from_payload

    for text in (description_text, raw_description):
        if not text:
            continue
        parsed = parse_bathrooms_from_text(text)
        if parsed > 0:
            return parsed

    return 0.0


def hydrate_listing_bathrooms(listing: Any) -> Any:
    """Fill ``listing.bathrooms`` from ``raw_description`` when the DB column is still zero."""
    if safe_float(getattr(listing, "bathrooms", 0), default=0.0) > 0:
        return listing
    parsed = parse_bathrooms_from_text(str(getattr(listing, "raw_description", "") or ""))
    if parsed > 0:
        listing.bathrooms = parsed
    return listing


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