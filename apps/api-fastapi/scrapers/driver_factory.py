"""
Driver factory registry (Open/Closed Principle).

Maps string portal tokens from the API to concrete BaseDriver classes without
the orchestrator or router hard-coding class names.
"""

from __future__ import annotations

from typing import Type

from sqlmodel import Session

from scrapers.drivers.base_driver import BaseDriver
from scrapers.drivers.remaxrd import RemaxRdDriver
from scrapers.drivers.realtor import RealtorDriver

# Type alias for registry values (uninstantiated driver classes).
DriverClass = Type[BaseDriver]


class DriverFactory:
    """
    Encapsulated registry + instantiation for portal drivers.

    To add a portal: import the class, add one line to _registry, implement BaseDriver.
    """

    # Portal token (lowercase) → driver class. Keys are the only supported ?source_portal values.
    _registry: dict[str, DriverClass] = {
        "remaxrd": RemaxRdDriver,
        "realtor": RealtorDriver,
    }

    @classmethod
    def supported_portals(cls) -> frozenset[str]:
        """Return immutable set of keys accepted by create_driver."""
        return frozenset(cls._registry.keys())

    def create_driver(self, source_portal: str, db_session: Session) -> BaseDriver:
        """
        Build a stateful driver for the requested portal.

        Args:
            source_portal: Query param from trigger-crawl (case-insensitive).
            db_session: Request or background SQLModel session.

        Returns:
            Configured BaseDriver instance.

        Raises:
            ValueError: Unknown portal — mapped to HTTP 400 in properties router.
        """
        # Normalize token so API callers are not case-sensitive.
        key = (source_portal or "").strip().lower()
        driver_cls = self._registry.get(key)
        if driver_cls is None:
            supported = ", ".join(sorted(self._registry.keys()))
            raise ValueError(
                f"Unsupported source_portal '{source_portal}'. "
                f"Supported portals: {supported}"
            )
        return driver_cls(db_session)