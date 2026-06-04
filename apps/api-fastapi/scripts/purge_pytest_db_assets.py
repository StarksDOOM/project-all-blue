"""
Remove integration-test rows left in Postgres when pytest exits early (no fixture teardown).

Safe markers: #BLU-TEST* ids, example.test URLs, Pytest Integration titles, 900xxx remote_ids.

Usage (from apps/api-fastapi):
    .venv\\Scripts\\python.exe scripts/purge_pytest_db_assets.py
    .venv\\Scripts\\python.exe scripts/purge_pytest_db_assets.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import or_
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import engine  # noqa: E402
from models import PropertyListing, ScraperErrorLog  # noqa: E402
from tests.db_cleanup import delete_property_cascade  # noqa: E402


def _pytest_property_filters():
    return or_(
        PropertyListing.id.like("#BLU-TEST%"),
        PropertyListing.title.like("Pytest Integration Asset%"),
        PropertyListing.url.like("%example.test%"),
        PropertyListing.raw_description.ilike("%pytest%"),
        PropertyListing.remote_id.like("999%"),
    )


def purge(*, dry_run: bool = False) -> dict[str, int]:
    with Session(engine) as session:
        listings = session.exec(
            select(PropertyListing).where(_pytest_property_filters())
        ).all()
        scraper_rows = session.exec(
            select(ScraperErrorLog).where(
                or_(
                    ScraperErrorLog.url.like("%example.test%"),
                    ScraperErrorLog.remote_id.in_(["999001", "999002"]),
                )
            )
        ).all()

        if dry_run:
            return {
                "properties": len(listings),
                "scraper_error_logs": len(scraper_rows),
            }

        for listing in listings:
            delete_property_cascade(session, property_id=listing.id)

        for row in scraper_rows:
            session.delete(row)
        session.commit()

        return {
            "properties": len(listings),
            "scraper_error_logs": len(scraper_rows),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge pytest integration assets from Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Count only; do not delete")
    args = parser.parse_args()
    counts = purge(dry_run=args.dry_run)
    action = "Would remove" if args.dry_run else "Removed"
    print(
        f"{action}: {counts['properties']} propert(ies), "
        f"{counts['scraper_error_logs']} scraper_error_log(s)"
    )


if __name__ == "__main__":
    main()