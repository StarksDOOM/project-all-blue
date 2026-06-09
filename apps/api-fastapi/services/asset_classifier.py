"""Asset Classifier service for property categorization.

STREAM 6 PHASE 1.8.
"""

from __future__ import annotations

import logging
from models import PropertyListing

logger = logging.getLogger(__name__)


class AssetClassifier:
    """Resilient text-scanning engine classifying properties upon ingestion."""

    @staticmethod
    def classify_property_listing(listing: PropertyListing) -> None:
        """Scan property title and description to tag listing and property types.

        Inspects the text case-insensitively. Sets:
            - listing_type to "FOR_RENT" if rent keywords matched, else "FOR_SALE"
            - property_type to "COMMERCIAL" if commercial keywords matched, else "RESIDENTIAL"
        """
        # Combine title and description for single scanning pass
        scan_text = f"{listing.title or ''} {listing.raw_description or ''}".lower()

        # Listing type classification
        rent_keywords = ["alquiler", "renta", "for rent", "se alquila"]
        is_rent = any(kw in scan_text for kw in rent_keywords)
        listing.listing_type = "FOR_RENT" if is_rent else "FOR_SALE"

        # Property type classification
        comm_keywords = [
            "local comercial",
            "nave industrial",
            "plaza",
            "oficina",
            "edificio corporativo",
        ]
        is_comm = any(kw in scan_text for kw in comm_keywords)
        listing.property_type = "COMMERCIAL" if is_comm else "RESIDENTIAL"

        logger.info(
            "Classified property remote_id=%s: listing_type=%s, property_type=%s",
            listing.remote_id,
            listing.listing_type,
            listing.property_type,
        )
