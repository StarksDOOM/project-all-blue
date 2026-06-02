"""
CLI entry for portal ingestion sync.

Uses the same IngestionOrchestrator + DriverFactory stack as:
  POST /api/v1/properties/trigger-crawl

Example:
  python crawl_test.py --portal remaxrd
"""

import argparse
import logging
import sys

from services.sync_service import run_portal_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def main() -> int:
    """Parse CLI args, run sync, print metrics, return process exit code."""
    parser = argparse.ArgumentParser(description="Run All Blue portal ingestion sync")
    parser.add_argument(
        "--portal",
        default="remaxrd",
        help="Portal key registered in DriverFactory (remaxrd, realtor)",
    )
    args = parser.parse_args()

    try:
        result = run_portal_sync(args.portal)
    except ValueError as exc:
        # Unknown portal token — same message as HTTP 400.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except NotImplementedError as exc:
        # realtor stub — same as HTTP 501 path.
        print(f"NOT IMPLEMENTED: {exc}", file=sys.stderr)
        return 2

    print(
        f"OK portal={result['source_portal']} job={result.get('job_id')} "
        f"status={result.get('status')} fetched={result['fetched']} "
        f"inserted={result['inserted']} updated={result['updated']} "
        f"elapsed={result.get('elapsed_seconds')}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())