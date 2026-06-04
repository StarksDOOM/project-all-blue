"""
Database engine, session factory, and additive schema helpers.

Used by FastAPI Depends(get_db_session), IngestionOrchestrator, and crawl_test.py.
"""

import os
import secrets
import time
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.schema import CreateSchema
from sqlmodel import SQLModel, Session

# Load DATABASE_URL from apps/api-fastapi/.env
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/all_blue",
)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)


def generate_blu_id() -> str:
    """Primary key factory for AllBlueBaseModel rows (e.g. #BLU-A1B2C3D4)."""
    return f"#BLU-{secrets.token_hex(4).upper()}"


def get_current_timestamp_ms() -> int:
    """Unix epoch milliseconds for last_modified fields and sync versioning."""
    return int(time.time() * 1000)


def ensure_transaction_schema() -> None:
    """Phase 4: transaction sessions and legal contract artifacts."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS real_estate.transaction_sessions (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL DEFAULT 'tenant_all_blue',
            property_id VARCHAR NOT NULL REFERENCES real_estate.properties(id),
            buyer_name VARCHAR NOT NULL,
            buyer_id_doc VARCHAR NOT NULL,
            seller_name VARCHAR NOT NULL,
            seller_id_doc VARCHAR NOT NULL,
            agreed_price DOUBLE PRECISION NOT NULL,
            currency VARCHAR NOT NULL DEFAULT 'USD',
            status VARCHAR NOT NULL DEFAULT 'DRAFT',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS real_estate.legal_contracts (
            id VARCHAR PRIMARY KEY,
            transaction_session_id VARCHAR NOT NULL
                REFERENCES real_estate.transaction_sessions(id),
            file_path VARCHAR,
            storage_url VARCHAR,
            document_body TEXT NOT NULL DEFAULT '',
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            version_hash VARCHAR NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_transaction_sessions_property_id
        ON real_estate.transaction_sessions (property_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_legal_contracts_session_id
        ON real_estate.legal_contracts (transaction_session_id)
        """,
    ]
    with engine.connect() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.commit()


def ensure_ingestion_schema() -> None:
    """
    Apply additive DDL required by STREAM 2 PHASE 4.1 ingestion.

    Safe to run on every startup (IF NOT EXISTS).
    """
    statements = [
        # Required for IngestionOrchestrator ON CONFLICT (source_portal, remote_id).
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_properties_source_portal_remote_id
        ON real_estate.properties (source_portal, remote_id)
        """,
        "ALTER TABLE real_estate.properties ADD COLUMN IF NOT EXISTS sqm_land DOUBLE PRECISION",
        "ALTER TABLE real_estate.properties ADD COLUMN IF NOT EXISTS listing_currency VARCHAR DEFAULT 'USD'",
        "ALTER TABLE real_estate.properties ADD COLUMN IF NOT EXISTS agent_name VARCHAR",
        "ALTER TABLE real_estate.properties ADD COLUMN IF NOT EXISTS agent_phone VARCHAR",
        "ALTER TABLE real_estate.properties ADD COLUMN IF NOT EXISTS agent_email VARCHAR",
        "ALTER TABLE real_estate.properties ADD COLUMN IF NOT EXISTS agent_whatsapp VARCHAR",
        "ALTER TABLE real_estate.properties ADD COLUMN IF NOT EXISTS agent_agency VARCHAR",
        "ALTER TABLE real_estate.properties ADD COLUMN IF NOT EXISTS list_price DOUBLE PRECISION",
        "ALTER TABLE real_estate.properties ADD COLUMN IF NOT EXISTS image_urls JSONB",
        """
        CREATE TABLE IF NOT EXISTS real_estate.scraper_error_logs (
            id VARCHAR PRIMARY KEY,
            remote_id VARCHAR,
            url VARCHAR,
            scraper_method VARCHAR NOT NULL,
            error_type VARCHAR NOT NULL,
            stack_trace TEXT NOT NULL,
            resolved BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_scraper_error_logs_unresolved
        ON real_estate.scraper_error_logs (resolved, created_at DESC)
        WHERE resolved = FALSE
        """,
    ]
    with engine.connect() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.commit()


def ensure_contract_schema() -> None:
    """Apply additive column migrations for srl_contracts on existing databases."""
    column_statements = [
        "ALTER TABLE real_estate.srl_contracts ADD COLUMN IF NOT EXISTS property_remote_id VARCHAR",
        "ALTER TABLE real_estate.srl_contracts ADD COLUMN IF NOT EXISTS buyer_name VARCHAR",
        "ALTER TABLE real_estate.srl_contracts ADD COLUMN IF NOT EXISTS buyer_id VARCHAR",
        "ALTER TABLE real_estate.srl_contracts ADD COLUMN IF NOT EXISTS seller_name VARCHAR",
        "ALTER TABLE real_estate.srl_contracts ADD COLUMN IF NOT EXISTS seller_id VARCHAR",
        "ALTER TABLE real_estate.srl_contracts ADD COLUMN IF NOT EXISTS document_body TEXT NOT NULL DEFAULT ''",
    ]
    with engine.connect() as connection:
        for statement in column_statements:
            connection.execute(text(statement))
        connection.commit()


def init_db() -> None:
    """
    Create real_estate schema, SQLModel tables, and additive indexes/columns.

    Called from FastAPI lifespan and CLI sync entrypoints.
    """
    with engine.connect() as connection:
        connection.execute(CreateSchema("real_estate", if_not_exists=True))
        connection.commit()
    SQLModel.metadata.create_all(engine)
    ensure_contract_schema()
    ensure_ingestion_schema()
    ensure_transaction_schema()


def get_db_session() -> Generator[Session, None, None]:
    """
    Yield a request-scoped SQLModel session (FastAPI Depends).

    Do not pass this session into BackgroundTasks — use Session(engine) in orchestrator.
    """
    with Session(engine) as session:
        yield session


# Alias for routers that import get_db
get_db = get_db_session