"""Backfill list_price from listing_currency + price_usd/price_dop for crawl rows."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from database import engine, init_db

init_db()

with engine.connect() as conn:
    conn.execute(
        text(
            """
            UPDATE real_estate.properties
            SET list_price = price_usd
            WHERE (list_price IS NULL OR list_price = 0)
              AND COALESCE(listing_currency, 'USD') = 'USD'
              AND price_usd > 0
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE real_estate.properties
            SET list_price = price_dop
            WHERE (list_price IS NULL OR list_price = 0)
              AND listing_currency = 'DOP'
              AND price_dop IS NOT NULL
              AND price_dop > 0
            """
        )
    )
    conn.commit()
    print("list_price backfill complete")