"""
Wholesale Pricing Engine — stateless domain service for deal metric computation.

Module Purpose:
    Provides ``WholesalePricingEngine``, a single-responsibility class that derives
    wholesale real estate metrics (ARV, MAO, assignment fee, pitch price) and optional
    Short-Term Rental (STR) yield projections for any active ``PropertyListing`` using
    live sector data from the database and a fixed set of heuristic multipliers defined
    in the spec (``.spec-kit/specs/api/wholesale-analytics-engine.spec.md`` and
    ``.spec-kit/specs/api/airbnb-roi-engine.spec.md``).

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
    PM_FEE_RATIO : float = 0.20
        Property management fee as a fraction of monthly STR gross income.
    MAINTENANCE_RESERVE : float = 150.0
        Flat monthly maintenance reserve in USD for STR projections.
"""

import statistics

from fastapi import HTTPException
from sqlmodel import Session, select

from models import PropertyListing
from schemas.contracts import WholesaleDealMetrics, CommercialYieldMetrics, LtrYieldMetrics
from services.str_default_predictor import StrDefaultPredictor

# ---------------------------------------------------------------------------
# Spec-locked formula constants
# ---------------------------------------------------------------------------
_DISCOUNT_RATIO: float = 0.80
_ASSIGNMENT_FEE_RATIO: float = 0.05
_ASSIGNMENT_FEE_FLOOR: float = 5_000.0
_PM_FEE_RATIO: float = 0.20
_MAINTENANCE_RESERVE: float = 150.0


