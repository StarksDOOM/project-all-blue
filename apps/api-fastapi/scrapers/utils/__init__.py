"""
Shared scraper utilities (DRY).

Portal drivers should import normalization helpers from this package rather than
copying price/bath/parse logic per file.
"""

from scrapers.utils.normalization import (
    CHROME_USER_AGENT,
    DOP_TO_USD_RATE,
    combine_bathrooms,
    parse_bathrooms_from_text,
    resolve_bathroom_count,
    resolve_prices_usd_dop,
    safe_float,
    safe_int,
    title_case_label,
)

__all__ = [
    "CHROME_USER_AGENT",
    "DOP_TO_USD_RATE",
    "combine_bathrooms",
    "parse_bathrooms_from_text",
    "resolve_bathroom_count",
    "resolve_prices_usd_dop",
    "safe_float",
    "safe_int",
    "title_case_label",
]