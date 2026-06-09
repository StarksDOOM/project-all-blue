"""
Isolated match evaluation engine for STREAM 5 PHASE 3.0 Saved Searches.

Called from IngestionOrchestrator immediately after a new PropertyListing
is successfully recorded via bulk upsert. Performs pure-Python predicate
evaluation (consistent with Phase 2 compile_property_filters semantics)
against active SavedSearchAlert.filters_json rows and writes
SavedSearchMatch records.

The engine is intentionally implemented as a class (per Python OOP & Documentation
Standards) even though the ingestion call site uses a thin convenience function.
This allows future extension (caching of active alerts, different evaluation
strategies, metrics, etc.) via subclassing or composition.

No raw SQL with user data; JSONB deserialized into validated PropertyFilterParams.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from sqlmodel import Session, select

if TYPE_CHECKING:
    from fastapi import BackgroundTasks

from models import (
    NotificationDeliveryStatus,
    PropertyListing,
    SavedSearchAlert,
    SavedSearchMatch,
)
from schemas.property_filters import PropertyFilterParams

# Local imports for Phase 4 / 4.1 notification (avoid circular at module level)
from services.email_client import ResendEmailProvider, StubEmailProvider
from services.notification_compiler import NotificationCompiler
from services.notification_dispatcher import NotificationDispatcher


class SearchMatchEngine:
    """
    Object-oriented property-to-saved-search matcher.

    Responsibilities:
    - Hold the DB session for the duration of a batch evaluation.
    - Load active alerts once per evaluation cycle.
    - Apply the Phase-2-compatible Python predicate to decide matches.
    - Persist `SavedSearchMatch` rows + update `last_matched_at` on alerts.

    Thread-safety note: Instances are **not** thread-safe. Each background
    ingestion job should create its own engine (or pass the job's session).
    The evaluate method performs its own commit for the match rows so that
    a failure inside the matcher does not roll back the main ingestion upsert.

    Usage from orchestration code (after chunk commit):

        engine = SearchMatchEngine(db_session)
        matches = engine.evaluate(newly_inserted_listing)
    """

    def __init__(self, session: Session) -> None:
        """Initialize with an active SQLModel session (usually the orchestrator's)."""
        self._session = session

    def _property_matches_filters(
        self, listing: PropertyListing, filters: PropertyFilterParams
    ) -> bool:
        """
        Python-native AND predicate equivalent to the SQLAlchemy criteria in
        services/property_list_service.py:compile_property_filters.

        Private because callers should use the public `evaluate` entry point.
        Must be kept in sync with any additions to PropertyFilterParams.
        """
        # source_portal (case-insensitive as in compiler)
        if filters.source_portal:
            if (listing.source_portal or "").lower() != filters.source_portal.strip().lower():
                return False

        if filters.sector and listing.sector != filters.sector:
            return False

        if filters.keyword:
            haystack = f"{listing.title or ''} {listing.raw_description or ''}".lower()
            if filters.keyword.lower() not in haystack:
                return False

        # Effective price uses normalized price_usd in USD
        effective_price = listing.price_usd
        if filters.price_min is not None and effective_price < filters.price_min:
            return False
        if filters.price_max is not None and effective_price > filters.price_max:
            return False

        if filters.bedrooms_min is not None and listing.bedrooms < filters.bedrooms_min:
            return False

        if filters.bathrooms_min is not None and listing.bathrooms < filters.bathrooms_min:
            return False

        # property_type special patterns (venta / alquiler) — mirror the ilike logic
        if filters.property_type in ("venta", "alquiler"):
            desc = f"{listing.raw_description or ''} {listing.title or ''}".lower()
            if filters.property_type == "venta":
                if not ("business_type=venta" in desc or "venta" in desc):
                    return False
            else:  # alquiler
                if not (
                    "business_type=alquiler" in desc
                    or "alquiler" in desc
                    or "renta" in desc
                ):
                    return False

        if filters.agency and listing.agent_agency:
            if filters.agency.lower() not in (listing.agent_agency or "").lower():
                return False

        return True

    def evaluate(
        self,
        property_obj: PropertyListing,
        background_tasks: "BackgroundTasks | None" = None,
        session_factory: callable | None = None,
    ) -> int:
        """
        For a freshly persisted (inserted) PropertyListing, scan all active
        SavedSearchAlert rows, deserialize their filters_json, test the predicate,
        and INSERT SavedSearchMatch rows for every hit.

        Side-effect: commits matches + bumps last_matched_at on matched alerts.
        If background_tasks is provided (FastAPI web path), also schedules
        outbound notification delivery via NotificationDispatcher (Phase 4.0).
        The dispatch task receives its own fresh session via session_factory.

        Returns number of match records written (0 if none or property invalid).

        Must be called **after** the upsert chunk commit for the property so that
        the FK to properties.id is valid and we are outside the main ingestion tx.

        Args:
            background_tasks: Optional FastAPI BackgroundTasks for non-blocking email.
            session_factory: Callable returning fresh Session for the background task.
        """
        if property_obj is None or not getattr(property_obj, "id", None):
            return 0

        # Only active, non-deleted alerts (tenant isolation is future)
        stmt = select(SavedSearchAlert).where(
            SavedSearchAlert.is_active == True,
            SavedSearchAlert.deleted_at.is_(None),  # type: ignore[attr-defined]
        )
        alerts: list[SavedSearchAlert] = self._session.exec(stmt).all()

        matches_written = 0
        now = datetime.now(timezone.utc)

        for alert in alerts:
            try:
                # Re-validate / normalize using the same Pydantic model as API surface
                f = PropertyFilterParams.model_validate(alert.filters_json)
            except Exception:
                # Corrupt or legacy JSON — skip this alert (do not crash ingestion)
                continue

            if self._property_matches_filters(property_obj, f):
                # Record which criteria were active for this match (for UI / future notifier)
                matched_on: list[str] = []
                for field in (
                    "sector",
                    "keyword",
                    "price_min",
                    "price_max",
                    "bedrooms_min",
                    "bathrooms_min",
                    "property_type",
                    "agency",
                    "source_portal",
                ):
                    val = getattr(f, field, None)
                    if val not in (None, "", 0):
                        matched_on.append(field)

                details: dict[str, Any] = {
                    "matched_on": matched_on,
                    "snapshot": {
                        "price_usd": property_obj.price_usd,
                        "list_price": property_obj.list_price,
                        "sector": property_obj.sector,
                        "bedrooms": property_obj.bedrooms,
                        "bathrooms": property_obj.bathrooms,
                    },
                }

                match_row = SavedSearchMatch(
                    saved_search_alert_id=alert.id,
                    user_id=alert.user_id,  # Phase 5.0: tenant isolation
                    property_id=property_obj.id,
                    match_details=details,
                )
                self._session.add(match_row)

                # Light touch on alert for "last activity"
                alert.last_matched_at = now
                self._session.add(alert)

                # Phase 4.0: Schedule outbound notification (non-blocking) when
                # background context is available. Avoids session-passing creep by
                # delegating scheduling to FastAPI BackgroundTasks + fresh session
                # inside the task.
                if background_tasks is not None and session_factory is not None:
                    try:
                        compiler = NotificationCompiler(frontend_base_url="http://localhost:3000")
                        rendered = compiler.compile(
                            match_details=details,
                            alert_title=alert.title,
                            property_id=property_obj.id,
                            property_title=property_obj.title,
                            image_urls=property_obj.image_urls,
                            sector=property_obj.sector,
                            price_usd=property_obj.price_usd,
                            list_price=property_obj.list_price,
                        )

                        recipient = "alerts@allblue.example"  # demo; resolve from user profile in prod

                        # DI for Phase 4.1: prefer Resend if configured, else safe stub.
                        # Dispatcher now handles default internally, but explicit here
                        # for clarity and to demonstrate production path selection.
                        if os.getenv("RESEND_API_KEY"):
                            provider = ResendEmailProvider()
                        else:
                            provider = StubEmailProvider()

                        dispatcher = NotificationDispatcher(email_client=provider)

                        dispatcher.schedule(
                            background_tasks=background_tasks,
                            rendered_html=rendered,
                            recipient=recipient,
                            match_id=match_row.id,
                            alert_title=alert.title,
                            session_factory=session_factory,
                        )
                    except Exception:
                        logger.exception("Failed to schedule Phase 4 notification for match %s", match_row.id)

                matches_written += 1

        if matches_written > 0:
            self._session.commit()

        return matches_written


def evaluate_property_against_alerts(
    property_obj: PropertyListing,
    session: Session,
    background_tasks: "BackgroundTasks | None" = None,
    session_factory: callable | None = None,
) -> int:
    """
    Convenience wrapper that preserves the original function-based call site
    used by IngestionOrchestrator while delegating to the canonical
    SearchMatchEngine class (OOP requirement).

    Phase 4.0: forwards background_tasks and session_factory so that match
    creation can immediately schedule the notification email without blocking
    the caller.

    All new call sites and tests should prefer the class form when they need
    more control (e.g. multiple evaluations against the same session).
    """
    return SearchMatchEngine(session).evaluate(
        property_obj,
        background_tasks=background_tasks,
        session_factory=session_factory,
    )