class WholesalePricingEngine:
    """
    Stateless domain service that computes wholesale deal metrics for a property.

    Purpose:
        Encapsulates the wholesale analysis algorithm (STREAM 6 PHASE 1.3) and
        the optional STR yield calculator (STREAM 6 PHASE 1.6).  Given a
        ``property_id`` and an open database ``Session``, it queries the
        ``PropertyListing`` table to derive a
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
        *,
        nightly_rate: float | None = None,
        occupancy_pct: float | None = None,
        monthly_maintenance: float | None = None,
        monthly_rent_per_sqm: float | None = None,
        comm_vacancy_rate: float | None = None,
        annual_taxes_insurance: float | None = None,
        monthly_rent: float | None = None,
        ltr_vacancy_rate: float | None = None,
        ltr_pm_fee_pct: float | None = None,
    ) -> WholesaleDealMetrics:
        """
        Compute wholesale deal metrics for the given property.

        Purpose:
            Executes the complete STREAM 6 PHASE 1.3 algorithm:
            1. Validate the target property exists and is active.
            2. Retrieve all active listings in the same sector.
            3. Compute the sector median price-per-square-metre.
            4. Derive ARV, repairs, MAO, assignment fee, and pitch price.

            When ``nightly_rate`` is supplied, also computes STR yield metrics
            (STREAM 6 PHASE 1.6): monthly gross/net, annual NOI, Cash-on-Cash
            return percentage, and 6-month/1-year/3-year net profit projections.

            When LTR or Commercial parameters are supplied, also computes corresponding
            Cap Rate yield metrics (STREAM 6 PHASE 1.8).

        Parameters:
            property_id : str
                The BLU database ID of the target ``PropertyListing``.
            session : Session
                An open SQLModel ``Session`` bound to the request lifecycle.
                The engine performs read-only queries; the session is not
                committed or closed by this method.
            nightly_rate : float | None
                Average nightly STR rate in USD.  When ``None``, STR metrics
                are omitted from the response.
            occupancy_pct : float | None
                Occupancy ratio (0.0–1.0).  Defaults to ``0.70`` if ``nightly_rate``
                is provided but ``occupancy_pct`` is ``None``.
            monthly_maintenance : float | None
                Monthly complex maintenance dues in USD.  Defaults to ``0.0``.
            monthly_rent_per_sqm : float | None
                Monthly commercial rent per square meter.
            comm_vacancy_rate : float | None
                Expected vacancy rate for commercial.
            annual_taxes_insurance : float | None
                Expected annual taxes and insurance for commercial.
            monthly_rent : float | None
                Monthly LTR residential rent.
            ltr_vacancy_rate : float | None
                Expected vacancy rate for LTR.
            ltr_pm_fee_pct : float | None
                Property management fee percentage for LTR.

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

        auto_emv = median_price_per_sqm * target.square_meters
        mao = auto_emv * _DISCOUNT_RATIO
        assignment_fee = max(auto_emv * _ASSIGNMENT_FEE_RATIO, _ASSIGNMENT_FEE_FLOOR)
        pitch_price = mao + assignment_fee

        # Compute optional STR yield metrics when nightly_rate is provided
        str_kwargs: dict[str, float | None] = {}
        if nightly_rate is not None:
            str_kwargs = self.calculate_str_metrics(
                nightly_rate=nightly_rate,
                occupancy_pct=occupancy_pct if occupancy_pct is not None else 0.70,
                monthly_maintenance=monthly_maintenance if monthly_maintenance is not None else 0.0,
                pitch_price=pitch_price,
            )

        # Compute Commercial Cap Rate if requested or if commercial listing
        commercial_metrics = None
        comm_v_rate = comm_vacancy_rate if comm_vacancy_rate is not None else 0.10
        comm_tax_ins = annual_taxes_insurance if annual_taxes_insurance is not None else (pitch_price * 0.01)

        if monthly_rent_per_sqm is not None:
            commercial_metrics = self.calculate_commercial_metrics(
                pitch_price=pitch_price,
                size_sqm=target.square_meters,
                monthly_rent_per_sqm=monthly_rent_per_sqm,
                vacancy_rate=comm_v_rate,
                annual_taxes_insurance=comm_tax_ins,
            )
        elif getattr(target, "property_type", "RESIDENTIAL") == "COMMERCIAL":
            commercial_metrics = self.calculate_commercial_metrics(
                pitch_price=pitch_price,
                size_sqm=target.square_meters,
                monthly_rent_per_sqm=15.0,
                vacancy_rate=comm_v_rate,
                annual_taxes_insurance=comm_tax_ins,
            )

        # Compute LTR Cap Rate if requested or if residential listing
        ltr_metrics = None
        ltr_v_rate = ltr_vacancy_rate if ltr_vacancy_rate is not None else 0.05
        ltr_pm = ltr_pm_fee_pct if ltr_pm_fee_pct is not None else 0.10
        ltr_maint = monthly_maintenance if monthly_maintenance is not None else 0.0

        if monthly_rent is not None:
            ltr_metrics = self.calculate_ltr_metrics(
                pitch_price=pitch_price,
                monthly_rent=monthly_rent,
                vacancy_rate=ltr_v_rate,
                pm_fee_pct=ltr_pm,
                monthly_maintenance=ltr_maint,
            )
        elif getattr(target, "property_type", "RESIDENTIAL") == "RESIDENTIAL":
            # Smart default rent: 8% yield of target purchase price
            default_rent = round((target.price_usd * 0.08) / 12, 2)
            if default_rent <= 0:
                default_rent = 1200.0
            ltr_metrics = self.calculate_ltr_metrics(
                pitch_price=pitch_price,
                monthly_rent=default_rent,
                vacancy_rate=ltr_v_rate,
                pm_fee_pct=ltr_pm,
                monthly_maintenance=ltr_maint,
            )

        return self._build_metrics(
            target,
            median_price_per_sqm,
            str_kwargs=str_kwargs,
            commercial_metrics=commercial_metrics,
            ltr_metrics=ltr_metrics,
        )

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

    def calculate_str_metrics(
        self,
        nightly_rate: float,
        occupancy_pct: float,
        monthly_maintenance: float,
        pitch_price: float,
    ) -> dict[str, float | None]:
        """
        Compute Short-Term Rental (STR) yield metrics from user-supplied assumptions.

        Purpose:
            Pure computational method (no database access) that derives monthly
            income, NOI, Cash-on-Cash return, and time-horizon profit projections
            from STR operating assumptions.  Defined in STREAM 6 PHASE 1.6 spec.

        Parameters:
            nightly_rate : float
                Average nightly rental rate in USD.
            occupancy_pct : float
                Expected occupancy ratio (0.0–1.0).
            monthly_maintenance : float
                Monthly complex maintenance dues in USD.
            pitch_price : float
                Total investor entry cost (MAO + assignment fee) used as
                the denominator for Cash-on-Cash return.

        Returns:
            dict[str, float | None]
                Dictionary keyed by STR metric field names, suitable for
                unpacking into ``WholesaleDealMetrics`` constructor kwargs.

        Side Effects:
            None.  Stateless pure computation.
        """
        monthly_gross = nightly_rate * 30 * occupancy_pct
        pm_cost = monthly_gross * _PM_FEE_RATIO
        monthly_net = monthly_gross - pm_cost - monthly_maintenance - _MAINTENANCE_RESERVE
        annual_noi = monthly_net * 12

        cash_on_cash_pct = (annual_noi / pitch_price) * 100 if pitch_price > 0 else 0.0

        return {
            "str_monthly_gross": round(monthly_gross, 2),
            "str_pm_cost": round(pm_cost, 2),
            "str_monthly_net": round(monthly_net, 2),
            "str_annual_noi": round(annual_noi, 2),
            "str_cash_on_cash_pct": round(cash_on_cash_pct, 2),
            "str_projection_6mo": round(monthly_net * 6, 2),
            "str_projection_1yr": round(monthly_net * 12, 2),
            "str_projection_3yr": round(monthly_net * 36, 2),
        }

    def calculate_commercial_metrics(
        self,
        pitch_price: float,
        size_sqm: float,
        monthly_rent_per_sqm: float,
        vacancy_rate: float = 0.10,
        annual_taxes_insurance: float = 0.0,
    ) -> CommercialYieldMetrics:
        """Calculate commercial cap rate metrics."""
        annual_gross = (size_sqm * monthly_rent_per_sqm) * 12
        egi = annual_gross * (1 - vacancy_rate)
        annual_noi = egi - annual_taxes_insurance
        cap_rate = (annual_noi / pitch_price) * 100 if pitch_price > 0 else 0.0
        return CommercialYieldMetrics(
            annual_gross_rent=round(annual_gross, 2),
            effective_gross_income=round(egi, 2),
            annual_noi=round(annual_noi, 2),
            cap_rate_pct=round(cap_rate, 2),
        )

    def calculate_ltr_metrics(
        self,
        pitch_price: float,
        monthly_rent: float,
        vacancy_rate: float = 0.05,
        pm_fee_pct: float = 0.10,
        monthly_maintenance: float = 0.0,
    ) -> LtrYieldMetrics:
        """Calculate LTR corporate lease cap rate metrics."""
        annual_gross = monthly_rent * 12
        egr = annual_gross * (1 - vacancy_rate)
        operating_expenses = (annual_gross * pm_fee_pct) + (monthly_maintenance * 12)
        annual_noi = egr - operating_expenses
        cap_rate = (annual_noi / pitch_price) * 100 if pitch_price > 0 else 0.0
        return LtrYieldMetrics(
            annual_gross_rent=round(annual_gross, 2),
            effective_gross_rent=round(egr, 2),
            operating_expenses=round(operating_expenses, 2),
            annual_noi=round(annual_noi, 2),
            cap_rate_pct=round(cap_rate, 2),
        )

    def _build_metrics(
        self,
        target: PropertyListing,
        median_price_per_sqm: float,
        *,
        str_kwargs: dict[str, float | None] | None = None,
        commercial_metrics: CommercialYieldMetrics | None = None,
        ltr_metrics: LtrYieldMetrics | None = None,
    ) -> WholesaleDealMetrics:
        """
        Apply spec-locked heuristics to produce the final deal metrics payload.

        Purpose:
            Translates the sector median and target property attributes into
            the turnkey ``WholesaleDealMetrics`` output according to the formulas
            defined in ``.spec-kit/specs/api/wholesale-analytics-engine.spec.md``.
            When ``str_kwargs`` is provided, merges STR yield fields into the
            response (STREAM 6 PHASE 1.6).

        Parameters:
            target : PropertyListing
                The validated target property with populated ``square_meters``
                and ``sector`` fields.
            median_price_per_sqm : float
                Sector median price in USD per square metre (output of
                ``_compute_median_price_per_sqm``).
            str_kwargs : dict[str, float | None] | None
                Optional STR metric fields to include in the response.
            commercial_metrics : CommercialYieldMetrics | None
                Optional commercial cap rate metrics.
            ltr_metrics : LtrYieldMetrics | None
                Optional LTR cap rate metrics.

        Returns:
            WholesaleDealMetrics
                Fully populated response schema instance.

        Side Effects:
            None.
        """
        auto_emv = median_price_per_sqm * target.square_meters
        mao = auto_emv * _DISCOUNT_RATIO
        assignment_fee = max(auto_emv * _ASSIGNMENT_FEE_RATIO, _ASSIGNMENT_FEE_FLOOR)
        pitch_price = mao + assignment_fee

        recommended = StrDefaultPredictor.predict_defaults(
            square_meters=target.square_meters,
            province=target.province,
            sector=target.sector,
        )

        return WholesaleDealMetrics(
            property_id=str(target.id),
            sector=target.sector,
            sector_median_price_per_sqm=round(median_price_per_sqm, 2),
            auto_emv=round(auto_emv, 2),
            mao=round(mao, 2),
            assignment_fee=round(assignment_fee, 2),
            pitch_price=round(pitch_price, 2),
            recommended_str_assumptions=recommended,
            commercial_metrics=commercial_metrics,
            ltr_metrics=ltr_metrics,
            **(str_kwargs or {}),
        )
