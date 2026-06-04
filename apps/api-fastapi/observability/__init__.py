"""Telemetry and error-reporting helpers (swappable persistence sinks)."""

from observability.scraper_errors import (
    ScraperMethod,
    map_detail_source_to_method,
    persist_scraper_error_record,
    report_scraper_error,
    scraper_error_scope,
)

__all__ = [
    "ScraperMethod",
    "map_detail_source_to_method",
    "persist_scraper_error_record",
    "report_scraper_error",
    "scraper_error_scope",
]