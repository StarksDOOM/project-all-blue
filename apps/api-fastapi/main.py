"""
All Blue Core — FastAPI entrypoint.

Mounts:
  - properties router (listings + trigger-crawl)
  - contracts router (SRL draft engine)

Startup ensures Postgres schema, contract migrations, and ingestion unique index.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import (
    ensure_contract_schema,
    ensure_ingestion_schema,
    ensure_docusign_schema,
    ensure_phase6_schema,
    ensure_phase5_schema,
    ensure_transaction_schema,
    init_db,
)
from routers import admin, contracts, docusign, properties, realtime, transactions

# Load DATABASE_URL, CORS_ORIGINS, ADSPOWER_* from apps/api-fastapi/.env
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: bootstrap database artifacts before serving traffic.

    init_db creates tables; ensure_* applies additive indexes/columns on existing DBs.
    """
    import asyncio

    from services.realtime_broadcaster import bind_app_event_loop

    bind_app_event_loop(asyncio.get_running_loop())
    init_db()
    ensure_contract_schema()
    ensure_ingestion_schema()
    ensure_transaction_schema()
    ensure_phase5_schema()
    ensure_docusign_schema()
    ensure_phase6_schema()
    yield


app = FastAPI(title="All Blue Core API", version="0.2.0", lifespan=lifespan)

_default_cors = "http://localhost:3000,http://127.0.0.1:3000"
_cors_raw = os.getenv("CORS_ORIGINS", _default_cors)
allow_origins = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(properties.router)
app.include_router(contracts.router)
app.include_router(admin.router)
app.include_router(transactions.router)
app.include_router(docusign.router)
app.include_router(realtime.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for Docker / load balancers."""
    return {"status": "ok"}