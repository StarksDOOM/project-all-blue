"""
Short-Term Rental (STR) Default Predictor utility.

STREAM 6 PHASE 1.6.1 — Dynamic STR Pre-fills.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class StrDefaultPredictor:
    """Predicts recommended STR assumptions based on property size and location."""

    @staticmethod
    def predict_defaults(
        square_meters: float | None,
        province: str | None,
        sector: str | None = None,
    ) -> dict[str, float]:
        """
        Derive recommended nightly_rate, occupancy_pct, and monthly_maintenance.

        Rules:
            - Maintenance: square_meters * 2.50. Fallback to 150.00 if size is <= 0 or None.
            - ADR (nightly_rate) and Occupancy based on location text matching (case-insensitive):
                - "punta cana" or "altagracia" -> $169.00 ADR, 0.45 Occupancy
                - "las terrenas" or "samana" -> $234.00 ADR, 0.40 Occupancy
                - "santo domingo" -> $80.00 ADR, 0.40 Occupancy
                - Fallback -> $120.00 ADR, 0.40 Occupancy

        Parameters:
            square_meters : float | None
                Size of the property in square meters.
            province : str | None
                The province/city name of the property.
            sector : str | None
                The sector/neighborhood of the property.

        Returns:
            dict[str, float]
                A dictionary containing:
                    - "nightly_rate": float
                    - "occupancy_pct": float
                    - "monthly_maintenance": float
        """
        # Determine monthly maintenance
        if square_meters is None or square_meters <= 0:
            monthly_maintenance = 150.00
        else:
            monthly_maintenance = min(round(square_meters * 2.50, 2), 400.00)

        # Build location search string
        loc_str = ""
        if province:
            loc_str += province.lower()
        if sector:
            loc_str += " " + sector.lower()

        # Match location rules
        if "punta cana" in loc_str or "altagracia" in loc_str:
            nightly_rate = 169.00
            occupancy_pct = 0.45
        elif "las terrenas" in loc_str or "samana" in loc_str:
            nightly_rate = 234.00
            occupancy_pct = 0.40
        elif "santo domingo" in loc_str:
            nightly_rate = 80.00
            occupancy_pct = 0.40
        else:
            nightly_rate = 120.00
            occupancy_pct = 0.40

        return {
            "nightly_rate": nightly_rate,
            "occupancy_pct": occupancy_pct,
            "monthly_maintenance": monthly_maintenance,
        }
