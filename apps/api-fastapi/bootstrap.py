from sqlmodel import SQLModel, create_engine, text
from database import engine  # Assumes this imports the engine from your DB config
import models  # Import your models module to register them with metadata

def ensure_db_initialized():
    """Checks for the real_estate schema and creates all tables if missing."""
    with engine.connect() as conn:
        # 1. Create the schema if it doesn't exist
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS real_estate;"))
        conn.commit()
        
    # 2. Sync models to the database
    # This will create tables for every class that inherits from SQLModel and has table=True
    SQLModel.metadata.create_all(engine)
    print("[Database] Schema and tables verified/initialized.")

if __name__ == "__main__":
    ensure_db_initialized()