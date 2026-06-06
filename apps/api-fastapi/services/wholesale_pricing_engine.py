"""
Wholesale Pricing Engine — stateless domain service for deal metric computation.

Module Purpose:
    Provides ``WholesalePricingEngine``, a single-responsibility class that derives
    wholesale real estate metrics (ARV, MAO, assignment fee, pitch price) for any
    active ``PropertyListing`` using live sector data from the database and a fixed
    set of heuristic multipliers defined in the spec
    (``.spec-kit/specs/api/wholesale-analytics-engine.spec.md``).

    This module is read-only with respect to the database: no writes, no side effects.

Thread Safety:
    ``WholesalePricingEngine`` is fully stateless (no instance attributes mutated
    after construction).  A single shared instance is safe for concurrent use across
    multiple FastAPI request handlers as long as each handler supplies its own
    SQLModel ``Session``.

Collaborators:
    - ``models.PropertyListing`` — source of sector, price_usd, and square_meters.
    - ``schemas.contracts.WholesaleDealMetrics`` — output data contract.
    - ``routers.analytics`` — sole caller of ``calculate_deal_metrics``.

Constants (spec-locked — changes require spec update + user approval):
    REPAIR_COST_PER_SQM : float = 150.0
        Flat USD repair estimate per square metre of the target property.
    ARV_ACQUISITION_RATIO : float = 0.70
        Maximum fraction of ARV an investor should pay (MAO numerator factor).
    ASSIGNMENT_FEE_RATIO : float = 0.05
        Percentage of ARV retained as the wholesale assignment fee.
    ASSIGNMENT_FEE_FLOOR : float = 5_000.0
        Minimum assignment fee in USD regardless of ARV percentage result.
"""

import statistics

from fastapi import HTTPException
from sqlmodel import Session, select

from models import PropertyListing
from schemas.contracts import WholesaleDealMetrics

# ---------------------------------------------------------------------------
# Spec-locked formula constants
# ---------------------------------------------------------------------------
_REPAIR_COST_PER_SQM: float = 150.0
_ARV_ACQUISITION_RATIO: float = 0.70
_ASSIGNMENT_FEE_RATIO: float = 0.05
_ASSIGNMENT_FEE_FLOOR: float = 5_000.0


