"""
RE/MAX scraper error telemetry.

Console logging uses the standard library ``logging`` module. Database persistence
is isolated in ``persist_scraper_error_record`` so production can swap in Sentry,
Logfire, or Datadog by replacing that single function (or registering a custom sink).
"""

from __future__ import annotations

import logging
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator, Literal, Optional

from sqlmodel import Session

from database import engine
from models import ScraperErrorLog

logger = logging.getLogger(__name__)

ScraperMethod = Literal["json", "dom", "api", "enrichment", "unknown"]

# Optional override hook for external APM (Sentry, Logfire, Datadog, etc.).
_error_sink: Callable[..., None] | None = None


def register_scraper_error_sink(sink: Callable[..., None]) -> None:
    """Replace the default DB persistence sink (e.g. Sentry-only in production)."""
    global _error_sink
    _error_sink = sink


def map_detail_source_to_method(source: str | None) -> ScraperMethod:
    """Map scraper detail ``source`` field to telemetry ``scraper_method``."""
    normalized = (source or "").strip().lower()
    if normalized in {"next_data", "remax_api"}:
        return "json"
    if normalized == "dom_fallback":
        return "dom"
    if normalized == "enrichment":
        return "enrichment"
    if normalized == "api":
        return "api"
    return "unknown"


def persist_scraper_error_record(
    *,
    scraper_method: ScraperMethod,
    error_type: str,
    stack_trace: str,
    remote_id: str | None = None,
    url: str | None = None,
    session: Session | None = None,
) -> None:
    """
    Default persistence sink — insert one ``ScraperErrorLog`` row.

    Swapping this function (or ``register_scraper_error_sink``) is the only change
    required to move off Postgres telemetry later.
    """
    if _error_sink is not None:
        _error_sink(
            scraper_method=scraper_method,
            error_type=error_type,
            stack_trace=stack_trace,
            remote_id=remote_id,
            url=url,
        )
        return

    row = ScraperErrorLog(
        remote_id=remote_id,
        url=url,
        scraper_method=scraper_method,
        error_type=error_type[:255],
        stack_trace=stack_trace[:50000],
        resolved=False,
        created_at=datetime.now(timezone.utc),
    )

    try:
        if session is not None:
            session.add(row)
            session.commit()
            return
        with Session(engine) as dedicated:
            dedicated.add(row)
            dedicated.commit()
    except Exception:
        logger.exception(
            "Failed to persist ScraperErrorLog remote_id=%s method=%s",
            remote_id,
            scraper_method,
        )


def report_scraper_error(
    exc: BaseException,
    *,
    scraper_method: ScraperMethod,
    remote_id: str | None = None,
    url: str | None = None,
    session: Session | None = None,
) -> None:
    """Structured console log + persistence for one scraper failure."""
    stack = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    logger.error(
        "scraper_error method=%s remote_id=%s url=%s type=%s message=%s",
        scraper_method,
        remote_id,
        url,
        type(exc).__name__,
        exc,
        exc_info=exc,
    )
    persist_scraper_error_record(
        scraper_method=scraper_method,
        error_type=type(exc).__name__,
        stack_trace=stack,
        remote_id=remote_id,
        url=url,
        session=session,
    )


@contextmanager
def scraper_error_scope(
    scraper_method: ScraperMethod,
    *,
    remote_id: str | None = None,
    url: str | None = None,
    session: Session | None = None,
    swallow: bool = False,
    reraise: bool = True,
) -> Iterator[None]:
    """
    Wrap a parsing or enrichment block.

    Args:
        swallow: When True, log + persist then suppress the exception (continue fetch).
        reraise: When False, same as swallow for backward compatibility.
    """
    try:
        yield
    except Exception as exc:
        report_scraper_error(
            exc,
            scraper_method=scraper_method,
            remote_id=remote_id,
            url=url,
            session=session,
        )
        if swallow or not reraise:
            return
        raise