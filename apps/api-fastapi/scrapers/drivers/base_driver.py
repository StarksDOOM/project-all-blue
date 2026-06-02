"""
Abstract portal driver contract (STREAM 2 PHASE 4.1).

Defines the interface every listing portal must implement so IngestionOrchestrator
stays decoupled from RE/MAX, Realtor, or future sources (Dependency Inversion).

See: .spec-kit/specs/api/ingestion-oop.spec.md
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sqlmodel import Session

from models import PropertyListing


class BaseDriver(ABC):
    """
    Portal driver contract (LSP / DIP).

    Subclasses own network/auth mechanics; the orchestrator owns Postgres upserts.
    """

    # Set on each concrete driver; used for logging, upserts, and IngestionSyncJob rows.
    source_portal: str

    def __init__(self, db_session: Session) -> None:
        """
        Store the SQLModel session for optional read-side lookups.

        Drivers must not commit writes — persistence is orchestrator-only (SRP).
        """
        self._db_session = db_session

    @property
    def db_session(self) -> Session:
        """Expose session for helpers that need existence checks before fetch."""
        return self._db_session

    @abstractmethod
    async def initialize(self) -> None:
        """
        Bootstrap portal access (e.g. AdsPower credential harvest).

        Called once per job before run_sync. Must be idempotent-safe when re-run.
        """

    @abstractmethod
    async def run_sync(self) -> list[PropertyListing]:
        """
        Fetch all listings for this portal and map to PropertyListing rows.

        Returns:
            In-memory models ready for chunked upsert (all required scalars set).

        Raises:
            NotImplementedError: For registered-but-unbuilt drivers (realtor stub).
            RuntimeError: When upstream API or auth fails unrecoverably.
        """