class WholesalePricingEngine:
    """
    Stateless domain service that computes wholesale deal metrics for a property.

    Purpose:
        Encapsulates the complete wholesale analysis algorithm defined in
        STREAM 6 PHASE 1.3.  Given a ``property_id`` and an open database
        ``Session``, it queries the ``PropertyListing`` table to derive a
        sector-level median price-per-square-metre, then applies fixed heuristic
        multipliers to produce an ARV, MAO, assignment fee, and pitch price.

    Lifecycle:
        Stateless — instantiate once and reuse across requests, or instantiate
        per-request; both patterns are safe.  No background threads or timers are
        started.

    Thread Safety:
        Safe for concurrent invocation.  Each call to ``calculate_deal_metrics``
        operates entirely on the caller-supplied ``session``; no shared mutable
        state exists on the instance.

    Collaborators:
        - ``models.PropertyListing`` — ORM model queried for sector comps.
        - ``schemas.contracts.WholesaleDealMetrics`` — typed output contract.

    Invariants:
        - Only ``is_active=True`` listings contribute to the sector median.
        - ``price_usd`` (always populated) is the sole price source; ``list_price``
          is ignored (per spec decision — see open question resolution).
        - ``assignment_fee`` is never less than ``_ASSIGNMENT_FEE_FLOOR``.
        - ``pitch_price == mao + assignment_fee`` (algebraic identity).
    """

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def calculate_deal_metrics(
        self,
        property_id: str,
        session: Session,
    ) -> WholesaleDealMetrics:
        """
        Compute wholesale deal metrics for the given property.

        Purpose:
            Executes the complete STREAM 6 PHASE 1.3 algorithm:
            1. Validate the target property exists and is active.
            2. Retrieve all active listings in the same sector.
            3. Compute the sector median price-per-square-metre.
            4. Derive ARV, repairs, MAO, assignment fee, and pitch price.

        Parameters:
            property_id : str
                The BLU database ID of the target ``PropertyListing``.
            session : Session
                An open SQLModel ``Session`` bound to the request lifecycle.
                The engine performs read-only queries; the session is not
                committed or closed by this method.

        Returns:
            WholesaleDealMetrics
                A fully populated response schema ready for JSON serialisation.

        Raises:
            HTTPException(404)
                If no active ``PropertyListing`` with ``property_id`` exists.
            HTTPException(422)
                If the target property's sector contains zero active listings
                (insufficient data to compute a reliable sector median).

        Side Effects:
            None.  All database interactions are read-only SELECT statements.
        """
        target = self._load_target_property(property_id, session)
        sector_listings = self._query_sector_listings(target.sector, session)
        median_price_per_sqm = self._compute_median_price_per_sqm(
            sector_listings, target.sector
        )
        return self._build_metrics(target, median_price_per_sqm)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_target_property(
        self, property_id: str, session: Session
    ) -> PropertyListing:
        """
        Load and validate the target ``PropertyListing`` from the database.

        Purpose:
            Fetches the listing row identified by ``property_id`` and asserts
            that it is currently active.  Inactive listings are treated as
            absent to prevent analytics on stale inventory.

        Parameters:
            property_id : str
                BLU identifier of the listing to load.
            session : Session
                Active SQLModel session.

        Returns:
            PropertyListing
                The validated, active listing ORM object.

        Raises:
            HTTPException(404)
                If the listing does not exist or ``is_active`` is ``False``.
        """
        statement = select(PropertyListing).where(
            PropertyListing.id == property_id,
            PropertyListing.is_active.is_(True),  # type: ignore[attr-defined]
        )
        listing = session.exec(statement).first()
        if listing is None:
            raise HTTPException(
                status_code=404,
                detail=f"Property '{property_id}' not found or is not active.",
            )
        return listing

    def _query_sector_listings(
        self, sector: str, session: Session
    ) -> list[PropertyListing]:
        """
        Retrieve all active listings in the given sector.

        Purpose:
            Collects the peer set used to compute the sector median
            price-per-square-metre.  The target property itself is included
            in this set (it is an active listing in its own sector), which
            is the correct behaviour per the spec — the target is part of
            the market it is being priced against.

        Parameters:
            sector : str
                The neighbourhood / sector identifier to query.
            session : Session
                Active SQLModel session.

        Returns:
            list[PropertyListing]
                All active ``PropertyListing`` rows for the sector.  May
                contain only the target property itself (single-peer case).

        Raises:
            HTTPException(422)
                If zero active listings are found for the sector (should not
                occur after ``_load_target_property`` succeeds, but guards
                against edge cases such as concurrent deactivation).
        """
        statement = select(PropertyListing).where(
            PropertyListing.sector == sector,
            PropertyListing.is_active.is_(True),  # type: ignore[attr-defined]
        )
        listings = list(session.exec(statement).all())
        if not listings:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Sector '{sector}' has no active listings. "
                    "Insufficient data to compute a sector median."
                ),
            )
        return listings

    def _compute_median_price_per_sqm(
        self, listings: list[PropertyListing], sector: str
    ) -> float:
        """
        Compute the median USD price per square metre across a list of listings.

        Purpose:
            Derives the sector-level market benchmark used as the foundation for
            ARV estimation.  The median is preferred over the mean to reduce
            sensitivity to outlier luxury or distressed listings.

        Algorithm:
            For each listing: ratio = price_usd / square_meters.
            Return statistics.median(ratios).

        Parameters:
            listings : list[PropertyListing]
                Non-empty list of active sector listings.  Caller guarantees
                non-empty (enforced by ``_query_sector_listings``).
            sector : str
                Human-readable sector name — used only in error messages.

        Returns:
            float
                The median price-per-square-metre in USD/m².

        Raises:
            HTTPException(422)
                If any listing has ``square_meters <= 0``, protecting against
                division-by-zero from bad ingestion data.
        """
        ratios: list[float] = []
        for listing in listings:
            if listing.square_meters <= 0:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Listing '{listing.id}' in sector '{sector}' has "
                        f"invalid square_meters={listing.square_meters}. "
                        "Cannot compute sector median."
                    ),
                )
            ratios.append(listing.price_usd / listing.square_meters)
        return statistics.median(ratios)

    def _build_metrics(
        self,
        target: PropertyListing,
        median_price_per_sqm: float,
    ) -> WholesaleDealMetrics:
        """
        Apply spec-locked heuristics to produce the final deal metrics payload.

        Purpose:
            Translates the sector median and target property attributes into
            the full ``WholesaleDealMetrics`` output according to the formulas
            defined in ``.spec-kit/specs/api/wholesale-analytics-engine.spec.md``.

        Parameters:
            target : PropertyListing
                The validated target property with populated ``square_meters``
                and ``sector`` fields.
            median_price_per_sqm : float
                Sector median price in USD per square metre (output of
                ``_compute_median_price_per_sqm``).

        Returns:
            WholesaleDealMetrics
                Fully populated response schema instance.

        Side Effects:
            None.
        """
        auto_arv = median_price_per_sqm * target.square_meters
        estimated_repairs = target.square_meters * _REPAIR_COST_PER_SQM
        mao = (auto_arv * _ARV_ACQUISITION_RATIO) - estimated_repairs
        assignment_fee = max(auto_arv * _ASSIGNMENT_FEE_RATIO, _ASSIGNMENT_FEE_FLOOR)
        pitch_price = mao + assignment_fee

        return WholesaleDealMetrics(
            property_id=str(target.id),
            sector=target.sector,
            sector_median_price_per_sqm=round(median_price_per_sqm, 2),
            auto_arv=round(auto_arv, 2),
            estimated_repairs=round(estimated_repairs, 2),
            mao=round(mao, 2),
            assignment_fee=round(assignment_fee, 2),
            pitch_price=round(pitch_price, 2),
        )
