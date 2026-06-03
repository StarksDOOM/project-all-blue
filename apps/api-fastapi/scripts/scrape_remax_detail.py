#!/usr/bin/env python3
"""
CLI: scrape RE/MAX property detail from a listing URL (reuses PropertyListing.url).

Examples:
    python scripts/scrape_remax_detail.py --url "https://www.remaxrd.com/propiedad/casa/vendo-casa-de-oportunidad-en-nisibon-222598?city=higüey"
    python scripts/scrape_remax_detail.py --remote-id 222574
    python scripts/scrape_remax_detail.py --from-db --remote-id 222574
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select

from database import engine
from models import PropertyListing
from scrapers.remax_detail_scraper import RemaxDetailScrapeError, scrape_remax_property_detail


def _resolve_url(args: argparse.Namespace) -> str:
    if args.url:
        return args.url.strip()

    if not args.remote_id:
        raise SystemExit("Provide --url or --remote-id")

    if args.from_db:
        with Session(engine) as session:
            listing = session.exec(
                select(PropertyListing).where(PropertyListing.remote_id == str(args.remote_id))
            ).first()
            if listing is None:
                raise SystemExit(f"No PropertyListing with remote_id={args.remote_id}")
            return listing.url

    slug_hint = args.slug or f"property-{args.remote_id}"
    return f"https://www.remaxrd.com/propiedad/{slug_hint}-{args.remote_id}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape RE/MAX RD property detail page")
    parser.add_argument("--url", help="Full RE/MAX storefront URL to scrape")
    parser.add_argument("--remote-id", help="Portal property id (uses DB url with --from-db)")
    parser.add_argument("--slug", help="Optional slug prefix when synthesizing URL")
    parser.add_argument("--city", dest="city_slug", help="city= query param for SSR hydration")
    parser.add_argument("--from-db", action="store_true", help="Load PropertyListing.url from Postgres")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    try:
        target_url = _resolve_url(args)
        detail = scrape_remax_property_detail(target_url, city_slug=args.city_slug)
    except RemaxDetailScrapeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.pretty:
        print(json.dumps(detail, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(detail, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())