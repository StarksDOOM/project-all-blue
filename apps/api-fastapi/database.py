import os
import secrets
import time
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.schema import CreateSchema
from sqlmodel import SQLModel, Session
from dotenv import load_dotenv

# Load variables out of the local .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/all_blue")

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

def generate_blu_id() -> str:
    return f"#BLU-{secrets.token_hex(4).upper()}"

def get_current_timestamp_ms() -> int:
    return int(time.time() * 1000)

def ensure_contract_schema() -> None:
    """Apply additive migrations for srl_contracts on existing databases."""
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
    with engine.connect() as connection:
        connection.execute(CreateSchema("real_estate", if_not_exists=True))
        connection.commit()
    SQLModel.metadata.create_all(engine)
    ensure_contract_schema()

def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session