"""
Stateful ingestion orchestration (STREAM 2 PHASE 4.1).

IngestionOrchestrator is the only component that:
  - Runs driver.initialize() + driver.run_sync()
  - Persists PropertyListing rows in chunked Postgres upserts
  - Tracks IngestionSyncJob lifecycle (PENDING → RUNNING → COMPLETED/FAILED)

Drivers depend on BaseDriver; this module depends on DriverFactory — not on RemaxRdDriver.
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, select

from database import engine, get_current_timestamp_ms, init_db
from models import IngestionSyncJob, PropertyListing, SyncJobStatus
from scrapers.drivers.base_driver import BaseDriver
from scrapers.driver_factory import DriverFactory

logger = logging.getLogger(__name__)

# Legacy RemaxRDScraper batch size — balances memory vs transaction length.
BULK_CHUNK_SIZE = 250

# Columns overwritten when (source_portal, remote_id) already exists in properties.
_UPSERT_UPDATE_COLUMNS = (
    "url",
    "title",
    "price_usd",
    "price_dop",
    "province",
    "sector",
    "bedrooms",
    "bathrooms",
    "square_meters",
    "raw_description",
    "is_active",
    "last_modified",
    "server_version",
)


class IngestionOrchestrator:
    """
    Coordinates portal drivers, bulk upsert, and sync job state.

    Instantiate with a live SQLModel Session; use run_sync_for_portal() from background tasks.
    """

    def __init__(self, db_session: Session) -> None:
        """Bind orchestrator to an open database session for job + property writes."""
        self._db_session = db_session

    @property
    def db_session(self) -> Session:
        """Read-only accessor for tests or future extensions."""
        return self._db_session

    def _create_job(self, source_portal: str) -> IngestionSyncJob:
        """
        Insert a new IngestionSyncJob row in PENDING state.

        Commits immediately so background workers can observe job id before work starts.
        """
        job = IngestionSyncJob(source_portal=source_portal, status=SyncJobStatus.PENDING)
        self._db_session.add(job)
        self._db_session.commit()
        self._db_session.refresh(job)
        return job

    def _set_job_status(
        self,
        job: IngestionSyncJob,
        status: SyncJobStatus,
        *,
        error_message: str | None = None,
    ) -> None:
        """
        Transition job status and optionally persist failure reason.

        Args:
            job: Row created by _create_job.
            status: Next lifecycle enum value.
            error_message: Truncated to 2000 chars for FAILED jobs.
        """
        job.status = status
        if error_message is not None:
            job.error_message = error_message[:2000]
        job.last_modified = get_current_timestamp_ms()
        self._db_session.add(job)
        self._db_session.commit()

    def execute_sync_job(
        self,
        driver: BaseDriver,
        job: IngestionSyncJob | None = None,
    ) -> dict[str, Any]:
        """
        Run a full portal sync synchronously (CLI or BackgroundTasks worker).

        Args:
            driver: Portal-specific BaseDriver from DriverFactory.
            job: Existing job row, or None to create one.

        Returns:
            Metrics dict: source_portal, fetched, inserted, updated, job_id, status, elapsed_seconds.
        """
        portal = getattr(driver, "source_portal", "unknown")
        if job is None:
            job = self._create_job(portal)

        started = time.perf_counter()
        self._set_job_status(job, SyncJobStatus.RUNNING)
        logger.info("IngestionOrchestrator: job=%s portal=%s RUNNING", job.id, portal)

        try:
            # asyncio.run is safe here — FastAPI background thread has no running loop.
            result = asyncio.run(self._execute_async(driver))
            job.fetched = result["fetched"]
            job.inserted = result["inserted"]
            job.updated = result["updated"]
            self._set_job_status(job, SyncJobStatus.COMPLETED)
            elapsed = time.perf_counter() - started
            result["job_id"] = job.id
            result["status"] = SyncJobStatus.COMPLETED.value
            result["elapsed_seconds"] = round(elapsed, 2)
            logger.info(
                "IngestionOrchestrator: job=%s COMPLETED fetched=%s inserted=%s updated=%s elapsed=%.2fs",
                job.id,
                result["fetched"],
                result["inserted"],
                result["updated"],
                elapsed,
            )
            return result
        except NotImplementedError:
            self._set_job_status(
                job,
                SyncJobStatus.FAILED,
                error_message="Driver not implemented",
            )
            raise
        except Exception as exc:
            self._set_job_status(job, SyncJobStatus.FAILED, error_message=str(exc))
            logger.exception(
                "IngestionOrchestrator: job=%s FAILED portal=%s error=%s",
                job.id,
                portal,
                exc,
            )
            raise

    async def _execute_async(self, driver: BaseDriver) -> dict[str, Any]:
        """
        Async pipeline: harvest → fetch → upsert (no job status side effects).

        Separated from execute_sync_job so asyncio.run wraps only I/O-bound work.
        """
        await driver.initialize()
        listings = await driver.run_sync()
        metrics = self._bulk_upsert_chunks(listings)
        return {
            "source_portal": getattr(driver, "source_portal", "unknown"),
            "fetched": len(listings),
            "inserted": metrics["inserted"],
            "updated": metrics["updated"],
        }

    def _bulk_upsert_chunks(self, listings: list[PropertyListing]) -> dict[str, int]:
        """
        Upsert all listings in BULK_CHUNK_SIZE slices with commit per chunk.

        Returns:
            Aggregated inserted/updated counts across chunks.
        """
        if not listings:
            return {"inserted": 0, "updated": 0}

        inserted_total = 0
        updated_total = 0

        for i in range(0, len(listings), BULK_CHUNK_SIZE):
            chunk = listings[i : i + BULK_CHUNK_SIZE]
            metrics = self._upsert_chunk(chunk)
            inserted_total += metrics["inserted"]
            updated_total += metrics["updated"]
            self._db_session.commit()

        return {"inserted": inserted_total, "updated": updated_total}

    def _upsert_chunk(self, chunk: list[PropertyListing]) -> dict[str, int]:
        """
        PostgreSQL INSERT .. ON CONFLICT (source_portal, remote_id) DO UPDATE.

        Requires unique index uq_properties_source_portal_remote_id (ensure_ingestion_schema).
        """
        if not chunk:
            return {"inserted": 0, "updated": 0}

        portal = chunk[0].source_portal
        remote_ids = [row.remote_id for row in chunk]
        # Metrics: count rows that existed before this statement (upsert handles both paths).
        existing_ids = self._existing_remote_ids(portal, remote_ids)

        now_ms = get_current_timestamp_ms()
        rows: list[dict[str, Any]] = []
        inserted = 0
        updated = 0

        for listing in chunk:
            if listing.remote_id in existing_ids:
                updated += 1
            else:
                inserted += 1
            rows.append(self._listing_to_row(listing, now_ms))

        table = PropertyListing.__table__  # type: ignore[attr-defined]
        insert_stmt = pg_insert(table).values(rows)
        excluded = insert_stmt.excluded
        # Map EXCLUDED.* to column updates on conflict.
        update_map = {
            column: getattr(excluded, column)
            for column in _UPSERT_UPDATE_COLUMNS
            if column not in ("last_modified", "server_version")
        }
        update_map["last_modified"] = now_ms
        update_map["server_version"] = table.c.server_version + 1

        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["source_portal", "remote_id"],
            set_=update_map,
        )
        self._db_session.execute(upsert_stmt)
        return {"inserted": inserted, "updated": updated}

    def _listing_to_row(self, listing: PropertyListing, now_ms: int) -> dict[str, Any]:
        """
        Flatten PropertyListing ORM object to dict for pg_insert().values().

        id is generated on model construction via generate_blu_id default_factory.
        """
        return {
            "id": listing.id,
            "tenant_id": listing.tenant_id or "tenant_all_blue",
            "server_version": listing.server_version or 1,
            "last_modified": now_ms,
            "deleted_at": listing.deleted_at,
            "remote_id": listing.remote_id,
            "source_portal": listing.source_portal,
            "url": listing.url,
            "title": listing.title,
            "price_usd": listing.price_usd,
            "price_dop": listing.price_dop,
            "province": listing.province,
            "sector": listing.sector,
            "bedrooms": listing.bedrooms,
            "bathrooms": listing.bathrooms,
            "square_meters": listing.square_meters,
            "raw_description": listing.raw_description,
            "is_active": listing.is_active,
        }

    def _existing_remote_ids(self, source_portal: str, remote_ids: list[str]) -> set[str]:
        """
        Lookup which remote_ids already exist for a portal within the current chunk.

        Used only for insert/update metrics — conflict resolution is in SQL upsert.
        """
        if not remote_ids:
            return set()
        statement = select(PropertyListing.remote_id).where(
            PropertyListing.source_portal == source_portal,
            PropertyListing.remote_id.in_(remote_ids),
        )
        rows = self._db_session.exec(statement).all()
        return {row for row in rows if row}

    @classmethod
    def run_sync_for_portal(cls, source_portal: str) -> dict[str, Any]:
        """
        Entry point for FastAPI BackgroundTasks — owns Session lifecycle.

        Never pass the request-scoped Depends(get_db_session) session here; it closes
        when the 202 response returns.
        """
        init_db()
        portal = (source_portal or "").strip().lower()
        with Session(engine) as session:
            factory = DriverFactory()
            driver = factory.create_driver(portal, session)
            orchestrator = cls(session)
            job = orchestrator._create_job(portal)
            return orchestrator.execute_sync_job(driver, job)


def execute_portal_sync_background(source_portal: str) -> None:
    """
    Thin wrapper for background_tasks.add_task(...).

    Catches and prints exceptions so one failed crawl does not crash the API process.
    """
    try:
        IngestionOrchestrator.run_sync_for_portal(source_portal)
    except Exception:
        traceback.print_exc()


def run_portal_sync(source_portal: str) -> dict[str, Any]:
    """
    Synchronous entry for crawl_test.py and manual operator runs.

    Same orchestration path as HTTP trigger-crawl background job.
    """
    init_db()
    portal = (source_portal or "").strip().lower()
    with Session(engine) as session:
        factory = DriverFactory()
        driver = factory.create_driver(portal, session)
        orchestrator = IngestionOrchestrator(session)
        job = orchestrator._create_job(portal)
        return orchestrator.execute_sync_job(driver, job)