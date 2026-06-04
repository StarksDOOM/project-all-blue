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


def ensure_phase6_schema() -> None:
    """Phase 6: post-execution audit certificate path on legal contracts."""
    statements = [
        """
        ALTER TABLE real_estate.legal_contracts
        ADD COLUMN IF NOT EXISTS audit_certificate_path VARCHAR
        """,
    ]
    with engine.connect() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.commit()


def ensure_docusign_schema() -> None:
    """DocuSign envelope tracking on legal contracts."""
    statements = [
        "ALTER TABLE real_estate.legal_contracts ADD COLUMN IF NOT EXISTS docusign_envelope_id VARCHAR",
        "ALTER TABLE real_estate.legal_contracts ADD COLUMN IF NOT EXISTS docusign_status VARCHAR",
        """
        CREATE INDEX IF NOT EXISTS ix_legal_contracts_docusign_envelope_id
        ON real_estate.legal_contracts (docusign_envelope_id)
        """,
    ]
    with engine.connect() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.commit()


def ensure_phase5_schema() -> None:
    """Phase 5: PDF tamper hash, secure PDF path, multi-party signature telemetry."""
    statements = [
        "ALTER TABLE real_estate.legal_contracts ADD COLUMN IF NOT EXISTS document_hash VARCHAR",
        "ALTER TABLE real_estate.legal_contracts ADD COLUMN IF NOT EXISTS pdf_file_path VARCHAR",
        """
        CREATE INDEX IF NOT EXISTS ix_legal_contracts_document_hash
        ON real_estate.legal_contracts (document_hash)
        """,
        "ALTER TABLE real_estate.transaction_sessions ADD COLUMN IF NOT EXISTS buyer_signed_at TIMESTAMPTZ",
        "ALTER TABLE real_estate.transaction_sessions ADD COLUMN IF NOT EXISTS seller_signed_at TIMESTAMPTZ",
        """
        ALTER TABLE real_estate.transaction_sessions
        ADD COLUMN IF NOT EXISTS signature_telemetry JSONB NOT NULL DEFAULT '{}'
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
        """
        CREATE INDEX IF NOT EXISTS ix_properties_active_portal
        ON real_estate.properties (source_portal)
        WHERE deleted_at IS NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_properties_portal_active_modified
        ON real_estate.properties (source_portal, last_modified DESC)
        WHERE deleted_at IS NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_properties_faceted_core
        ON real_estate.properties (source_portal, sector, bedrooms, price_usd)
        WHERE deleted_at IS NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_properties_faceted_agency
        ON real_estate.properties (agent_agency, last_modified DESC)
        WHERE deleted_at IS NULL AND agent_agency IS NOT NULL
        """,
    ]
    with engine.connect() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.commit()


def ensure_saved_searches_schema() -> None:
    """
    Additive DDL for STREAM 5 PHASE 3.0 Saved Searches & Match Notification Engine.

    - saved_search_alerts: user persisted filter matrix (filters_json stores canonical Phase 2 shape)
    - saved_search_matches: structured hits written by search_match_engine post-ingestion insert
    Safe to run repeatedly (IF NOT EXISTS + ALTER ADD IF NOT EXISTS for upgrade safety on test/dev DBs).
    """
    create_statements = [
        """
        CREATE TABLE IF NOT EXISTS real_estate.saved_search_alerts (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL DEFAULT 'tenant_all_blue',
            user_id VARCHAR NOT NULL DEFAULT 'legacy_tenant',
            title VARCHAR(80) NOT NULL,
            filters_json JSONB NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_matched_at TIMESTAMPTZ,
            server_version INTEGER NOT NULL DEFAULT 1,
            last_modified BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000),
            deleted_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS real_estate.saved_search_matches (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL DEFAULT 'tenant_all_blue',
            saved_search_alert_id VARCHAR NOT NULL
                REFERENCES real_estate.saved_search_alerts(id),
            user_id VARCHAR NOT NULL DEFAULT 'legacy_tenant',
            property_id VARCHAR NOT NULL
                REFERENCES real_estate.properties(id),
            matched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            match_details JSONB NOT NULL DEFAULT '{}',
            server_version INTEGER NOT NULL DEFAULT 1,
            last_modified BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000),
            deleted_at TIMESTAMPTZ
        )
        """,
    ]
    alter_statements = [
        # Safety for test DBs or partial prior runs where table existed before model/DDL stabilized
        "ALTER TABLE real_estate.saved_search_alerts ADD COLUMN IF NOT EXISTS tenant_id VARCHAR",
        "ALTER TABLE real_estate.saved_search_alerts ADD COLUMN IF NOT EXISTS server_version INTEGER",
        "ALTER TABLE real_estate.saved_search_alerts ADD COLUMN IF NOT EXISTS last_modified BIGINT",
        "ALTER TABLE real_estate.saved_search_alerts ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
        # Phase 5.0: additive user_id for tenant isolation (default for legacy dev data)
        "ALTER TABLE real_estate.saved_search_alerts ADD COLUMN IF NOT EXISTS user_id VARCHAR DEFAULT 'legacy_tenant'",
        "ALTER TABLE real_estate.saved_search_matches ADD COLUMN IF NOT EXISTS tenant_id VARCHAR",
        "ALTER TABLE real_estate.saved_search_matches ADD COLUMN IF NOT EXISTS server_version INTEGER",
        "ALTER TABLE real_estate.saved_search_matches ADD COLUMN IF NOT EXISTS last_modified BIGINT",
        "ALTER TABLE real_estate.saved_search_matches ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
        # Phase 5.0: user_id for direct tenant filtering on matches (additive, legacy default)
        "ALTER TABLE real_estate.saved_search_matches ADD COLUMN IF NOT EXISTS user_id VARCHAR DEFAULT 'legacy_tenant'",
        # Phase 4.0 delivery tracking columns (additive, safe on existing DBs)
        "ALTER TABLE real_estate.saved_search_matches ADD COLUMN IF NOT EXISTS delivery_status VARCHAR DEFAULT 'pending'",
        "ALTER TABLE real_estate.saved_search_matches ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ",
        "ALTER TABLE real_estate.saved_search_matches ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0",
        "ALTER TABLE real_estate.saved_search_matches ADD COLUMN IF NOT EXISTS error_message TEXT",
    ]
    index_statements = [
        """
        CREATE INDEX IF NOT EXISTS ix_saved_search_alerts_user_active
        ON real_estate.saved_search_alerts (user_id, is_active)
        WHERE deleted_at IS NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_saved_search_matches_alert_matched
        ON real_estate.saved_search_matches (saved_search_alert_id, matched_at DESC)
        WHERE deleted_at IS NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_saved_search_matches_property
        ON real_estate.saved_search_matches (property_id)
        WHERE deleted_at IS NULL
        """,
        # Phase 4.0: partial index for efficient pending delivery worker queries
        """
        CREATE INDEX IF NOT EXISTS ix_saved_search_matches_pending_delivery
        ON real_estate.saved_search_matches (delivery_status, matched_at)
        WHERE delivery_status = 'pending' AND deleted_at IS NULL
        """,
    ]
    with engine.connect() as connection:
        for statement in create_statements + alter_statements + index_statements:
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
    ensure_phase5_schema()
    ensure_docusign_schema()
    ensure_phase6_schema()
    ensure_saved_searches_schema()


def get_db_session() -> Generator[Session, None, None]:
    """
    Yield a request-scoped SQLModel session (FastAPI Depends).

    Do not pass this session into BackgroundTasks — use Session(engine) in orchestrator.
    """
    with Session(engine) as session:
        yield session


# Alias for routers that import get_db
get_db = get_db_session