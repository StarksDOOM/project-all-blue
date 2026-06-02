import os
import secrets
import time
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateSchema
from sqlmodel import Session, SQLModel

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/all_blue"
)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)


def generate_blu_id() -> str:
    return f"#BLU-{secrets.token_hex(4).upper()}"


def get_current_timestamp_ms() -> int:
    return int(time.time() * 1000)


def init_db() -> None:
    with engine.connect() as connection:
        connection.execute(CreateSchema("real_estate", if_not_exists=True))
        connection.commit()
    SQLModel.metadata.create_all(engine)


def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session